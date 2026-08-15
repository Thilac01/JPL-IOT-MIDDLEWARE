def test_technical_login_admin(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["user"]["role"] == "technical"
    assert "live-tables" in data["user"]["allowed_tabs"]

def test_technical_login_tech(client):
    response = client.post("/api/auth/login", json={"username": "tech", "password": "tech123"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["user"]["role"] == "technical"
    assert "iot-maps" in data["user"]["allowed_tabs"]

def test_staff_login_staff(client):
    response = client.post("/api/auth/login", json={"username": "staff", "password": "staff123"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["user"]["role"] == "staff"
    assert "live-tables" not in data["user"]["allowed_tabs"]

def test_staff_login_librarian(client):
    response = client.post("/api/auth/login", json={"username": "librarian", "password": "staff123"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["user"]["role"] == "staff"
    assert "audit" not in data["user"]["allowed_tabs"]

def test_invalid_login(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert response.status_code == 401

def test_auth_me_endpoint(client):
    login_res = client.post("/api/auth/login", json={"username": "staff", "password": "staff123"})
    token = login_res.json()["token"]

    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["username"] == "staff"
    assert me_data["role"] == "staff"
