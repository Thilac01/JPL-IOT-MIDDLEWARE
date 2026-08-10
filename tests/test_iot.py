from unittest.mock import MagicMock, patch

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

def test_iot_deploy_ssh_mocked(client):
    with patch("paramiko.SSHClient") as mock_ssh_cls:
        mock_client = MagicMock()
        mock_sftp = MagicMock()
        mock_file = MagicMock()
        mock_sftp.file.return_value.__enter__.return_value = mock_file
        mock_client.open_sftp.return_value = mock_sftp
        mock_ssh_cls.return_value = mock_client

        deploy_payload = {
            "ip": "10.0.5.20",
            "username": "pi",
            "password": "pi_secure_password"
        }
        response = client.post("/api/iot/deploy", json=deploy_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

def test_iot_stats_ssh_mocked(client):
    with patch("paramiko.SSHClient") as mock_ssh_cls:
        mock_client = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b'{"cpu": 18.5, "mem": 42.1, "temp": 48.2, "uptime": "up 5 days"}'
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b''
        mock_client.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)
        mock_ssh_cls.return_value = mock_client

        stats_payload = {
            "ip": "10.0.5.20",
            "username": "pi",
            "password": "pi_secure_password"
        }
        response = client.post("/api/iot/stats", json=stats_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "stats" in data
        assert data["stats"]["cpu"] == 18.5
