from datetime import UTC, datetime

from ice_gateway.constants import ReadQuality
from ice_gateway.database import PiHealthRow, SensorReadingRow


def test_overview_returns_200(app_client):
    response = app_client.get("/")
    assert response.status_code == 200
    assert "Ice Gateway" in response.text


def test_api_temperatures_returns_200(app_client):
    response = app_client.get("/api/temperatures")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_api_health_returns_200(app_client):
    response = app_client.get("/api/health")
    assert response.status_code == 200


def test_api_temperatures_empty_initially(app_client):
    response = app_client.get("/api/temperatures")
    assert response.json() == []


def test_api_health_empty_initially(app_client):
    response = app_client.get("/api/health")
    assert response.json() == {}


def test_api_temperatures_returns_data(app_client, db_session):
    db_session.add(
        SensorReadingRow(
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            sensor_id="28-abc",
            sensor_name="freezer",
            temperature_c=-5.0,
            temperature_f=23.0,
            read_quality=ReadQuality.OK.value,
            error_message=None,
        )
    )
    db_session.commit()
    response = app_client.get("/api/temperatures")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["sensor_id"] == "28-abc"
    assert data[0]["temperature_c"] == -5.0
    assert data[0]["read_quality"] == "ok"


def test_api_health_returns_data(app_client, db_session):
    db_session.add(
        PiHealthRow(
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            cpu_temp_c=50.0,
            cpu_percent=42.0,
            memory_percent=35.0,
            disk_percent=20.0,
        )
    )
    db_session.commit()
    response = app_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["cpu_percent"] == 42.0
    assert data["cpu_temp_c"] == 50.0
