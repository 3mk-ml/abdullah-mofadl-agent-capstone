"""UI and document-flow invariants, runnable without an API key."""
import hashlib
import uuid
from pathlib import Path
from docpilot.storage import Storage

ROOT = Path(__file__).resolve().parents[1]


def test_upload_hash_visible_and_duplicate_detection_possible(tmp_path):
    store = Storage(str(tmp_path / 'docs.sqlite3'))
    owner = str(uuid.uuid4())
    raw = b'DocPilot source text: deadline is 2026-11-01.'
    doc = store.add_document(owner, 'notes.txt', raw)
    indexed = store.list_documents(owner)
    assert len(indexed) == 1
    assert indexed[0]['id'] == doc['id']
    assert indexed[0]['sha256'] == hashlib.sha256(raw).hexdigest()
    assert indexed[0]['page_count'] >= 1


def test_document_removal_is_scoped_and_cascades(tmp_path):
    store = Storage(str(tmp_path / 'docs.sqlite3'))
    owner, other = str(uuid.uuid4()), str(uuid.uuid4())
    doc = store.add_document(owner, 'a.md', b'hello world')
    assert store.delete_document(other, doc['id']) is False
    assert len(store.get_pages(owner, doc['id'])) == 1
    assert store.delete_document(owner, doc['id']) is True
    assert not store.get_pages(owner, doc['id'])


def test_app_distinguishes_user_and_demo_document_sources():
    ui = (ROOT / 'app.py').read_text(encoding='utf-8')
    assert 'My documents' in ui
    assert 'Guided evaluation demo' in ui
    assert 'Import selected documents' not in ui
    assert 'import happens automatically' in ui
    assert 'st.query_params["ws"]' in ui
    assert 'hmac.compare_digest' in ui
    assert 'max_turns=turns' in ui
    assert 'budget_usd=budget' in ui