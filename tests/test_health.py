def test_liveness_probe(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "uptime_seconds" in data

def test_readiness_probe(client):
    response = client.get("/ready")
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data

def test_diagnostic_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "database" in data
    assert "smtp" in data
    assert "iot" in data
    assert "system" in data

def test_metrics_endpoint(client):
    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "app_uptime_seconds" in data
    assert "db_queries_total" in data
    assert "cdc_events_processed_total" in data
