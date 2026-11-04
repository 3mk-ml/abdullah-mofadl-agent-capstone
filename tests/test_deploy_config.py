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


def test_delivery_ui_mentions_workspace_separation_and_live_lock():
    src = (ROOT / 'app.py').read_text()
    assert 'My documents' in src
    assert 'Guided evaluation demo' in src
    assert 'DOCPILOT_LIVE_ACCESS_PASSWORD' in src
    assert 'The two sources never mix.' in src