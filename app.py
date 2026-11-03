"""DocPilot interactive Streamlit demonstration."""
from __future__ import annotations
import json
import os
import uuid
from pathlib import Path
import streamlit as st

from docpilot.agent import Agent, OpenAIBackend, ScriptedBackend
from docpilot.storage import Storage
from docpilot.fixtures import make_scenarios, sample_session

st.set_page_config(page_title="DocPilot AI | MCP Capstone", page_icon="📄", layout="wide")
st.markdown("""<style>
.main .block-container{max-width:1120px;padding-top:2rem}
h1,h2,h3{letter-spacing:-.025em}
[data-testid="stMetricValue"]{font-weight:650}
</style>""", unsafe_allow_html=True)
st.title("📄 DocPilot AI")
st.caption("Week 5 capstone · One autonomous agent · Model Context Protocol · SQLite memory · Human-approved writes")

store = Storage()
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "agent_state" not in st.session_state:
    st.session_state.agent_state = None
if "agent" not in st.session_state:
    st.session_state.agent = None

with st.sidebar:
    st.header("Run settings")
    mode = st.radio("Model backend", ["OpenAI (live)", "Scripted demonstration"], index=0,
                    help="Scripted tests do not call any LLM and are not evidence of live model quality.")
    budget = st.number_input("Maximum USD per task", min_value=0.001, max_value=1.0, value=0.03, step=0.005, format="%.3f")
    turns = st.slider("Maximum model turns", 1, 20, 8)
    policy = st.selectbox("Permission policy", ["ask_on_write", "always_ask", "auto"], index=0,
                          help="auto automatically authorizes all tools; use ask_on_write for real work.")
    st.divider()
    st.caption("Documents, reports, and memories are scoped to this browser's random session UUID. This demo is not an authenticated multi-user document vault.")
    st.code(st.session_state.session_id)
    if st.button("Start fresh session"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.agent_state = None
        st.session_state.agent = None
        st.rerun()

upload_tab, chat_tab, memory_tab, logs_tab = st.tabs(["Documents", "Run the agent", "Persistent memory & reports", "Audit & cost"])
with upload_tab:
    st.subheader("Add source documents")
    uploads = st.file_uploader("Upload text-based PDF, TXT or Markdown (up to 8 MB each)",
                               type=["pdf", "txt", "md"], accept_multiple_files=True)
    if st.button("Import selected documents", disabled=not uploads):
        for item in uploads or []:
            try:
                result = store.add_document(st.session_state.session_id, item.name, item.getvalue())
                st.success(f"Imported {result['title']} · {result['page_count']} page(s)")
            except Exception as exc:
                st.error(f"{item.name}: {exc}")
    docs = store.list_documents(st.session_state.session_id)
    if docs:
        st.dataframe([{"title": d["title"], "pages": d["page_count"], "document_id": d["id"]} for d in docs], use_container_width=True)
    else:
        st.info("No documents yet. You can upload your own or use the scripted sample scenario.")
    st.caption("Scanned PDFs without extractable text are rejected; OCR is not included.")

with chat_tab:
    st.subheader("Evidence-grounded document agent")
    scenario = None
    if mode == "Scripted demonstration":
        st.info("Offline infrastructure demonstration. Model decisions are predetermined; MCP calls, SQLite and controller rules are real.")
        scenario = st.selectbox("Fixture", ["success_1", "near_failure_recovery", "explicit_failure"])
    question = st.text_area("Task", value="What are the deadlines and the submission requirements?", height=95,
                            disabled=mode == "Scripted demonstration")
    if st.button("Run agent", type="primary"):
        try:
            if mode == "Scripted demonstration":
                owner, docs = sample_session(store)
                st.session_state.session_id = owner
                spec = make_scenarios(docs)[scenario]
                backend = ScriptedBackend(spec["steps"])
                actual_question = spec["question"]
            else:
                if not os.environ.get("OPENAI_API_KEY"):
                    raise ValueError("OPENAI_API_KEY is not configured on the server. Use Scripted demonstration until configured.")
                backend = OpenAIBackend()
                actual_question = question
            agent = Agent(store, backend)
            state = agent.start(actual_question, st.session_state.session_id,
                                max_turns=turns, budget_usd=budget, permission_policy=policy)
            state = agent.advance(state)
            st.session_state.agent = agent
            st.session_state.agent_state = state
        except Exception as exc:
            st.error(f"Could not run: {type(exc).__name__}: {exc}")
    state = st.session_state.agent_state
    if state is not None:
        c1, c2, c3 = st.columns(3)
        c1.metric("Status", state.status)
        c2.metric("Model turns", f"{state.turns}/{state.max_turns}")
        c3.metric("Estimated API cost", f"${state.cumulative_cost:.6f}")
        if state.status == "approval_required":
            st.warning(f"Approval required for {state.pending['name']}")
            st.code(state.pending.get("arguments", ""), language="json")
            left, right = st.columns(2)
            if left.button("Approve action"):
                st.session_state.agent_state = st.session_state.agent.advance(state, approval=True)
                st.rerun()
            if right.button("Deny action"):
                st.session_state.agent_state = st.session_state.agent.advance(state, approval=False)
                st.rerun()
        elif state.status == "completed":
            st.success("Agent completed the task")
            st.markdown(state.answer)
        elif state.status == "failed":
            st.error(f"Explicit failure: {state.failure_reason}")
        if state.trace_path.exists():
            st.download_button("Download JSONL execution trace", data=state.trace_path.read_bytes(),
                               file_name=state.trace_path.name, mime="application/x-ndjson")
        with st.expander("Executed tools & source refs"):
            st.write(state.executed_tools)
            st.write(sorted(state.source_refs))

with memory_tab:
    st.subheader("Memory after restart")
    st.caption("SQLite retains approved memories when storage is persistent. Enter the same session UUID after restarting the CLI to retrieve them.")
    st.write("Saved memories")
    st.dataframe(store.list_memories(st.session_state.session_id), use_container_width=True)
    st.write("Saved reports")
    reports = store.list_reports(st.session_state.session_id)
    st.dataframe([{"title": r["title"], "created_at": r["created_at"]} for r in reports], use_container_width=True)
    for report in reports:
        with st.expander(report["title"]):
            st.markdown(report["body"])

with logs_tab:
    st.subheader("Cost accounting")
    usage = store.usage_summary(st.session_state.session_id)
    st.json(usage)
    st.caption("Scripted traces have zero tokens and cost; actual measured model use appears only for live OpenAI calls.")
    st.subheader("Audit trail")
    st.dataframe(store.audits(st.session_state.session_id, limit=100), use_container_width=True)