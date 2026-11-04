"""DocPilot AI — polished, evidence-first Streamlit capstone workspace.

All document searches and agent actions remain backed by the original MCP,
SQLite, budget, and approval controller. No external frontend services needed.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import re
import uuid
from pathlib import Path

import streamlit as st

from docpilot.agent import Agent, OpenAIBackend, ScriptedBackend
from docpilot.documents import DocumentTools
from docpilot.fixtures import make_scenarios, sample_session
from docpilot.storage import Storage

APP_ROOT = Path(__file__).resolve().parent
REPO_URL = "https://github.com/3mk-ml/abdullah-mofadl-agent-capstone"
NAVIGATION = ["Overview", "Documents", "Agent studio", "Memory & reports", "Audit & costs"]
SCENARIO_LABELS = {
    "success_1": "Successful research · grounded answer",
    "near_failure_recovery": "Recovery · broader search",
    "explicit_failure": "Explicit failure · repetition limit",
}
PROMPTS = [
    ("Executive summary", "Summarize my uploaded documents with key facts and citations."),
    ("Deadlines & dates", "Find important dates, explain which are deadlines, and cite the relevant pages."),
    ("Requirements", "List the important requirements and obligations in my uploaded documents, with evidence."),
]

st.set_page_config(
    page_title="DocPilot AI — Document Intelligence",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
:root{--ink:#111b31;--sub:#64748b;--line:#e5e9f2;--panel:#fff;--violet:#6554db;--teal:#0d998f}
html,body,[class*="css"]{font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.stApp{background:#f6f8fc;color:var(--ink)}
.main .block-container{max-width:1260px;padding:1.65rem 2.2rem 3.2rem}
[data-testid="stSidebar"]{background:linear-gradient(170deg,#101a35 0%,#111630 55%,#1c1a46 100%)}
[data-testid="stSidebar"] .block-container{padding-top:1.65rem}
[data-testid="stSidebar"] :is(p,small,label,span,h1,h2,h3,h4){color:#e2e8f4}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p{color:#b2bcd1!important}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){background:rgba(105,90,231,.24);border-radius:9px}
[data-testid="stSidebar"] [data-testid="stRadio"] label{padding:.24rem .4rem;border-radius:10px}
[data-testid="stSidebar"] [data-testid="stDivider"]{border-color:rgba(255,255,255,.13)}
[data-testid="stSidebar"] input{color:#151b30!important}
section[data-testid="stSidebar"] button{border-radius:11px}
[data-testid="stHeader"]{background:transparent}
h1,h2,h3{letter-spacing:-.035em;color:#111b31}
h2{font-weight:760!important}
p{line-height:1.5}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-radius:17px!important;border-color:#e6eaf3!important}
[data-testid="stMetric"]{background:white;padding:.85rem 1.1rem;border:1px solid #e4eaf3;border-radius:17px;box-shadow:0 5px 24px rgba(25,33,65,.035)}
[data-testid="stMetricLabel"] p{font-size:.84rem;font-weight:610;color:#64748b}
[data-testid="stMetricValue"]{font-weight:780;letter-spacing:-.035em;color:#151b39}
[data-testid="stFileUploader"]{border-radius:16px}
[data-testid="stFileUploaderDropzone"]{border:1.5px dashed #a4abdb;background:#f7f6ff;border-radius:17px;padding:1.3rem}
[data-testid="stDataFrame"]{border-radius:12px;overflow:hidden}
.stButton>button{border-radius:12px;font-weight:650;min-height:2.65rem;border-color:#dce2f0}
.stButton>button[kind="primary"]{background:#6152de;border-color:#6152de;box-shadow:0 7px 20px rgba(97,82,222,.21)}
.stButton>button[kind="primary"]:hover{background:#5141d5;border-color:#5141d5}
[data-testid="stDownloadButton"] button{border-radius:12px}
.stTabs [data-baseweb="tab-list"]{gap:.5rem}
.stTabs [data-baseweb="tab"]{border-radius:10px 10px 0 0;padding:.5rem 1.1rem}
[data-testid="stAlert"]{border-radius:13px}
.dp-brand{display:flex;align-items:center;gap:.7rem;margin:0 0 1.2rem;padding:.1rem 0 .6rem}
.dp-mark{display:flex;align-items:center;justify-content:center;width:43px;height:43px;background:linear-gradient(145deg,#8d7bff,#50b7ef);border-radius:14px;color:#fff;font-size:24px;font-weight:900;box-shadow:0 8px 22px rgba(85,100,244,.3)}
.dp-brand-name{font-size:1.28rem;letter-spacing:-.035em;color:#fff;font-weight:780;line-height:1.03}
.dp-brand-sub{color:#bbc6e1;font-size:.75rem;letter-spacing:.025em;margin-top:.18rem}
.dp-kicker{font-size:.72rem;color:#7a68ee;font-weight:800;text-transform:uppercase;letter-spacing:.14em;margin-bottom:.5rem}
.dp-title{font-size:clamp(1.7rem,3.0vw,2.45rem);font-weight:810;line-height:1.2;letter-spacing:-.048em;color:#141a35;margin:.1rem 0 .4rem}
.dp-lead{font-size:.99rem;color:#64748b;max-width:760px;line-height:1.65}
.dp-hero{background:radial-gradient(circle at 96% 10%,rgba(132,122,245,.36),transparent 35%),linear-gradient(122deg,#182348 0%,#252560 59%,#40358a 100%);color:white;border-radius:24px;padding:2.2rem 2.35rem;min-height:260px;position:relative;overflow:hidden;box-shadow:0 17px 40px rgba(32,35,91,.14)}
.dp-hero:after{content:"";position:absolute;right:-70px;top:40px;width:280px;height:280px;border:1px solid rgba(255,255,255,.17);border-radius:50%;box-shadow:0 0 0 35px rgba(255,255,255,.04),0 0 0 72px rgba(255,255,255,.035),0 0 0 106px rgba(255,255,255,.02);pointer-events:none}
.dp-hero .eyebrow{font-size:.72rem;letter-spacing:.15em;text-transform:uppercase;color:#c1bbff;font-weight:740}
.dp-hero h1{color:white!important;font-size:clamp(2rem,3.5vw,3rem);line-height:1.12;max-width:670px;margin:.65rem 0 .65rem;letter-spacing:-.05em}
.dp-hero p{color:#e0e5ff;max-width:650px;font-size:.99rem;margin-bottom:1.2rem}
.dp-chip{display:inline-flex;align-items:center;gap:.35rem;color:#e9f2ff;background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.17);padding:.38rem .7rem;border-radius:100px;font-size:.75rem;font-weight:640;margin-right:.35rem;margin-bottom:.25rem}
.dp-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#40d9b3;margin-right:.3rem;vertical-align:middle}
.dp-panel{background:white;border:1px solid #e7ebf5;border-radius:18px;padding:1.2rem 1.25rem;box-shadow:0 5px 22px rgba(23,32,70,.025)}
.dp-panel-title{font-size:1.02rem;font-weight:745;color:#17213e;letter-spacing:-.025em;margin-bottom:.35rem}
.dp-muted{color:#64748b;font-size:.9rem;line-height:1.58}
.dp-step{font-weight:750;color:#6554db;display:inline-flex;align-items:center;justify-content:center;width:31px;height:31px;border-radius:10px;background:#f0edff;margin-bottom:.7rem}
.dp-mini{font-size:.8rem;color:#67768e}
.dp-tag{display:inline-block;background:#f1f0ff;color:#6352cc;padding:.25rem .62rem;border-radius:50px;font-size:.78rem;font-weight:650;margin:0 .25rem .3rem 0}
.dp-status{display:inline-flex;align-items:center;border-radius:100px;background:#edfaf6;color:#0c7767;font-size:.78rem;font-weight:730;padding:.33rem .72rem}
.dp-soft{background:#f8f9fe;border:1px solid #e8ebf6;border-radius:16px;padding:1.1rem 1.3rem}
.dp-result{background:#fff;border:1px solid #dfebe7;border-left:4px solid #18ab94;border-radius:14px;padding:1.1rem;margin-top:.65rem}
.dp-section{margin-top:1.05rem;margin-bottom:.8rem}
.dp-divider{height:1px;background:#e7ebf3;margin:1.2rem 0}
@media(max-width:900px){.main .block-container{padding:1rem .8rem 2rem}.dp-hero{padding:1.5rem;min-height:225px}.dp-hero:after{opacity:.25}}
</style>
    """,
    unsafe_allow_html=True,
)


