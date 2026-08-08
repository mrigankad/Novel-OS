"""Media storage (PLAN.md P0.3) validation, content-addressing, and routes."""

import json
import struct
import zlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import media as media_lib
from api.main import create_app


# --------------------------------------------------------------------- fixtures

def _png(width: int, height: int) -> bytes:
    """A minimal but structurally valid PNG, so header parsing is exercised
    against real bytes rather than a hand-faked prefix."""
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _gif(width: int, height: int) -> bytes:
    return b"GIF89a" + struct.pack("<HH", width, height) + b"\x00" * 10


def _seed_project(root: Path, slug: str) -> None:
    state_dir = root / slug / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "metadata": {"title": "The Last Signal", "genre": "Sci-Fi", "author": "T"},
        "characters": {}, "plot_threads": {}, "chapters": {},
        "timeline": [], "style_profile": {}, "session_log": [],
    }
    (state_dir / "story_state.json").write_text(json.dumps(state), encoding="utf-8")


@pytest.fixture
def projects_root(tmp_path):
    _seed_project(tmp_path / "projects", "the-last-signal")
    return tmp_path / "projects"


@pytest.fixture
def client(tmp_path, projects_root):
    db_url = f"sqlite:///{(tmp_path / 'media_test.db').as_posix()}"
    app = create_app(projects_root=projects_root, db_url=db_url,
                     media_root=tmp_path / "media")
    return TestClient(app)


def _upload(client, data: bytes, name="portrait.png", ctype="image/png", **form):
    return client.post(
        "/api/projects/the-last-signal/media",
        files={"file": (name, data, ctype)},
        data=form or None,
    )


# ------------------------------------------------------------------ unit: media

def test_validate_rejects_svg():
    """SVG can carry script; it must not be storable as an image."""
    with pytest.raises(media_lib.MediaError) as e:
        media_lib.validate(b"<svg/>", "image/svg+xml")
    assert e.value.status == 415


def test_validate_rejects_oversize():
    with pytest.raises(media_lib.MediaError) as e:
        media_lib.validate(b"x" * (media_lib.MAX_BYTES + 1), "image/png")
    assert e.value.status == 413


def test_validate_accepts_content_type_with_charset():
    assert media_lib.validate(b"x", "image/png; charset=binary") == ".png"


def test_clean_filename_strips_path_components():
    assert media_lib.clean_filename("../../etc/passwd") == "passwd"
    assert media_lib.clean_filename("") == "image"
    # Whatever the platform makes of a backslash path, no separator survives.
    cleaned = media_lib.clean_filename("C:\\evil\\..\\x.png")
    assert "/" not in cleaned and "\\" not in cleaned


def test_dimensions_reads_png_and_gif_headers():
    assert media_lib.dimensions(_png(7, 3)) == (7, 3)
    assert media_lib.dimensions(_gif(64, 32)) == (64, 32)


def test_dimensions_returns_zero_for_unparseable_bytes():
    assert media_lib.dimensions(b"not an image at all") == (0, 0)


def test_local_store_rejects_traversal_in_ids(tmp_path):
    store = media_lib.LocalMediaStore(tmp_path)
    with pytest.raises(media_lib.MediaError):
        store.read("../../etc", "a" * 64, ".png")
    with pytest.raises(media_lib.MediaError):
        store.read("proj", "../../../etc/passwd", ".png")


def test_local_store_round_trips_and_deletes(tmp_path):
    store = media_lib.LocalMediaStore(tmp_path)
    data = _png(2, 2)
    sha = media_lib.digest(data)
    store.put("proj", sha, ".png", data)
    assert store.read("proj", sha, ".png") == data
    assert store.delete("proj", sha, ".png") is True
    assert store.read("proj", sha, ".png") is None
    assert store.delete("proj", sha, ".png") is False


# ----------------------------------------------------------------- routes

def test_upload_returns_metadata_and_dimensions(client):
    resp = _upload(client, _png(12, 5), alt="Lena at the array")
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "portrait.png"
    assert body["content_type"] == "image/png"
    assert (body["width"], body["height"]) == (12, 5)
    assert body["alt"] == "Lena at the array"
    assert body["kind"] == "general"
    assert body["url"].endswith("/raw")


def test_uploaded_image_is_served_back_byte_identical(client):
    data = _png(4, 4)
    url = _upload(client, data).json()["url"]
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.content == data
    assert resp.headers["content-type"] == "image/png"
    # Content-addressed, so the bytes behind this id can never change.
    assert "immutable" in resp.headers["cache-control"]


def test_identical_bytes_deduplicate_to_one_record(client):
    data = _png(3, 3)
    first = _upload(client, data, name="a.png").json()
    second = _upload(client, data, name="b.png").json()
    assert first["id"] == second["id"]
    assert len(client.get("/api/projects/the-last-signal/media").json()) == 1


def test_different_bytes_create_separate_records(client):
    _upload(client, _png(3, 3))
    _upload(client, _png(4, 4))
    assert len(client.get("/api/projects/the-last-signal/media").json()) == 2


def test_list_filters_by_kind(client):
    _upload(client, _png(3, 3), kind="portrait")
    _upload(client, _png(4, 4), kind="research")
    portraits = client.get("/api/projects/the-last-signal/media?kind=portrait").json()
    assert [m["kind"] for m in portraits] == ["portrait"]


def test_patch_media_updates_alt(client):
    media = _upload(client, _png(6, 6), kind="research", name="pier.png").json()
    resp = client.patch(
        f"/api/projects/the-last-signal/media/{media['id']}",
        json={"alt": "Glass Harbor pier at dusk"},
    )
    assert resp.status_code == 200
    assert resp.json()["alt"] == "Glass Harbor pier at dusk"
    listed = client.get("/api/projects/the-last-signal/media?kind=research").json()
    assert listed[0]["alt"] == "Glass Harbor pier at dusk"


def test_upload_rejects_svg(client):
    resp = _upload(client, b"<svg onload=alert(1)/>", name="x.svg", ctype="image/svg+xml")
    assert resp.status_code == 415


def test_delete_removes_record_and_blob(client, tmp_path):
    media = _upload(client, _png(5, 5)).json()
    blob = tmp_path / "media" / "the-last-signal"
    assert any(blob.rglob("*.png"))

    assert client.delete(f"/api/projects/the-last-signal/media/{media['id']}").status_code == 204
    assert client.get(media["url"]).status_code == 404
    assert not any(blob.rglob("*.png"))


def test_media_routes_404_on_unknown_project(client):
    assert client.get("/api/projects/nope/media").status_code == 404
    assert client.post("/api/projects/nope/media",
                       files={"file": ("a.png", _png(2, 2), "image/png")}).status_code == 404


def test_media_is_not_readable_across_projects(client, projects_root):
    """A media id from one project must not resolve under another."""
    _seed_project(projects_root, "other-book")
    media = _upload(client, _png(6, 6)).json()
    resp = client.get(f"/api/projects/other-book/media/{media['id']}/raw")
    assert resp.status_code == 404
