import json
import uuid
from pathlib import Path

from docpilot.agent import Agent, ScriptedBackend
from docpilot.documents import DocumentTools
from docpilot.fixtures import generate_fixture_traces, sample_session
from docpilot.storage import Storage


def test_fixture_traces(tmp_path):
    result = generate_fixture_traces(str(tmp_path / 'db.sqlite3'), tmp_path / 'traces')
    assert result['success_1']['status'] == 'completed'
    assert result['near_failure_recovery']['status'] == 'completed'
    assert result['explicit_failure']['status'] == 'failed'
    assert result['explicit_failure']['failure_reason'] == 'repetition_limit'
    for name in result:
        rows = [json.loads(x) for x in (tmp_path / 'traces' / (name + '.jsonl')).read_text().splitlines()]
        assert rows and all(row['backend'] == 'scripted_fixture' for row in rows)


def test_memory_survives_restart(tmp_path):
    path = str(tmp_path / 'persist.sqlite3')
    owner = str(uuid.uuid4())
    store = Storage(path)
    store.save_memory(owner, 'language', 'Arabic')
    del store
    assert Storage(path).recall_memory(owner, 'language')['value'] == 'Arabic'


def test_scoped_document_access(tmp_path):
    store = Storage(str(tmp_path / 'scoped.sqlite3'))
    owner, docs = sample_session(store)
    other = str(uuid.uuid4())
    tool = DocumentTools(store)
    assert tool.list_documents(other)['count'] == 0
    assert tool.read_document(other, docs['supplier_agreement.md']['id'])['error']


def test_approval_denial_and_approval(tmp_path):
    store = Storage(str(tmp_path / 'writes.sqlite3'))
    owner = str(uuid.uuid4())
    steps = [{'calls': [{'name': 'save_memory', 'args': {'key': 'tone', 'value': 'formal'}}]},
             {'calls': [{'name': 'final_answer', 'args': {'answer': 'Done.', 'citations': []}}]}]
    agent = Agent(store, ScriptedBackend(steps))
    state = agent.advance(agent.start('Remember my preferred writing tone', owner, trace_dir=tmp_path))
    assert state.status == 'approval_required'
    state = agent.advance(state, approval=False)
    assert state.status == 'completed'
    assert store.recall_memory(owner, 'tone')['found'] is False
    agent2 = Agent(store, ScriptedBackend(steps))
    state2 = agent2.advance(agent2.start('Remember my preferred writing tone', owner, trace_dir=tmp_path))
    assert state2.status == 'approval_required'
    state2 = agent2.advance(state2, approval=True)
    assert state2.status == 'completed'
    assert store.recall_memory(owner, 'tone')['value'] == 'formal'


def test_unknown_tool_blocked(tmp_path):
    store = Storage(str(tmp_path / 'attack.sqlite3'))
    agent = Agent(store, ScriptedBackend([{'calls': [{'name': 'run_shell', 'args': {'cmd': 'cat .env'}}]}]))
    state = agent.advance(agent.start('Run a dangerous tool', str(uuid.uuid4()), trace_dir=tmp_path))
    assert state.status == 'failed' and state.failure_reason == 'unauthorized_tool'


def test_prompt_injection_remains_document_data(tmp_path):
    store = Storage(str(tmp_path / 'injected.sqlite3'))
    owner, docs = sample_session(store)
    doc = docs['untrusted_invoice.txt']['id']
    contents = DocumentTools(store).read_document(owner, doc)
    assert contents.get('warning')
    assert contents.get('reference') == f'{doc}:p1'
    # No shell or arbitrary filesystem tool is in the agent's allowlist.
    from docpilot.agent import TOOL_NAMES
    assert 'run_shell' not in TOOL_NAMES and 'delete_file' not in TOOL_NAMES