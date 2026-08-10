def test_active_loans_endpoint(client):
    response = client.get("/api/active-loans")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        loan = data[0]
        assert "barcode" in loan or "issue_id" in loan

def test_recent_returns_endpoint(client):
    response = client.get("/api/recent-returns")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_stats_endpoint(client):
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "active_loans" in data
    assert "overdue" in data
    assert "system_status" in data

def test_audit_logs_endpoint(client):
    response = client.get("/api/audit-logs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
