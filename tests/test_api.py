"""
Integration tests for Flask REST API endpoints
"""
import pytest
import json
from backend.app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert "version" in data


def test_fields_endpoint(client):
    res = client.get("/api/fields")
    assert res.status_code == 200
    data = res.get_json()
    assert "fields" in data
    assert len(data["fields"]) >= 5


def test_sensors_endpoint(client):
    res = client.get("/api/sensors/latest")
    assert res.status_code == 200
    data = res.get_json()
    assert "readings" in data


def test_model_metrics_endpoint(client):
    res = client.get("/api/model/metrics")
    assert res.status_code == 200
    data = res.get_json()
    assert data["model_loaded"] is True
    assert "metrics" in data


def test_yield_history_endpoint(client):
    res = client.get("/api/yields/history")
    assert res.status_code == 200
    data = res.get_json()
    assert "yields" in data
    assert len(data["yields"]) > 0


def test_storage_status_endpoint(client):
    res = client.get("/api/storage/status")
    assert res.status_code == 200
    data = res.get_json()
    assert "storage_status" in data
    assert "storage_summary" in data


def test_predictions_post_and_get(client):
    payload = {
        "field_id": "FIELD_001",
        "crop_type": "wheat",
        "season": "rabi",
        "area_ha": 6.5,
        "year": 2024,
        "demo_mode": True,
    }
    # POST prediction
    post_res = client.post("/api/predictions", json=payload)
    assert post_res.status_code == 201
    pred_data = post_res.get_json()
    assert pred_data["predicted_yield"] > 0
    assert pred_data["area_ha"] == 6.5

    # GET predictions list
    get_res = client.get("/api/predictions")
    assert get_res.status_code == 200
    list_data = get_res.get_json()
    assert len(list_data["predictions"]) > 0
