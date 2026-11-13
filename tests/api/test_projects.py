def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_project_crud(client, project):
    pid = project["id"]
    assert project["word_count"] == 0
    assert [p["id"] for p in client.get("/api/projects").json()] == [pid]
    r = client.patch(f"/api/projects/{pid}", json={"premise": "Frost, wasps, a knife."})
    assert r.json()["premise"] == "Frost, wasps, a knife."
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/projects/{pid}").status_code == 404
