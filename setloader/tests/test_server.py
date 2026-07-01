import base64
import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def server_fixture(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")
    monkeypatch.delenv("EMAIL_FALLBACK_TO", raising=False)

    import server as server_module

    server_module = importlib.reload(server_module)

    uploads = tmp_path / "uploads"
    work = tmp_path / "work"
    pack = tmp_path / "pack"
    for path in (uploads, work, pack):
        path.mkdir(parents=True, exist_ok=True)

    run_sh = tmp_path / "run.sh"
    run_sh.write_text("#!/usr/bin/env bash\n")

    monkeypatch.setattr(server_module, "ROOT", tmp_path)
    monkeypatch.setattr(server_module, "UPLOADS", uploads)
    monkeypatch.setattr(server_module, "WORK", work)
    monkeypatch.setattr(server_module, "PACK", pack)
    monkeypatch.setattr(server_module, "RUN_SH", run_sh)

    client = TestClient(server_module.app)
    return client, server_module
DATA_PATH = Path(__file__).parent / "data" / "sample.pdf"


def _pdf_bytes() -> bytes:
    return DATA_PATH.read_bytes()


def test_run_requires_secret(server_fixture):
    client, _ = server_fixture
    response = client.post("/run")
    assert response.status_code == 401


def test_run_rejects_missing_file(server_fixture):
    client, server_module = server_fixture
    headers = {"X-Secret": server_module.SECRET}
    response = client.post("/run", headers=headers, json={"name": "NoFile"})
    assert response.status_code == 422


def test_run_success(server_fixture, monkeypatch):
    client, server_module = server_fixture

    artifact = server_module.PACK / "test_set.sbp"
    artifact.write_text("dummy")

    class DummyProc:
        returncode = 0
        stdout = f"ARTIFACT={artifact}\n"
        stderr = ""

    monkeypatch.setattr(server_module.subprocess, "run", lambda *a, **k: DummyProc())
    monkeypatch.setattr(server_module, "send_email_with_attachment", lambda *a, **k: None)

    files = {"file": ("set.pdf", _pdf_bytes(), "application/pdf")}
    headers = {"X-Secret": server_module.SECRET}
    response = client.post("/run", headers=headers, files=files)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert Path(body["artifact"]) == artifact


def test_run_reports_missing_artifact(server_fixture, monkeypatch):
    client, server_module = server_fixture

    class DummyProc:
        returncode = 0
        stdout = "ARTIFACT=/non/existent/path.sbp\n"
        stderr = ""

    monkeypatch.setattr(server_module.subprocess, "run", lambda *a, **k: DummyProc())

    files = {"file": ("set.pdf", _pdf_bytes(), "application/pdf")}
    headers = {"X-Secret": server_module.SECRET}
    response = client.post("/run", headers=headers, files=files)
    assert response.status_code == 500
    body = response.json()
    assert body["ok"] is False
    assert "artifact not found" in body["error"]


def test_run_accepts_base64_json(server_fixture, monkeypatch):
    client, server_module = server_fixture

    artifact = server_module.PACK / "json_set.sbp"
    artifact.write_text("dummy")

    class DummyProc:
        returncode = 0
        stdout = f"ARTIFACT={artifact}\n"
        stderr = ""

    monkeypatch.setattr(server_module.subprocess, "run", lambda *a, **k: DummyProc())
    monkeypatch.setattr(server_module, "send_email_with_attachment", lambda *a, **k: None)

    payload = {
        "name": "Json Set",
        "file_b64": base64.b64encode(_pdf_bytes()).decode(),
    }
    headers = {"X-Secret": server_module.SECRET, "Content-Type": "application/json"}
    response = client.post("/run", headers=headers, json=payload)
    assert response.status_code == 200
    assert response.json()["ok"] is True
