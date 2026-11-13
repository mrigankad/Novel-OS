"""Studio access control: local-only by default, password when exposed, reader links always public."""

from server import auth


def test_local_only_by_default(client, project, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_LOCAL_ONLY", "1")
    r = client.get("/api/projects")  # TestClient's peer is not loopback, like a remote device
    assert r.status_code == 403 and "NOVEL_OS_PASSWORD" in r.json()["detail"]
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/read/not-a-real-token").status_code in (404, 410)  # public route, not 403


def test_forwarded_client_decides_behind_the_proxy():
    assert auth.client_is_local("127.0.0.1", None)
    assert auth.client_is_local("127.0.0.1", "::1")
    assert not auth.client_is_local("127.0.0.1", "203.0.113.9")  # a phone on the internet via Next
    assert not auth.client_is_local("192.168.1.20", None)


def test_password_mode_requires_sign_in(client, project, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_LOCAL_ONLY", "1")
    monkeypatch.setenv("NOVEL_OS_PASSWORD", "orchard")
    assert client.get("/api/projects").status_code == 401
    assert client.get("/api/auth/status").json() == {"password_required": True, "signed_in": False}
    assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
    r = client.post("/api/auth/login", json={"password": "orchard"})
    assert r.status_code == 200 and auth.COOKIE in r.cookies
    assert client.get("/api/projects").status_code == 200
    assert client.get("/api/auth/status").json()["signed_in"] is True
    client.post("/api/auth/logout")
    client.cookies.clear()
    assert client.get("/api/projects").status_code == 401


def test_tampered_or_expired_sessions_fail(monkeypatch):
    token = auth.issue()
    assert auth.valid(token)
    v, exp, sig = token.split(".")
    assert not auth.valid(f"{v}.{int(exp) + 999}.{sig}")
    assert not auth.valid(f"{v}.{exp}.{'0' * len(sig)}")
    assert not auth.valid("garbage")


def test_login_is_rate_limited(client, monkeypatch):
    from server.routers import auth as auth_router
    auth_router._attempts.clear()
    monkeypatch.setenv("NOVEL_OS_PASSWORD", "orchard")
    codes = [client.post("/api/auth/login", json={"password": "nope"}).status_code for _ in range(12)]
    assert codes[:10] == [401] * 10 and codes[-1] == 429
