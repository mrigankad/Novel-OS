"""Codex typed entries + portrait attach (PLAN.md P2.2 / P2.3)."""

import struct
import zlib

from fastapi.testclient import TestClient

from api.main import create_app


def _png(width: int = 32, height: int = 32) -> bytes:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _client(tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    app = create_app(
        projects_root=projects,
        db_url=f"sqlite:///{(tmp_path / 't.db').as_posix()}",
        media_root=tmp_path / "media",
    )
    return TestClient(app)


def test_codex_crud_and_portrait(tmp_path):
    client = _client(tmp_path)
    created = client.post("/api/projects", json={
        "title": "Codex Tale", "genre": "Fantasy", "author": "Ada",
    }).json()
    pid = created["id"]

    chars = client.post(f"/api/projects/{pid}/codex", json={
        "entry_type": "character", "name": "Mara Vale", "role": "protagonist",
    })
    assert chars.status_code == 201
    assert any(e["name"] == "Mara Vale" for e in chars.json())

    locs = client.post(f"/api/projects/{pid}/codex", json={
        "entry_type": "location",
        "name": "Glass Harbor",
        "summary": "A fogbound port city.",
    })
    assert locs.status_code == 201
    loc = next(e for e in locs.json() if e["name"] == "Glass Harbor")
    assert loc["entry_type"] == "location"
    assert "fogbound" in loc["summary"].lower()

    all_entries = client.get(f"/api/projects/{pid}/codex").json()
    assert len(all_entries) >= 2
    only_loc = client.get(f"/api/projects/{pid}/codex?entry_type=location").json()
    assert all(e["entry_type"] == "location" for e in only_loc)

    bad = client.post(f"/api/projects/{pid}/codex", json={
        "entry_type": "spaceship", "name": "Nope",
    })
    assert bad.status_code == 400

    mara = next(e for e in client.get(f"/api/projects/{pid}/codex?entry_type=character").json()
                if e["name"] == "Mara Vale")

    up = client.post(
        f"/api/projects/{pid}/media",
        files={"file": ("mara.png", _png(), "image/png")},
        data={"kind": "portrait", "alt": "Mara"},
    )
    assert up.status_code == 201, up.text
    media_id = up.json()["id"]

    portrait = client.put(
        f"/api/projects/{pid}/codex/{mara['id']}/portrait",
        json={"media_id": media_id, "entry_type": "character"},
    )
    assert portrait.status_code == 200, portrait.text
    body = portrait.json()
    assert body["portrait_media_id"] == media_id
    assert body["portrait_url"] and media_id in body["portrait_url"]

    up2 = client.post(
        f"/api/projects/{pid}/media",
        files={"file": ("harbor.png", _png(16, 16), "image/png")},
        data={"kind": "location", "alt": "Harbor"},
    )
    assert up2.status_code == 201
    loc_portrait = client.put(
        f"/api/projects/{pid}/codex/{loc['id']}/portrait",
        json={"media_id": up2.json()["id"], "entry_type": "location"},
    )
    assert loc_portrait.status_code == 200
    assert loc_portrait.json()["portrait_media_id"] == up2.json()["id"]