def safe(value: object) -> str:
    return html.escape(str(value), quote=True)


def valid_workspace_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value)) if str(uuid.UUID(value)) == value else None
    except (ValueError, AttributeError):
        return None


def sync_workspace() -> None:
    """Restore session after refresh via an unguessable URL token (demo, not auth)."""
    query = st.query_params.get("ws")
    ws = valid_workspace_id(query)
    if not ws:
        ws = str(uuid.uuid4())
        st.query_params["ws"] = ws
    if st.session_state.get("workspace_id") != ws:
        st.session_state.workspace_id = ws
        st.session_state.agent_state = None
        st.session_state.agent = None
        st.session_state.demo_id = None
    st.session_state.setdefault("navigation", NAVIGATION[0])
    requested = st.session_state.pop("_navigation_request", None)
    if requested in NAVIGATION:
        st.session_state.navigation = requested
    st.session_state.setdefault("task_prompt", PROMPTS[0][1])
    st.session_state.setdefault("live_unlocked", False)
    st.session_state.setdefault("last_run_scope", "My documents")


def goto(page: str) -> None:
    """Change the radio selection before its next widget render."""
    st.session_state._navigation_request = page
    st.rerun()


def dashboard_heading(label: str, title: str, description: str) -> None:
    st.markdown(
        f'<div class="dp-section"><div class="dp-kicker">{safe(label)}</div>'
        f'<div class="dp-title">{safe(title)}</div>'
        f'<div class="dp-lead">{safe(description)}</div></div>',
        unsafe_allow_html=True,
    )


