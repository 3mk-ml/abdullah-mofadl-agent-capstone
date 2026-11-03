"""Offline integration fixtures. Simulated model decisions, real MCP/SQLite operations."""
from __future__ import annotations
import uuid
from pathlib import Path
from .agent import Agent, ScriptedBackend
from .storage import Storage

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample_docs"


def sample_session(store: Storage) -> tuple[str, dict]:
    owner = str(uuid.uuid4())
    documents = {}
    for filename in ("project_submission_policy.txt", "supplier_agreement.md", "untrusted_invoice.txt"):
        documents[filename] = store.add_document(owner, filename, (SAMPLE / filename).read_bytes())
    return owner, documents


def make_scenarios(docs: dict) -> dict[str, dict]:
    policy = docs["project_submission_policy.txt"]["id"]
    supplier = docs["supplier_agreement.md"]["id"]
    ref_policy = f"{policy}:p1"
    ref_supplier = f"{supplier}:p1"
    return {
        "success_1": {
            "question": "What is the deadline and what deliverables are required in the lab policy?",
            "steps": [
                {"calls": [{"name": "list_documents", "args": {}}]},
                {"calls": [{"name": "search_documents", "args": {"query": "deadline deliverables", "limit": 4}}]},
                {"calls": [{"name": "find_dates", "args": {"document_id": policy}}]},
                {"calls": [{"name": "final_answer", "args": {
                    "answer": "The synthetic policy lists November 1, 2026 at 11:59 PM Yemen time. It requires a source-code link, live demo, specification, cost analysis and traces, including an explicit failure.",
                    "citations": [ref_policy]}}]}
            ]
        },
        "near_failure_recovery": {
            "question": "When must the supplier deliver sensors and when is payment due?",
            "steps": [
                {"calls": [{"name": "search_documents", "args": {"query": "ultracentrifuge subroutine", "limit": 2}}]},
                {"calls": [{"name": "search_documents", "args": {"query": "delivery payment supplier", "limit": 4}}]},
                {"calls": [{"name": "read_document", "args": {"document_id": supplier, "page": 1}}]},
                {"calls": [{"name": "final_answer", "args": {
                    "answer": "Delivery is due December 15, 2026. Payment is within 14 days after confirmed delivery and a passing inspection, not a fixed date. The first search found nothing; a broader query recovered.",
                    "citations": [ref_supplier]}}]}
            ]
        },
        "explicit_failure": {
            "question": "Find an undocumented keyword that does not occur in any file, without inventing an answer.",
            "steps": [
                {"calls": [{"name": "search_documents", "args": {"query": "zxqv_unfindable_keyword", "limit": 2}}]},
                {"calls": [{"name": "search_documents", "args": {"query": "zxqv_unfindable_keyword", "limit": 2}}]},
                {"calls": [{"name": "search_documents", "args": {"query": "zxqv_unfindable_keyword", "limit": 2}}]}
            ]
        }
    }


def generate_fixture_traces(db_path: str, out_dir: str | Path) -> dict:
    store = Storage(db_path)
    owner, docs = sample_session(store)
    output = {}
    for name, scenario in make_scenarios(docs).items():
        agent = Agent(store, ScriptedBackend(scenario["steps"]))
        state = agent.start(scenario["question"], owner, trace_name=f"{name}.jsonl", trace_dir=out_dir)
        state = agent.advance(state)
        output[name] = {"status": state.status, "failure_reason": state.failure_reason,
                        "turns": state.turns, "trace": str(state.trace_path), "backend": state.backend}
    return output