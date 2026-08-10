def test_get_tables_list(client):
    response = client.get("/api/tables")
    assert response.status_code == 200
    tables = response.json()
    assert isinstance(tables, list)
    assert len(tables) > 0

def test_get_table_data_valid(client):
    response = client.get("/api/table-data/biblio?limit=10")
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)

def test_sql_injection_rejection(client):
    bad_tables = [
        "biblio; DROP TABLE items; --",
        "biblio UNION SELECT 1, 2, 3",
        "users--",
        "biblio' OR '1'='1"
    ]
    for bad in bad_tables:
        response = client.get(f"/api/table-data/{bad}")
        assert response.status_code in [400, 404, 422]