def tool_owner() -> str:
    return st.session_state.workspace_id


def get_demo_owner(store: Storage) -> str:
    if not st.session_state.get("demo_id"):
        demo_id, _ = sample_session(store)
        st.session_state.demo_id = demo_id
    return st.session_state.demo_id


def metric_strip(store: Storage, owner: str) -> None:
    docs = store.list_documents(owner)
    usage = store.usage_summary(owner)
    stats = [
        ("Documents", f"{len(docs):02d}"),
        ("Indexed pages", f"{sum(x['page_count'] for x in docs):02d}"),
        ("Saved reports", f"{len(store.list_reports(owner)):02d}"),
        ("API cost", f"${usage['estimated_total_usd']:.4f}"),
    ]
    cols = st.columns(4, gap="small")
    for col, (label, value) in zip(cols, stats):
        with col:
            st.metric(label, value)


sync_workspace()
store = Storage()
tools = DocumentTools(store)
owner = tool_owner()
live_key_configured = bool(os.environ.get("OPENAI_API_KEY"))
live_password = os.environ.get("DOCPILOT_LIVE_ACCESS_PASSWORD", "")

# Navigation and access controls are in the sidebar on every page.
with st.sidebar:
    st.markdown(
        '<div class="dp-brand"><div class="dp-mark">D</div>'
        '<div><div class="dp-brand-name">DocPilot <span style="color:#99a8ff">AI</span></div>'
        '<div class="dp-brand-sub">DOCUMENT INTELLIGENCE</div></div></div>',
        unsafe_allow_html=True,
    )
    st.caption("WORKSPACE")
    st.radio("Navigation", NAVIGATION, label_visibility="collapsed", key="navigation")
    st.divider()
    st.markdown("**AI connection**")
    if not live_key_configured:
        st.info("Offline demonstration available. The server has no OpenAI key.")
    elif live_password:
        provided = st.text_input("Live access password", type="password", key="live_password_input")
        if provided:
            st.session_state.live_unlocked = hmac.compare_digest(provided, live_password)
        if st.session_state.live_unlocked:
            st.success("Live OpenAI access unlocked")
        else:
            st.caption("Enter the private demo password to enable paid AI runs.")
    else:
        st.success("Live OpenAI is configured")
    st.divider()
    st.markdown("**Session**")
    st.caption("Uploads are retained in SQLite for this workspace across page refreshes.")
    with st.expander("Workspace details"):
        st.code(owner)
        st.caption("This link contains a session identifier, not account authentication. Do not share it or upload confidential data.")
    if st.button("New workspace", use_container_width=True):
        st.query_params["ws"] = str(uuid.uuid4())
        st.rerun()
    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
    st.caption("LLM4Yemen · Track B / Week 5")
    st.caption("Single agent · MCP · SQLite · Cost limits")

