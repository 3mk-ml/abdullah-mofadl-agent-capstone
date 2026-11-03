"""Configuration smoke tests (do not claim a live HTTP deployment)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_railway_docker_start_command_is_stable():
    railway = json.loads((ROOT / 'railway.json').read_text())
    assert railway['build']['builder'] == 'DOCKERFILE'
    assert '--server.port=8501' in railway['deploy']['startCommand']
    assert railway['deploy']['healthcheckPath'] == '/_stcore/health'
    assert '--server.port=8501' in (ROOT / 'Procfile').read_text()
    assert 'EXPOSE 8501' in (ROOT / 'Dockerfile').read_text()


def test_demo_defaults_to_scripted_without_api_key():
    src = (ROOT / 'app.py').read_text()
    assert 'choices = ["Scripted demonstration", "OpenAI (live)"] if live_available else ["Scripted demonstration"]' in src
    assert 'hmac.compare_digest(password_input, live_access_password)' in src
    assert 'if not live_available or not os.environ.get("OPENAI_API_KEY")' in src