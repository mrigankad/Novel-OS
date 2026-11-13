"""Ship area: media, cover studio, releases, compile, marketing."""

import io
import time
import zipfile

import pytest

from server.publish import cover as cv

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402


def _png(w=40, h=60, color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def _add_chapters(pid, chapters):
    from server.db import session_scope
    from server.models import Chapter

    with session_scope() as s:
        for n, title, text in chapters:
            s.add(Chapter(project_id=pid, number=n, title=title, text=text,
                          word_count=len(text.split()), status="drafted"))


def _upload(client, pid, data, name="a.png", ctype="image/png"):
    return client.post(f"/api/projects/{pid}/media", files=[("files", (name, data, ctype))])


# ------------------------------------------------------------------ media

def test_media_upload_dedupe_serve_delete(client, project):
    pid = project["id"]
    r = _upload(client, pid, _png())
    assert r.status_code == 201
    m = r.json()[0]
    assert (m["width"], m["height"], m["content_type"]) == (40, 60, "image/png")
    assert m["duplicate"] is False

    again = _upload(client, pid, _png(), name="copy.png").json()[0]
    assert again["id"] == m["id"] and again["duplicate"] is True
    assert len(client.get(f"/api/projects/{pid}/media").json()) == 1

    served = client.get(m["url"])
    assert served.status_code == 200
    assert served.content == _png()
    assert "immutable" in served.headers["cache-control"]
    assert served.headers["etag"] == f'"{m["sha256"]}"'
    assert client.get(m["url"], headers={"If-None-Match": served.headers["etag"]}).status_code == 304

    p = client.patch(f"/api/media/{m['id']}", json={"caption": "Orchard", "tags": ["moody", "Moody", "map"],
                                                     "kind": "map"}).json()
    assert p["tags"] == ["moody", "map"] and p["kind"] == "map"
    assert client.patch(f"/api/media/{m['id']}", json={"kind": "nope"}).status_code == 422
    assert [x["id"] for x in client.get(f"/api/projects/{pid}/media?kind=map").json()] == [m["id"]]
    assert client.get(f"/api/projects/{pid}/media?tag=moody").json()[0]["id"] == m["id"]
    assert client.get(f"/api/projects/{pid}/media?tag=other").json() == []

    assert client.delete(f"/api/media/{m['id']}").status_code == 204
    assert client.get(m["url"]).status_code == 404
    assert client.get(f"/api/projects/{pid}/media").json() == []


def test_media_rejects_non_images(client, project):
    r = _upload(client, project["id"], b"hello world", name="x.txt", ctype="text/plain")
    assert r.status_code == 415


def test_media_import_from_url(client, project, monkeypatch):
    from server.publish import media as store

    monkeypatch.setattr(store, "fetch_url", lambda url: (_png(10, 10), "image/png", "remote.png"))
    r = client.post(f"/api/projects/{project['id']}/media/import", json={"url": "https://x.test/remote.png"})
    assert r.status_code == 201 and r.json()["filename"] == "remote.png"


# ------------------------------------------------------------------ cover maths

def test_spine_matches_kdp():
    assert cv.spine_width(312, "cream") == pytest.approx(0.78)
    assert cv.spine_width(300, "white") == pytest.approx(0.6756)
    assert cv.spine_width(200, "color") == pytest.approx(0.4694)


def test_page_estimate_and_wrap():
    assert cv.estimate_pages(78_000, "5.5x8.5") == 312
    assert cv.estimate_pages(90_000, "6x9") == 300
    assert cv.estimate_pages(100, "5.5x8.5") == 24  # KDP minimum
    s = cv.compute_spec(fmt="paperback", trim="6x9", paper="cream", words=0, pages=312)
    assert s.spine_in == pytest.approx(0.78)
    assert s.wrap_w_in == pytest.approx(2 * 6 + 0.78 + 0.25)
    assert s.wrap_h_in == pytest.approx(9.25)
    assert s.spine_text_allowed
    assert not cv.compute_spec(pages=80).spine_text_allowed


def test_cover_spec_endpoint_uses_manuscript(client, project):
    pid = project["id"]
    _add_chapters(pid, [(1, "One", " ".join(["word"] * 78_000))])
    d = client.get(f"/api/projects/{pid}/cover/spec?format=paperback&trim=5.5x8.5&paper=cream").json()
    assert d["pages"] == 312 and d["spine_in"] == pytest.approx(0.78)
    assert d["wrap_w_in"] == pytest.approx(11 + 0.78 + 0.25)
    assert d["wrap_h_in"] == pytest.approx(8.75)
    assert set(d["barcode_box"]) == {"x_in", "y_in", "w_in", "h_in"}
    assert client.get(f"/api/projects/{pid}/cover/spec?paper=gold").status_code == 422


def test_preflight_flags_low_res(client, project):
    pid = project["id"]
    low = _upload(client, pid, _png(400, 600)).json()[0]
    c = client.post(f"/api/projects/{pid}/covers", json={"front_media_id": low["id"], "pages": 80,
                                                         "spine_text": "TITLE"}).json()
    assert c["selected"] is True
    pf = client.get(f"/api/projects/{pid}/covers/{c['id']}/preflight").json()
    checks = {x["key"]: x for x in pf["checks"]}
    assert checks["front_image"]["status"] == "fail"
    assert checks["spine_text"]["status"] == "fail"  # < 100 pages
    assert checks["title"]["status"] == "pass"
    assert pf["ok"] is False

    hi = _upload(client, pid, _png(1800, 2700, (10, 10, 10))).json()[0]
    client.patch(f"/api/projects/{pid}/covers/{c['id']}",
                 json={"front_media_id": hi["id"], "spine_text": "", "back_copy": "x" * 5000})
    checks = {x["key"]: x for x in client.get(f"/api/projects/{pid}/covers/{c['id']}/preflight").json()["checks"]}
    assert checks["front_image"]["status"] == "pass"
    assert checks["back_copy"]["status"] == "fail"

    # Selecting a second design deselects the first
    c2 = client.post(f"/api/projects/{pid}/covers", json={"format": "ebook", "selected": True}).json()
    sel = [x["id"] for x in client.get(f"/api/projects/{pid}/covers").json() if x["selected"]]
    assert sel == [c2["id"]]

    pdf = client.get(f"/api/projects/{pid}/covers/{c['id']}/export?kind=pdf")
    if pdf.status_code != 501:
        assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    jpg = client.get(f"/api/projects/{pid}/covers/{c2['id']}/export?kind=jpg")
    assert jpg.status_code == 200
    assert Image.open(io.BytesIO(jpg.content)).size == (1600, 2560)


# ------------------------------------------------------------------ metadata + releases

def test_metadata_and_release_status(client, project):
    pid = project["id"]
    rel = client.get(f"/api/projects/{pid}/releases").json()
    stores = {r["store"]: r for r in rel["releases"]}
    assert set(stores) == {"kdp", "ingram", "d2d", "audiobook", "beta", "query"}
    assert stores["kdp"]["status"] == "blocked"
    assert rel["steps_total"] > 0 and rel["steps_done"] == 0

    assert client.put(f"/api/projects/{pid}/metadata", json={"keywords": [str(i) for i in range(8)]}).status_code == 422
    meta = client.put(f"/api/projects/{pid}/metadata", json={
        "description": "A long description. " * 12, "keywords": [f"k{i}" for i in range(7)],
        "bisac": ["fic019000", "FIC045000", "FIC014000"], "price": {"usd": 4.99},
    }).json()
    assert meta["bisac"][0] == "FIC019000"

    _add_chapters(pid, [(1, "One", "Frost came early."), (2, "Two", "The wasps woke.")])
    img = _upload(client, pid, _png(1800, 2700)).json()[0]
    client.post(f"/api/projects/{pid}/covers", json={"front_media_id": img["id"], "format": "paperback"})
    client.post(f"/api/projects/{pid}/covers", json={"front_media_id": img["id"], "format": "ebook"})

    stores = {r["store"]: r for r in client.get(f"/api/projects/{pid}/releases").json()["releases"]}
    if stores["kdp"]["items"][0]["done"]:  # reportlab present
        assert stores["kdp"]["status"] == "ready"
    ingram = {i["key"]: i for i in stores["ingram"]["items"]}
    assert ingram["isbn_print"]["done"] is False
    assert stores["ingram"]["status"] == "blocked"

    client.put(f"/api/projects/{pid}/metadata", json={**meta, "isbn_print": "978-0-306-40615-7"})
    stores = {r["store"]: r for r in client.get(f"/api/projects/{pid}/releases").json()["releases"]}
    if stores["ingram"]["items"][0]["done"]:
        assert stores["ingram"]["status"] == "ready"

    # Manual items and manual status
    r = client.patch(f"/api/projects/{pid}/releases/beta", json={"checklist": {"readers": True}}).json()
    assert r["status"] == "ready"
    r = client.patch(f"/api/projects/{pid}/releases/beta", json={"status": "live"}).json()
    assert r["status"] == "live"


# ------------------------------------------------------------------ compile

CHAPTERS = [
    (2, "Departure", "They left at dawn.\n\n---\n\nNobody **waved**."),
    (1, "Arrival", "She waited by the *pier*.\n\nThe tide came in."),
]


@pytest.mark.parametrize("fmt", ["md", "html", "epub", "docx"])
def test_compile_formats(client, project, fmt):
    pid = project["id"]
    _add_chapters(pid, CHAPTERS)
    r = client.get(f"/api/projects/{pid}/compile?format={fmt}")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    if fmt in ("md", "html"):
        text = r.text
        assert text.index("Arrival") < text.index("Departure")  # DB order by number
        assert "pier" in text
    else:
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()
        if fmt == "epub":
            assert names[0] == "mimetype"
        else:
            assert "word/document.xml" in names
            assert "Arrival" in z.read("word/document.xml").decode()


def test_compile_pdf_or_hint(client, project):
    pid = project["id"]
    _add_chapters(pid, CHAPTERS)
    r = client.get(f"/api/projects/{pid}/compile?format=pdf")
    assert r.status_code in (200, 501)
    if r.status_code == 200:
        assert r.content[:4] == b"%PDF"
    assert client.get(f"/api/projects/{pid}/compile?format=rtf").status_code == 422


# ------------------------------------------------------------------ marketing

def _wait(pred, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        v = pred()
        if v:
            return v
        time.sleep(0.05)
    raise AssertionError("timed out")


def test_marketing_job_with_fake_llm(client, project, monkeypatch):
    from server import llm

    calls = []

    def fake(session, system, user, **kw):
        calls.append(user)
        return f"COPY for task {len(calls)}", None, "fake-model"

    monkeypatch.setattr(llm, "complete", fake)
    pid = project["id"]
    _add_chapters(pid, CHAPTERS)
    assert client.post(f"/api/projects/{pid}/marketing", json={"kinds": ["poem"]}).status_code == 422
    r = client.post(f"/api/projects/{pid}/marketing", json={"kinds": ["blurb", "taglines"]})
    assert r.status_code == 202 and r.json()["run_id"]
    assets = _wait(lambda: (lambda a: a if len(a) == 2 else None)(
        client.get(f"/api/projects/{pid}/marketing").json()))
    assert {a["kind"] for a in assets} == {"blurb", "taglines"}
    assert all(a["model"] == "fake-model" for a in assets)
    assert "The Glass Orchard" in calls[0]


def test_cover_concepts_with_fake_llm(client, project, monkeypatch):
    from server import llm

    payload = ('Here: {"concepts": [' + ",".join(
        '{"name": "C%d", "mood": "cold", "palette": ["#112233", "#ffffff", "bad"], '
        '"composition": "orchard", "typography": "serif", "image_prompt": "frost orchard"}' % i
        for i in range(3)) + "]}")
    monkeypatch.setattr(llm, "complete", lambda *a, **k: (payload, None, "fake"))
    pid = project["id"]
    assert client.post(f"/api/projects/{pid}/cover/concepts").status_code == 202
    concepts = _wait(lambda: client.get(f"/api/projects/{pid}/cover/concepts").json())
    assert len(concepts) == 3 and concepts[0]["palette"] == ["#112233", "#ffffff"]
