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
