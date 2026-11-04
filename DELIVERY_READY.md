# DocPilot — submission and deployment checklist

## New interface

- Premium navigation and responsive Streamlit theme.
- Separate document workspaces for personal uploads and evaluation fixtures.
- Automatic indexing of selected PDF/TXT/Markdown files, with SHA-256 duplicate detection.
- Indexed-file list, page previews, keyword search and scoped document removal.
- Source-grounded Agent studio, example prompts, budget control and permission requests.
- Downloadable JSONL execution traces, saved reports and SQLite audit/cost views.
- Session URL continuity across page refreshes, with prominent bearer-link warning.

## Capstone submission artifacts

1. Repository: https://github.com/3mk-ml/abdullah-mofadl-agent-capstone
2. Demo: https://docpilot-production-7d0c.up.railway.app
3. Specification: `agent_spec.md`
4. Cost method: `cost_analysis.md`
5. Mandatory scripted traces: `traces/success_1.jsonl`, `traces/near_failure_recovery.jsonl`, `traces/explicit_failure.jsonl`

**Evidence limits:** The three traces remain explicitly marked as scripted integration fixtures. They are not live-model traces. Run live evaluations and calculate measured average cost before claiming the capstone is fully validated.

## Deployment and secret handling

- Railway service uses the root Dockerfile and port 8501 with `/_stcore/health`.
- `DOCPILOT_DB=/data/docpilot.sqlite3` on a persistent `/data` volume.
- Configure `OPENAI_API_KEY` and `DOCPILOT_LIVE_ACCESS_PASSWORD` as Railway variables.
- Do not store credentials or personal documents in the public GitHub repo.
- Replace the previously shared OpenAI API key because it was exposed in a conversation.
- Do not share URLs containing the `ws` workspace identifier.

## Quality gates

- Run `python -m pytest -q` and `python -m compileall -q app.py docpilot`.
- Confirm Railway deployment status is **SUCCESS**, not just BUILDING or DEPLOYING.
- Verify logs show a listener on `0.0.0.0:8501` and successful web requests.
- Test in the browser: index a sample file, search it, run scripted success and failure, and download a JSONL trace.
- Test a live OpenAI run only with permission and valid API credit; do not present simulations as real usage.