nav = st.session_state.navigation
current_docs = store.list_documents(owner)

if nav == "Overview":
    st.markdown(
        '<div class="dp-hero"><div class="eyebrow">AI AGENT WORKSPACE · TRACK B CAPSTONE</div>'
        '<h1>Turn documents into decisions, with evidence.</h1>'
        '<p>Bring your source files, ask grounded questions, and inspect every step of the agent — '
        'from MCP tools and approval gates to token-level cost tracking.</p>'
        '<span class="dp-chip"><span class="dp-dot"></span> Custom MCP server</span>'
        '<span class="dp-chip">SQLite memory</span>'
        '<span class="dp-chip">Auditable agent loop</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div style="height:.9rem"></div>', unsafe_allow_html=True)
    metric_strip(store, owner)
    st.markdown('<div style="height:.9rem"></div>', unsafe_allow_html=True)
    a, b = st.columns([1.0, .88], gap="large")
    with a:
        st.markdown('<div class="dp-panel"><div class="dp-kicker">GET STARTED</div>'
                    '<div class="dp-panel-title">Your research workspace</div>'
                    '<div class="dp-muted">Add files once, verify extracted text, then ask the agent to '
                    'find answers with page-level evidence.</div></div>', unsafe_allow_html=True)
        st.markdown('<div style="height:.65rem"></div>', unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        if b1.button("Add documents", type="primary", use_container_width=True):
            goto("Documents")
        if b2.button("Open agent studio", use_container_width=True):
            goto("Agent studio")
        st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
        if current_docs:
            st.markdown("#### Recently indexed")
            for d in current_docs[:4]:
                st.markdown(f"**📄 {safe(d['title'])}** · {d['page_count']} page(s)")
        else:
            st.info("No documents in your workspace yet. Upload TXT, Markdown, or text-based PDF to get started.")
    with b:
        st.markdown('<div class="dp-panel"><div class="dp-kicker">CAPSTONE ARCHITECTURE</div>'
                    '<div class="dp-panel-title">One transparent agent, four safeguards</div>'
                    '<div class="dp-muted">Tool calls are routed through a real JSON-RPC MCP server. '
                    'SQLite keeps your files and memories, while guardrails cap cost and require approval for writes.</div>'
                    '<div class="dp-divider"></div>'
                    '<span class="dp-tag">01 · OpenAI tool calling</span>'
                    '<span class="dp-tag">02 · MCP read tools</span>'
                    '<span class="dp-tag">03 · Permission gates</span>'
                    '<span class="dp-tag">04 · JSONL tracing</span></div>', unsafe_allow_html=True)
        st.markdown('<div style="height:.65rem"></div>', unsafe_allow_html=True)
        st.markdown('<div class="dp-soft"><div class="dp-panel-title">Submission evidence</div>'
                    '<div class="dp-muted">Agent specification · cost analysis · three clearly labeled '
                    'execution traces · public GitHub repository.</div></div>', unsafe_allow_html=True)
        st.link_button("View source on GitHub", REPO_URL, use_container_width=True)
    st.markdown("#### How it works")
    steps = st.columns(3, gap="medium")
    for col, num, title, desc in zip(
        steps,
        ("01", "02", "03"),
        ("Index your files", "Ask the agent", "Inspect the evidence"),
        ("Auto-import and inspect searchable pages.",
         "Run live OpenAI with a budget or a scripted demonstration.",
         "Review sources, tool calls, approvals, and cost estimates."),
    ):
        with col:
            st.markdown(f'<div class="dp-panel"><div class="dp-step">{num}</div>'
                        f'<div class="dp-panel-title">{title}</div>'
                        f'<div class="dp-muted">{desc}</div></div>', unsafe_allow_html=True)

elif nav == "Documents":
    dashboard_heading("Knowledge library", "Your documents, ready for analysis",
                      "Files are indexed as soon as you select them. Preview extracted pages and test search before running the agent.")
    st.markdown('<span class="dp-status"><span class="dp-dot"></span> Session-scoped workspace</span>', unsafe_allow_html=True)
    st.markdown('<div style="height:.85rem"></div>', unsafe_allow_html=True)
    upload_col, view_col = st.columns([.95, 1.15], gap="large")
    with upload_col:
        st.markdown("#### Upload & index")
        st.caption("Supported: PDF (text-based), TXT, and MD · Up to 8 MB per file · PDFs up to 60 pages")
        uploads = st.file_uploader(
            "Select source files — import happens automatically",
            type=["pdf", "txt", "md"],
            accept_multiple_files=True,
            key=f"upload_{owner}",
            help="Text extraction runs after selection. Scanned PDFs need OCR and are not supported in this version.",
        )
        if uploads:
            existing_hashes = {d.get("sha256") for d in current_docs}
            successes, skips, errors = [], [], []
            for f in uploads:
                payload = f.getvalue()
                digest = hashlib.sha256(payload).hexdigest()
                if digest in existing_hashes:
                    skips.append(f.name)
                    continue
                try:
                    doc = store.add_document(owner, f.name, payload)
                    existing_hashes.add(doc["sha256"])
                    successes.append(doc["title"])
                except (ValueError, UnicodeError, ImportError) as exc:
                    errors.append(f"{f.name}: {exc}")
            if successes:
                st.success(f"Indexed {len(successes)} new file(s): {', '.join(successes[:3])}")
            elif skips and not errors:
                st.caption("All selected files are already indexed. You can ask a question about them now.")
            for err in errors:
                st.error(err)
            current_docs = store.list_documents(owner)
        st.markdown("#### Try the sample collection")
        st.caption("A synthetic policy, an agreement, and an injection-test document. These can be added to your own workspace.")
        if st.button("Add three sample files", use_container_width=True):
            existing_hashes = {d.get("sha256") for d in current_docs}
            count = 0
            for path in sorted((APP_ROOT / "sample_docs").iterdir()):
                if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() not in existing_hashes:
                    info = store.add_document(owner, path.name, path.read_bytes())
                    existing_hashes.add(info["sha256"])
                    count += 1
            st.toast(f"{count} example files indexed", icon="✅")
            st.rerun()
        st.info("Security note: this public capstone demo has session-scoped storage, not account login. Avoid uploading confidential documents.")

    with view_col:
        st.markdown("#### Indexed library")
        if not current_docs:
            st.markdown('<div class="dp-soft"><div class="dp-panel-title">No files indexed yet</div>'
                        '<div class="dp-muted">Upload a file on the left. It will appear here immediately '
                        'with a page count and searchable text.</div></div>', unsafe_allow_html=True)
        else:
            st.dataframe(
                [{"File": d["title"], "Pages": d["page_count"], "Format": d["kind"].upper(),
                  "Imported": d["created_at"][:16].replace("T", " ")} for d in current_docs],
                use_container_width=True, hide_index=True,
            )
            selected_id = st.selectbox(
                "Preview file",
                [d["id"] for d in current_docs],
                format_func=lambda i: next((d["title"] for d in current_docs if d["id"] == i), i),
            )
            selected = next(d for d in current_docs if d["id"] == selected_id)
            page = st.number_input("Page", min_value=1, max_value=max(selected["page_count"], 1), value=1, step=1)
            result = tools.read_document(owner, selected_id, page)
            if result.get("error"):
                st.error(result["error"])
            else:
                st.text_area("Extracted text preview", result.get("text", ""), height=220,
                             help="The agent will access the same indexed text through MCP.")
                st.caption(f"Citation reference: `{result['reference']}`")
            with st.popover("Remove selected document"):
                st.warning("This permanently deletes the file and its indexed pages from this workspace.")
                if st.button("Confirm removal", key="confirm_remove"):
                    if store.delete_document(owner, selected_id):
                        st.toast("Document removed", icon="✅")
                    st.rerun()

    st.markdown('<div class="dp-divider"></div>', unsafe_allow_html=True)
    st.markdown("#### Search your documents")
    search_q = st.text_input("Search indexed pages", placeholder="Try: deadline, supplier, delivery, payment...")
    if search_q.strip():
        found = tools.search_documents(owner, search_q, 5)
        if found.get("matches"):
            st.caption(f"Showing {len(found['matches'])} of {found['total_matches']} matching page(s)")
            for hit in found["matches"]:
                with st.expander(f"{hit['title']} · Page {hit['page']} · Score {hit['relevance']}"):
                    st.write(hit["excerpt"])
                    st.code(hit["reference"])
        else:
            st.info(found.get("error") or "No keyword matches. Try a shorter or more specific term.")
    elif current_docs:
        st.caption("Search uses lightweight keyword matching. For a synthesized answer, go to Agent studio.")

elif nav == "Agent studio":
    dashboard_heading("Agent workspace", "Ask questions. Verify every answer.",
                      "Choose between your imported documents and a deterministic evaluation scenario. The two sources never mix.")
    metric_strip(store, owner)
    st.markdown('<div style="height:1.1rem"></div>', unsafe_allow_html=True)
    source = st.segmented_control("Source", ["My documents", "Guided evaluation demo"],
                                   default="My documents", key="agent_source")
    is_demo = source == "Guided evaluation demo"
    if is_demo:
        demo_owner = get_demo_owner(store)
        demo_docs = store.list_documents(demo_owner)
        st.info("**Evaluation mode:** The three scripted scenarios use synthetic sample files, not your uploads. No OpenAI credits are used.")
        st.markdown("".join(f'<span class="dp-tag">{safe(d["title"])}</span>' for d in demo_docs), unsafe_allow_html=True)
        scenario = st.selectbox("Scenario", list(SCENARIO_LABELS), format_func=lambda n: SCENARIO_LABELS[n])
        docs_map = {d["title"]: d for d in demo_docs}
        spec = make_scenarios(docs_map)[scenario]
        st.text_area("Scenario task", spec["question"], height=90, disabled=True)
    else:
        scenario = None
        if current_docs:
            st.success(f"Ready to analyze **{len(current_docs)} indexed document(s)** in your workspace.")
            with st.expander("Show files available to the agent"):
                for d in current_docs:
                    st.markdown(f"• {safe(d['title'])} · {d['page_count']} page(s)")
        else:
            st.warning("Your workspace has no indexed documents yet. Add documents in the Documents page first.")
        st.markdown("#### Start with a task")
        prompt_cols = st.columns(3)
        for col, (label, prompt) in zip(prompt_cols, PROMPTS):
            if col.button(label, use_container_width=True, key=f"prompt_{label}"):
                st.session_state.task_prompt = prompt
        st.text_area("What would you like DocPilot to find?", key="task_prompt", height=120,
                     placeholder="e.g. What is the delivery date, and where is it stated?")
        if live_key_configured and live_password and not st.session_state.live_unlocked:
            st.warning("Live model access is locked. Enter the access password in the left sidebar to run tasks on your documents.")
        elif not live_key_configured:
            st.warning("Live OpenAI is not configured on this deployment. You can explore the guided evaluation demo instead.")

    with st.expander("Execution controls · budget and permissions"):
        ctrl1, ctrl2, ctrl3 = st.columns(3)
        budget = ctrl1.number_input("Max. spend (USD)", min_value=.001, max_value=1.0, value=.03,
                                    step=.005, format="%.3f")
        turns = ctrl2.slider("Turn limit", 1, 20, 8)
        policy = ctrl3.selectbox("Write permission", ["ask_on_write", "always_ask", "auto"], index=0)
        st.caption("All runs require an explicit final_answer and stop at the configured budget / turn limits.")

    allow_run = is_demo or (bool(current_docs) and live_key_configured and
                           (not live_password or st.session_state.live_unlocked))
    if st.button("Run DocPilot agent", type="primary", use_container_width=True, disabled=not allow_run):
        try:
            if is_demo:
                run_owner = demo_owner
                backend = ScriptedBackend(spec["steps"])
                task = spec["question"]
            else:
                run_owner = owner
                backend = OpenAIBackend()
                task = st.session_state.task_prompt
            agent = Agent(store, backend)
            state = agent.advance(agent.start(task, run_owner,
                                             max_turns=turns, budget_usd=budget,
                                             permission_policy=policy))
            st.session_state.agent, st.session_state.agent_state = agent, state
            st.session_state.last_run_scope = "Guided evaluation demo" if is_demo else "My documents"
        except Exception as exc:
            st.error(f"Agent could not start: {type(exc).__name__}: {exc}")

    state = st.session_state.get("agent_state")
    if state is not None:
        st.markdown('<div class="dp-divider"></div>', unsafe_allow_html=True)
        st.markdown("#### Latest execution")
        st.caption(f"Source: {st.session_state.last_run_scope} · Backend: {state.backend} · Run: {state.run_id[:8]}")
        columns = st.columns(4)
        for col, label, value in zip(columns,
                                     ("Status", "Model turns", "Tool calls", "Estimated cost"),
                                     (state.status.replace("_", " ").title(),
                                      f"{state.turns}/{state.max_turns}",
                                      str(len(state.executed_tools)),
                                      f"${state.cumulative_cost:.6f}")):
            with col:
                st.metric(label, value)
        if state.status == "approval_required":
            st.warning(f"The agent requested permission to use **{state.pending['name']}**.")
            try:
                st.json(json.loads(state.pending.get("arguments", "{}")))
            except ValueError:
                st.code(state.pending.get("arguments", ""))
            yes, no = st.columns(2)
            if yes.button("Approve this action", type="primary", use_container_width=True):
                st.session_state.agent_state = st.session_state.agent.advance(state, approval=True)
                st.rerun()
            if no.button("Reject action", use_container_width=True):
                st.session_state.agent_state = st.session_state.agent.advance(state, approval=False)
                st.rerun()
        elif state.status == "completed":
            st.success("Task complete — final answer returned")
            with st.container(border=True):
                st.markdown(state.answer)
            if state.source_refs:
                st.caption("Referenced pages: " + " · ".join(f"`{r}`" for r in sorted(state.source_refs)))
        elif state.status == "failed":
            st.error(f"Explicit failure: {state.failure_reason}")
            st.caption("Failure traces are valuable evidence. Review the reason rather than concealing it.")
        a, b = st.columns([1.15, .85], gap="large")
        with a, st.expander("Tools executed and evidence references"):
            st.write(state.executed_tools or ["No tools executed"])
            st.write(sorted(state.source_refs) or ["No evidence references collected"])
        with b:
            if state.trace_path.exists():
                st.download_button("Download execution trace (.jsonl)",
                                   data=state.trace_path.read_bytes(),
                                   file_name=state.trace_path.name,
                                   mime="application/x-ndjson", use_container_width=True)
                st.caption("Traces are retained on the mounted SQLite storage volume.")

elif nav == "Memory & reports":
    dashboard_heading("Persistent knowledge", "Memory and saved reports",
                      "Only approved writes are persisted. Your personal workspace and synthetic demo remain separate.")
    view_scope = st.segmented_control("View", ["My documents", "Guided evaluation demo"],
                                       default="My documents", key="memory_scope")
    active = owner if view_scope == "My documents" else get_demo_owner(store)
    memories, reports = store.list_memories(active), store.list_reports(active)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Memory entries")
        if memories:
            st.dataframe([{"Key": m["key"], "Value": m["value"], "Updated": m["updated_at"]}
                          for m in memories], hide_index=True, use_container_width=True)
        else:
            st.info("No saved memories yet. A live agent can request permission to save one.")
    with c2:
        st.markdown("#### Saved reports")
        if reports:
            st.dataframe([{"Title": r["title"], "Saved": r["created_at"]}
                          for r in reports], hide_index=True, use_container_width=True)
        else:
            st.info("No saved reports yet. Approved reports appear here.")
    if reports:
        st.markdown("#### Report library")
        for report in reports:
            with st.expander(report["title"]):
                st.markdown(report["body"])
                st.download_button("Export Markdown", data=report["body"].encode("utf-8"),
                                   file_name="docpilot_report_" + report["id"][:8] + ".md",
                                   mime="text/markdown", key=report["id"])

elif nav == "Audit & costs":
    dashboard_heading("Operational transparency", "Run audit and cost tracking",
                      "Inspect tool activity and recorded token consumption. Scripted traces do not incur model costs.")
    view_scope = st.segmented_control("View", ["My documents", "Guided evaluation demo"],
                                       default="My documents", key="audit_scope")
    active = owner if view_scope == "My documents" else get_demo_owner(store)
    usage = store.usage_summary(active)
    cols = st.columns(4)
    for col, label, val in zip(cols, ("Live runs", "Input tokens", "Output tokens", "Estimated cost"),
                               (str(usage["runs"]), str(usage["input_tokens"]),
                                str(usage["output_tokens"]), f"${usage['estimated_total_usd']:.6f}")):
        with col:
            st.metric(label, val)
    st.markdown("#### Audit events")
    events = store.audits(active, limit=200)
    if events:
        st.dataframe([{"Time": a["occurred_at"], "Event": a["action"],
                      "Tool": a["tool"], "Outcome": a["outcome"], "Details": a["detail"]}
                      for a in events], use_container_width=True, hide_index=True)
    else:
        st.info("Audit events appear here after an agent run.")
    st.markdown("#### Capstone demonstration evidence")
    st.markdown("The repository contains `success_1.jsonl`, `near_failure_recovery.jsonl`, and "
                "`explicit_failure.jsonl`. These are **labeled scripted integration traces**, not live LLM evaluations.")
    st.link_button("Inspect traces on GitHub", REPO_URL + "/tree/main/traces")

st.markdown('<div style="height:1rem"></div><div class="dp-mini">'
            'DocPilot AI · One auditable agent · Custom MCP tools · Persistent SQLite · Human-approved writes'
            '</div>', unsafe_allow_html=True)