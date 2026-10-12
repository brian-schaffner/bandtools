"""Integration tests for the web API."""

import pytest
from fastapi.testclient import TestClient

from src.web_ui.app import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestFactoryPresetsAPI:
    """Tests for factory presets API."""

    def test_list_factory_presets(self, client):
        response = client.get("/api/factory-presets")
        assert response.status_code == 200
        data = response.json()
        assert "presets" in data
        assert len(data["presets"]) == 8

    def test_get_factory_preset_details(self, client):
        response = client.get("/api/factory-presets/THRILLENGANES")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "THRILLENGANES"
        assert "primary" in data
        assert "voice" in data

    def test_get_nonexistent_factory_preset(self, client):
        response = client.get("/api/factory-presets/NONEXISTENT")
        assert response.status_code == 404


class TestPresetCRUD:
    """Tests for preset CRUD operations."""

    def test_create_mxr_preset(self, client):
        response = client.post(
            "/api/presets/mxr",
            json={
                "name": "Test Preset",
                "mix": 0.7,
                "cutoff": 0.5,
                "resonance": 0.3,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["preset"]["name"] == "Test Preset"

    def test_create_from_factory(self, client):
        response = client.post("/api/presets/mxr/factory/SLEDGE")
        assert response.status_code == 200
        data = response.json()
        assert data["preset"]["name"] == "SLEDGE"

    def test_list_presets(self, client):
        client.post("/api/presets/mxr/factory/SLEDGE")

        response = client.get("/api/presets")
        assert response.status_code == 200
        data = response.json()
        assert "presets" in data

    def test_get_preset(self, client):
        create_response = client.post("/api/presets/mxr/factory/SLEDGE")
        preset_id = create_response.json()["id"]

        response = client.get(f"/api/presets/{preset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == preset_id

    def test_delete_preset(self, client):
        create_response = client.post("/api/presets/mxr/factory/SLEDGE")
        preset_id = create_response.json()["id"]

        response = client.delete(f"/api/presets/{preset_id}")
        assert response.status_code == 200

        response = client.get(f"/api/presets/{preset_id}")
        assert response.status_code == 404


class TestTranslation:
    """Tests for translation API."""

    def test_translate_preset(self, client):
        create_response = client.post("/api/presets/mxr/factory/SLEDGE")
        mxr_id = create_response.json()["id"]

        response = client.post(f"/api/translate/{mxr_id}")
        assert response.status_code == 200
        data = response.json()
        assert "axioma_preset" in data
        assert "translation_id" in data
        assert data["axioma_preset"]["device"] == "DARKGLASS_AXIOMA"

    def test_translate_nonexistent_preset(self, client):
        response = client.post("/api/translate/nonexistent-id")
        assert response.status_code == 404


class TestExport:
    """Tests for export API."""

    def test_export_configuration_guide(self, client):
        create_response = client.post("/api/presets/mxr/factory/SLEDGE")
        mxr_id = create_response.json()["id"]

        translate_response = client.post(f"/api/translate/{mxr_id}")
        axioma_id = translate_response.json()["axioma_preset"]["id"]

        response = client.get(f"/api/export/{axioma_id}/guide")
        assert response.status_code == 200
        data = response.json()
        assert "guide" in data
        assert "Axioma Preset Configuration" in data["guide"]
