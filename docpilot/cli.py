"""Windows-friendly CLI. Run `python -m docpilot.cli --help`."""
from __future__ import annotations
import argparse
import json
import sys
import uuid
from pathlib import Path
from .agent import Agent, OpenAIBackend
from .fixtures import generate_fixture_traces, SAMPLE
from .storage import Storage

ROOT = Path(__file__).resolve().parents[1]


def ask_interactive(agent: Agent, question: str, owner: str, trace_name=None, budget=0.03, max_turns=8):
    state = agent.start(question, owner, trace_name=trace_name, budget_usd=budget, max_turns=max_turns)
    state = agent.advance(state)
    while state.status == "approval_required":
        pending = state.pending
        print("Human approval required:", pending["name"], pending.get("arguments", "")[:400])
        decision = input("Approve this tool call? [y/N]: ").strip().lower() == "y"
        state = agent.advance(state, approval=decision)
    print("Status:", state.status)
    print("Answer:", state.answer if state.status == "completed" else state.failure_reason)
    print("Turns:", state.turns, "Estimated API cost: $", round(state.cumulative_cost, 7))
    print("JSONL trace:", state.trace_path)
    return state


def main():
    parser = argparse.ArgumentParser(description="DocPilot AI - Week 5 capstone")
    parser.add_argument("command", choices=["seed", "ask", "fixture-traces", "status"])
    parser.add_argument("--session", default=None, help="Stable UUID session identifier; save to reuse memory")
    parser.add_argument("--question", default="What is the document deadline and what must I submit?")
    parser.add_argument("--file", default=None, help="Optional PDF/TXT/MD to upload into the specified session")
    parser.add_argument("--budget", type=float, default=0.03)
    parser.add_argument("--max-turns", type=int, default=8)
    parser.add_argument("--trace-name", default=None)
    args = parser.parse_args()
    store = Storage()
    owner = args.session or str(uuid.uuid4())
    if args.command == "fixture-traces":
        print(json.dumps(generate_fixture_traces(store.db_path, ROOT / "traces"), indent=2))
        return
    if args.command == "status":
        print(json.dumps({"session": owner, "documents": store.list_documents(owner),
                          "memories": store.list_memories(owner), "usage": store.usage_summary(owner)}, indent=2))
        return
    if args.command == "seed":
        for file in SAMPLE.iterdir():
            if file.suffix in (".txt", ".md"):
                doc = store.add_document(owner, file.name, file.read_bytes())
                print("Added:", doc["title"], doc["id"])
        print("SESSION ID (save for restart):", owner)
        return
    if args.file:
        file = Path(args.file)
        doc = store.add_document(owner, file.name, file.read_bytes())
        print("Added:", doc["title"], doc["id"])
    print("SESSION ID (save for restart):", owner)
    try:
        agent = Agent(store, OpenAIBackend())
    except (RuntimeError, Exception) as exc:
        print("OpenAI initialization failed:", str(exc)[:160], file=sys.stderr)
        sys.exit(2)
    ask_interactive(agent, args.question, owner, trace_name=args.trace_name,
                    budget=args.budget, max_turns=args.max_turns)


if __name__ == "__main__":
    main()