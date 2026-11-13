import io
import json

import pytest
from sqlmodel import Session

from server.voice.analyze import compute_traits

YOU = """The orchard was quiet. Iris walked the rows slowly, counting the glass apples that hung like held breath.
"You came back," her father said.
"I said I would."
She touched the bark. It was cold. The wasps had gone.
Somewhere a branch cracked; the sound carried across the frost and died.
She waited. Nothing moved.
"""

OTHER = """It is a truth universally acknowledged that the committee, having deliberated at extraordinary length upon the matter of the municipal budget, would inevitably arrive at conclusions which satisfied absolutely nobody whatsoever in the assembled and increasingly restless population of the town.
The treasurer certainly considered the proposal carefully and thoroughly, weighing every conceivable objection that the opposition might eventually raise during the forthcoming and doubtless interminable sessions of the council chamber.
"""

FAKE = {
    "signature_moves": [
        {"example": "She waited. Nothing moved.", "note": "Ends beats on two short falling sentences."},
        {"example": "glass apples that hung like held breath", "note": "One bodily simile per image."},
        {"example": "x " * 40, "note": "too long"},
    ],
    "never": ["suddenly", "dream openings"],
    "style_guide": "Write in close third, past tense. End paragraphs on short falling sentences.",
}


def _chapter(pid, n, text, pov="Iris"):
    from server.db import engine
    from server.models import Chapter
    with Session(engine()) as s:
        s.add(Chapter(project_id=pid, number=n, text=text, pov=pov, word_count=len(text.split())))
        s.commit()


@pytest.fixture
def fake_llm(monkeypatch):
    calls = []

    def complete(session, system, user, **kw):
        calls.append(user)
        return json.dumps(FAKE), None, "fake-model"

    monkeypatch.setattr("server.llm.complete", complete)
    monkeypatch.setattr("server.jobs.submit", lambda pid, task, fn, **kw: _Inline(fn))
    return calls


class _Inline:
    def __init__(self, fn):
        self.id, self.status = "inline", "done"
        self.output = fn("inline")


def test_trait_math():
    text = 'He ran.\n"Stop," she said quietly.\nThe long road wound slowly through the hills toward the sea.\n"Fine."'
    t = compute_traits(text)
    assert t["dialogue_ratio"] == 0.5
    # sentences: He ran. / "Stop," she said quietly. / The long road ... / "Fine."
    assert t["burst_rate"] == 0.75
    assert t["adverbs_per_1k"] == round(2 * 1000 / t["words"], 2)  # quietly, slowly
    assert t["pov"] == "third" and t["tense"] == "past"
    first = compute_traits("I walk to the door. I am tired. My hands shake.")
    assert first["pov"] == "first" and first["tense"] == "present"


def test_samples_crud_and_chapter_source(client, project):
    pid = project["id"]
    r = client.post(f"/api/projects/{pid}/voice/samples", json={"text": YOU, "title": "Orchard"})
    assert r.status_code == 201 and r.json()["word_count"] > 30
    up = client.post(f"/api/projects/{pid}/voice/samples",
                     files={"file": ("notes.md", io.BytesIO(b"She ran. He stayed."), "text/markdown")})
    assert up.status_code == 201 and up.json()["source"] == "upload"
    bad = client.post(f"/api/projects/{pid}/voice/samples",
                      files={"file": ("x.pdf", io.BytesIO(b"%PDF"), "application/pdf")})
    assert bad.status_code == 400
    _chapter(pid, 1, YOU)
    ch = client.post(f"/api/projects/{pid}/voice/samples", json={"source": "chapter:1"})
    assert ch.json()["source"] == "chapter:1"
    rows = client.get(f"/api/projects/{pid}/voice/samples").json()
    assert len(rows) == 3
    assert client.delete(f"/api/projects/{pid}/voice/samples/{rows[0]['id']}").status_code == 204
    assert len(client.get(f"/api/projects/{pid}/voice/samples").json()) == 2


def test_learn_job_saves_profile(client, project, fake_llm):
    pid = project["id"]
    assert client.post(f"/api/projects/{pid}/voice/learn").status_code == 400
    client.post(f"/api/projects/{pid}/voice/samples", json={"text": YOU})
    assert client.post(f"/api/projects/{pid}/voice/learn").status_code == 202
    prof = client.get(f"/api/projects/{pid}/voice/profile").json()
    assert prof["exists"] and prof["words_analyzed"] == compute_traits(YOU)["words"]
    assert prof["never"] == ["suddenly", "dream openings"]
    assert len(prof["signature_moves"]) == 3
    assert prof["signature_moves"][0]["verbatim"] is True
    assert len(prof["signature_moves"][2]["example"].split()) <= 26
    assert "dialogue_ratio" in prof["traits"]


def test_match_scores(client, project, fake_llm):
    pid = project["id"]
    client.post(f"/api/projects/{pid}/voice/samples", json={"text": YOU})
    client.post(f"/api/projects/{pid}/voice/learn")
    _chapter(pid, 1, YOU)
    _chapter(pid, 2, OTHER)
    same = client.get(f"/api/projects/{pid}/voice/match", params={"chapter": 1}).json()
    assert same["score"] == 100 and same["gaps"] == []
    diff = client.get(f"/api/projects/{pid}/voice/match", params={"chapter": 2}).json()
    assert diff["score"] < 70 and 1 <= len(diff["gaps"]) <= 3
    assert any("Dialogue" in g for g in diff["gaps"]) or diff["gaps"]
    assert {t["key"] for t in diff["traits"]} >= {"dialogue_ratio", "burst_rate"}
    allm = client.get(f"/api/projects/{pid}/voice/match/all").json()
    assert [m["chapter"] for m in allm] == [1, 2] and allm[0]["score"] == 100


def test_style_guide_per_lift(client, project, fake_llm):
    from server.db import engine
    from server.services.voice import get_style_guide
    pid = project["id"]
    with Session(engine()) as s:
        assert get_style_guide(s, pid) == ""
    client.post(f"/api/projects/{pid}/voice/samples", json={"text": YOU})
    client.post(f"/api/projects/{pid}/voice/learn")
    expected = {"pure_me": "match the author exactly", "me_plus_lift": "never copy",
                "experiment": "push stylistic range while keeping POV/tense"}
    for lift, phrase in expected.items():
        r = client.patch(f"/api/projects/{pid}/voice/profile", json={"lift": lift})
        assert r.json()["lift"] == lift
        with Session(engine()) as s:
            g = get_style_guide(s, pid)
        assert "close third" in g and "suddenly" in g and phrase.lower() in g.lower()
    assert client.patch(f"/api/projects/{pid}/voice/profile", json={"lift": "bogus"}).status_code == 422
    r = client.patch(f"/api/projects/{pid}/voice/profile", json={"never": ["adverbs"], "style_guide": "Be terse."})
    assert r.json()["never"] == ["adverbs"] and r.json()["style_guide"] == "Be terse."


def test_docx_upload(client, project):
    docx = pytest.importorskip("docx")
    d = docx.Document()
    d.add_paragraph("The orchard was quiet.")
    d.add_paragraph("She waited. Nothing moved.")
    buf = io.BytesIO()
    d.save(buf)
    r = client.post(f"/api/projects/{project['id']}/voice/samples", data={"title": "Docx"},
                    files={"file": ("s.docx", buf.getvalue(),
                                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert r.status_code == 201 and r.json()["word_count"] == 8 and r.json()["title"] == "Docx"
