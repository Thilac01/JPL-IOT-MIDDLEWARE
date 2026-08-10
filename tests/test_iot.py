def test_iot_scan(client):
    response = client.post("/api/iot/scan")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "nodes" in data
    assert isinstance(data["nodes"], list)

def test_iot_heartbeat_and_nodes(client):
    payload = {
        "ip": "192.168.1.150",
        "status": "ACTIVE",
        "barcodes_tracked": 12
    }
    hb_resp = client.post("/api/iot/heartbeat", json=payload)
    assert hb_resp.status_code == 200
    assert hb_resp.json() == {"status": "ok"}

    nodes_resp = client.get("/api/iot/nodes")
    assert nodes_resp.status_code == 200
    nodes = nodes_resp.json()
    assert any(n.get("ip") == "192.168.1.150" for n in nodes)

def test_iot_deploy_simulated(client):
    deploy_payload = {
        "ip": "192.168.1.101",
        "username": "pi",
        "password": "raspberry_password"
    }
    response = client.post("/api/iot/deploy", json=deploy_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

def test_iot_stats_simulated(client):
    stats_payload = {
        "ip": "192.168.1.101",
        "username": "pi",
        "password": "raspberry_password"
    }
    response = client.post("/api/iot/stats", json=stats_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "stats" in data
    assert "cpu" in data["stats"]
