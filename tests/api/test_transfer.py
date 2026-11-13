"""Manuscript import (docx/md/txt/epub), preview, backup and restore."""

from __future__ import annotations

import io
import json
import zipfile

import docx
from sqlmodel import Session, select

from server.db import engine
from server.models import Chapter, CodexEntry, Connection, Media, Memory, Project

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


def make_docx() -> bytes:
    d = docx.Document()
    d.add_paragraph("The Glass Orchard", style="Title")
    d.add_heading("Part One", level=1)
    d.add_heading("Chapter 1: The Bridge", level=2)
    p = d.add_paragraph("Iris crossed the bridge. ")
    p.add_run("Never again,").italic = True
    p.add_run(" she thought — and meant it.")
    d.add_paragraph("The river answered.")
    d.add_heading("Chapter 2: The Orchard", level=2)
    d.add_paragraph("The trees were glass.")
    d.add_heading("Part Two", level=1)
    d.add_heading("Chapter 3", level=2)
    d.add_paragraph("Winter came early.")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def make_epub() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml", """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>""")
        z.writestr("OEBPS/content.opf", """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Salt Road</dc:title></metadata>
<manifest>
<item id="c2" href="text/two.xhtml" media-type="application/xhtml+xml"/>
<item id="cover" href="text/cover.xhtml" media-type="application/xhtml+xml"/>
<item id="c1" href="text/one.xhtml" media-type="application/xhtml+xml"/>
</manifest>
<spine><itemref idref="cover"/><itemref idref="c1"/><itemref idref="c2"/></spine>
</package>""")
        z.writestr("OEBPS/text/cover.xhtml", "<html><body><img src='c.png'/></body></html>")
        z.writestr("OEBPS/text/one.xhtml",
                   "<html><head><title>One</title></head><body><h1>The Salt Road</h1>"
                   "<p>She walked <em>far</em> that day.</p><p>Then she slept.</p></body></html>")
        z.writestr("OEBPS/text/two.xhtml",
                   "<html><body><h2>Harbour</h2><p>The sea &amp; the sky.</p></body></html>")
    return buf.getvalue()


def upload(client, path, name, data, **form):
    return client.post(path, files={"file": (name, data)}, data=form)


def test_docx_import_headings_acts_italics(client):
    r = upload(client, "/api/projects/import", "orchard.docx", make_docx(), author="A. Writer")
    assert r.status_code == 201, r.text
    body = r.json()
    rep = body["report"]
    assert rep["detected_by"] == "headings"
    assert [c["title"] for c in rep["chapters"]] == ["The Bridge", "The Orchard", "Chapter 3"]
    assert [c["act"] for c in rep["chapters"]] == [1, 1, 2]
    p = body["project"]
    assert p["title"] == "The Glass Orchard" and p["author"] == "A. Writer" and p["chapter_count"] == 3
    with Session(engine()) as s:
        chs = s.exec(select(Chapter).where(Chapter.project_id == p["id"]).order_by(Chapter.number)).all()
        assert chs[0].text == "Iris crossed the bridge. *Never again,* she thought — and meant it.\n\n" \
                              "The river answered."
        assert all(c.status == "drafted" and c.word_count > 0 for c in chs)
        assert rep["words"] == sum(c.word_count for c in chs)


def test_docx_chapter_lines_without_styles(client):
    d = docx.Document()
    for line in ["Chapter One", "First words here.", "CHAPTER TWO", "Second words.", "Act II",
                 "Ch. 3 - Fire", "Burning."]:
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    rep = upload(client, "/api/projects/import/preview", "x.docx", buf.getvalue()).json()
    assert rep["detected_by"] == "chapter_lines"
    assert [(c["title"], c["act"]) for c in rep["chapters"]] == [("Chapter One", 1), ("CHAPTER TWO", 1),
                                                                 ("Fire", 2)]


def test_markdown_import(client):
    md = ("# My Book\n\n## Part One\n\n## Chapter 1\n\nHello *there*.\n\nSecond para.\n\n***\n\nScene two.\n\n"
          "## Chapter 2\n\nBye.\n")
    rep = upload(client, "/api/projects/import/preview", "book.md", md.encode()).json()
    assert rep["detected_by"] == "headings" and rep["title"] == "My Book"
    assert [c["title"] for c in rep["chapters"]] == ["Chapter 1", "Chapter 2"]
    r = upload(client, "/api/projects/import", "book.md", md.encode())
    with Session(engine()) as s:
        ch = s.exec(select(Chapter).where(Chapter.project_id == r.json()["project"]["id"],
                                          Chapter.number == 1)).one()
        assert ch.text == "Hello *there*.\n\nSecond para.\n\n* * *\n\nScene two."


def test_txt_chapter_lines_and_separators(client):
    txt = "Title page\n\nChapter 1\n\nOne.\nStill one.\n\nTwo.\n\nChapter 2\n\nThree.\n"
    rep = upload(client, "/api/projects/import/preview", "a.txt", txt.encode()).json()
    assert rep["detected_by"] == "chapter_lines" and len(rep["chapters"]) == 2
    assert any("front matter" in w for w in rep["warnings"])
    sep = "Alpha prose.\n\n\n\n\nBeta prose.\n\n***\n\nGamma prose.\n"
    rep = upload(client, "/api/projects/import/preview", "b.txt", sep.encode()).json()
    assert rep["detected_by"] == "separators"
    assert [c["title"] for c in rep["chapters"]] == ["Chapter 1", "Chapter 2", "Chapter 3"]


def test_epub_spine_order_and_italics(client):
    r = upload(client, "/api/projects/import", "salt.epub", make_epub())
    assert r.status_code == 201, r.text
    rep = r.json()["report"]
    assert rep["detected_by"] == "epub_spine"
    assert [c["title"] for c in rep["chapters"]] == ["The Salt Road", "Harbour"]
    assert r.json()["project"]["title"] == "Salt Road"
    with Session(engine()) as s:
        ch = s.exec(select(Chapter).where(Chapter.project_id == r.json()["project"]["id"],
                                          Chapter.number == 1)).one()
        assert ch.text == "She walked *far* that day.\n\nThen she slept."


def test_preview_writes_nothing(client):
    before = len(client.get("/api/projects").json())
    r = upload(client, "/api/projects/import/preview", "orchard.docx", make_docx())
    assert r.status_code == 200 and len(r.json()["chapters"]) == 3
    assert len(client.get("/api/projects").json()) == before
    with Session(engine()) as s:
        assert s.exec(select(Chapter)).all() == []


def test_rejects_bad_type(client):
    assert upload(client, "/api/projects/import/preview", "x.pdf", b"%PDF").status_code == 400


def _seed(client, pid):
    with Session(engine()) as s:
        s.add(Chapter(project_id=pid, number=1, title="One", text="Iris *ran*.", word_count=2,
                      doc={"type": "doc"}))
        s.add(Connection(provider="anthropic", api_key="sk-secret-123", is_default=True))
        s.commit()
    a = client.post(f"/api/projects/{pid}/codex", json={"kind": "character", "name": "Iris"}).json()
    b = client.post(f"/api/projects/{pid}/codex", json={"kind": "location", "name": "Glass Orchard"}).json()
    client.post(f"/api/projects/{pid}/codex-links", json={"source_id": a["id"], "target_id": b["id"],
                                                          "label": "lives in"})
    client.post(f"/api/projects/{pid}/memory", json={"kind": "fact", "content": "Iris fears water."})
    m = client.post(f"/api/projects/{pid}/media", files={"files": ("p.png", PNG, "image/png")})
    assert m.status_code in (200, 201), m.text


def test_backup_restore_round_trip(client, project, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_NO_EMBED", "1")
    pid = project["id"]
    _seed(client, pid)
    r = client.get(f"/api/projects/{pid}/backup")
    assert r.status_code == 200 and "novelos.zip" in r.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    book = json.loads(z.read("book.json"))
    assert book["format_version"] == 1
    raw = z.read("book.json").decode()
    assert "sk-secret-123" not in raw and "api_key" not in raw and "connection" not in book
    assert any(n.startswith("media/") for n in z.namelist())

    ids = [client.post("/api/projects/restore", files={"file": ("b.novelos.zip", r.content)}).json()["id"]
           for _ in range(2)]
    assert len(set(ids + [pid])) == 3
    with Session(engine()) as s:
        def snap(p):
            chs = [(c.number, c.title, c.text, c.doc) for c in
                   s.exec(select(Chapter).where(Chapter.project_id == p).order_by(Chapter.number))]
            codex = sorted((e.name, e.kind) for e in s.exec(select(CodexEntry).where(CodexEntry.project_id == p)))
            mems = sorted(m.content for m in s.exec(select(Memory).where(Memory.project_id == p)))
            from server.publish import media as store
            media = [store.file_path(m).read_bytes() for m in s.exec(select(Media).where(Media.project_id == p))]
            return chs, codex, mems, media
        orig = snap(pid)
        for new in ids:
            assert snap(new) == orig
            assert s.get(Project, new).title == project["title"]
        orig_ch = s.exec(select(Chapter).where(Chapter.project_id == pid)).one()
        new_ch = s.exec(select(Chapter).where(Chapter.project_id == ids[0])).one()
        assert orig_ch.id != new_ch.id
    links = client.get(f"/api/projects/{ids[0]}/codex-links").json()
    codex_ids = {e["id"] for e in client.get(f"/api/projects/{ids[0]}/codex").json()}
    assert len(links) == 1 and {links[0]["source_id"], links[0]["target_id"]} <= codex_ids


def test_restore_rejects_garbage(client):
    r = client.post("/api/projects/restore", files={"file": ("x.zip", b"not a zip")})
    assert r.status_code == 400
