# Railway startup repair - November 4, 2026

## Confirmed cause (Railway deploy logs)

Railway reported a successful build and an application listening on
`0.0.0.0:8080`, while the Railway public domain forwarded requests to
port `8501`. The HTTP logs showed **502 connection refused**. This is a
verified upstream port mismatch, not a suspected package error.

## Changes made

- Add a Dockerfile using Python 3.12 and the repository's requirements.txt.
- Explicitly listen on 0.0.0.0:8501 in Dockerfile, railway.json and Procfile.
- Use Railway's Streamlit health endpoint `/_stcore/health`.
- Default to the free scripted demonstration. Paid OpenAI mode requires both
  `OPENAI_API_KEY` and the user-entered `DOCPILOT_LIVE_ACCESS_PASSWORD`.
- Use `include=["reasoning.encrypted_content"]` for a stateless multi-turn
  Responses API agent with `store=False`.
- Keep JSONL traces under the configured SQLite directory, persistent when
  DOCPILOT_DB=/data/docpilot.sqlite3 and /data is a Railway volume.

## Railway service configuration

- Project name: docpilot-week5-capstone
- Service: docpilot
- GitHub source: 3mk-ml/abdullah-mofadl-agent-capstone, main
- Environment variable: DOCPILOT_DB=/data/docpilot.sqlite3
- Persistent volume: mount at /data
- Public domain target port: 8501
- Secrets on Railway: `OPENAI_API_KEY` and `DOCPILOT_LIVE_ACCESS_PASSWORD`
  (neither is stored in GitHub). Keep access password to yourself.

After pushing these files, use Railway's Deployments view to see whether a
new Dockerfile build succeeds. Test:

https://docpilot-production-7d0c.up.railway.app/_stcore/health

A healthy Streamlit server normally returns HTTP 200 and `ok`.
If the page still fails, inspect **Deploy Logs** for startup/port errors,
**Build Logs** for pip failures, and make sure the Railway domain targets
port 8501. This patch was tested with local Python unit tests; the hosted
application must still be verified after deployment.