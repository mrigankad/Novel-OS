"""Audiobook studio: chunking, pronunciation, attribution, adapters (fake HTTP/SDK), rendering, streaming."""

import io
import json
import zipfile

import httpx
import pytest

from server.audio import pronounce, render, tts
from server.routers import audio as audio_router


def fake_mp3(frames: int = 40) -> bytes:
    # MPEG-1 Layer III, 128 kbps, 44.1 kHz, no padding: 417-byte frames.
    return (b"\xff\xfb\x90\x00" + b"\x00" * 413) * frames


# --------------------------------------------------------------- chunking

def test_chunks_respect_limit_and_paragraphs():
    paras = ["Para one is short.", "Para two. " * 30, "Para three."]
    text = "\n\n".join(paras)
    chunks = tts.chunk_text(text, 120)
    assert all(len(c) <= 120 for c in chunks)
    assert chunks[0].startswith("Para one is short.")
    # sentence boundaries: nothing ends mid-sentence
    assert all(c.rstrip().endswith(".") for c in chunks)
    assert " ".join(" ".join(chunks).split()) == " ".join(text.split())


def test_chunks_fall_back_to_words_and_hard_cut():
    long_sentence = "word " * 100
    assert all(len(c) <= 50 for c in tts.chunk_text(long_sentence, 50))
    assert tts.chunk_text("x" * 25, 10) == ["x" * 10, "x" * 10, "x" * 5]
    assert tts.chunk_text("", 10) == []


def test_provider_limits():
    assert tts.PROVIDERS["openai"].max_chars == 4000
    assert tts.PROVIDERS["elevenlabs"].max_chars == 5000


# --------------------------------------------------------------- pronunciation

def test_pronunciation_whole_words_any_case_longest_first():
    pairs = [("Iris", "EYE-ris"), ("Iris Vale", "EYE-ris VAYL")]
    assert pronounce.apply("Iris Vale met iris. Irises bloomed.", pairs) == \
        "EYE-ris VAYL met EYE-ris. Irises bloomed."
    assert pronounce.apply("No change", []) == "No change"


def test_pronunciation_suggest_from_names():
    got = pronounce.suggest(["Iris Vale", "the Orchard", "Ma"], existing=["vale"])
    assert "Iris Vale" in got and "Iris" in got and "Vale" not in got and "Ma" not in got


# --------------------------------------------------------------- attribution

NAMES = {"iris": "c1", "iris vale": "c1", "tom": "c2"}


@pytest.mark.parametrize("para,who", [
    ('"Come here," Iris said.', "c1"),
    ('"Where?" asked Tom.', "c2"),
    ('"Fine." Iris Vale whispered it.', "c1"),
    ('"Come here," she said.', None),          # pronoun: unsure
    ('"Come here," Marta said.', None),        # not cast
    ('"Come here." The wind rose.', None),     # no tag
    ("No dialogue at all.", None),
])
def test_attribution_is_conservative(para, who):
    assert render.speaker_for(para, NAMES) == who


def test_segments_split_quotes_from_narration():
    segs = render.segments('The door opened.\n\n"Come here," Iris said. "Now."\n\nShe left.', NAMES)
    assert segs[0] == (None, "The door opened.")
    assert segs[1] == ("c1", "Come here,")
    assert segs[2][0] is None and "Iris said." in segs[2][1]
    assert segs[3] == ("c1", "Now.")
    assert segs[-1] == (None, "She left.")


def test_mp3_info_reads_frames():
    info = render.mp3_info(fake_mp3(100))
    assert info["bitrates"] == [128] and info["cbr"] and info["sample_rates"] == [44100]
    assert 2.5 < info["duration_s"] < 2.7


# --------------------------------------------------------------- ElevenLabs adapter

def test_elevenlabs_request_shape_and_chunk_concat():
    calls = []

    def handler(req: httpx.Request):
        calls.append(req)
        if req.method == "GET":
            return httpx.Response(200, json={"voices": [{"voice_id": "v1", "name": "Rachel", "labels": {"accent": "american"}}]})
        return httpx.Response(200, content=b"MP3")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    text = ("A sentence of narration. " * 300).strip()  # > 5000 chars -> 2 chunks
    out = tts.synthesize("elevenlabs", text, voice="v1", api_key="xi", http=client)
    assert out == b"MP3MP3"
    req = calls[0]
    assert req.method == "POST"
    assert req.url.path == "/v1/text-to-speech/v1"
    assert req.url.params["output_format"] == "mp3_44100_128"
    assert req.headers["xi-api-key"] == "xi"
    body = json.loads(req.content)
    assert body["model_id"] == "eleven_multilingual_v2"
    assert set(body["voice_settings"]) >= {"stability", "similarity_boost"}
    assert len(body["text"]) <= 5000
    voices = tts.list_voices("elevenlabs", "xi", http=client)
    assert voices[0]["id"] == "v1" and calls[-1].url.path == "/v1/voices"


def test_elevenlabs_errors_are_readable():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401)))
    with pytest.raises(tts.TTSError, match="refused"):
        tts.synthesize("elevenlabs", "Hi.", voice="v", api_key="bad", http=client)


def test_openai_adapter_passes_instructions(monkeypatch):
    seen = {}

    class Speech:
        def create(self, **kw):
            seen.update(kw)
            return type("R", (), {"read": lambda self: b"OA"})()

    class Fake:
        def __init__(self, api_key=None, **_):
            self.audio = type("A", (), {"speech": Speech()})()

    import openai
    monkeypatch.setattr(openai, "OpenAI", Fake)
    assert tts.synthesize("openai", "Hello.", voice="coral", style="warm, slow", api_key="k") == b"OA"
    assert seen == {"model": "gpt-4o-mini-tts", "voice": "coral", "input": "Hello.",
                    "response_format": "mp3", "instructions": "warm, slow"}


# --------------------------------------------------------------- API

@pytest.fixture
def studio(client, project, monkeypatch):
    monkeypatch.setattr(audio_router, "SYNC", True)
    calls = []

    def fake_synth(provider, text, *, voice, api_key, style="", model="", http=None):
        calls.append((provider, voice, text))
        return fake_mp3(20)

    monkeypatch.setattr(tts, "synthesize", fake_synth)
    client.post("/api/settings/connections", json={"provider": "elevenlabs", "api_key": "xi"})
    pid = project["id"]
    iris = client.post(f"/api/projects/{pid}/codex", json={"kind": "character", "name": "Iris Vale"}).json()
    client.post(f"/api/projects/{pid}/chapters", json={"title": "One"})
    chs = client.get(f"/api/projects/{pid}/chapters").json()
    n = chs[0]["number"]
    client.patch(f"/api/projects/{pid}/chapters/{n}",
                 json={"text": 'The orchard was still.\n\n"Look," Iris said.\n\nThe glass rang.'})
    return {"pid": pid, "n": n, "iris": iris, "calls": calls}


def test_render_saves_track_and_skips_unchanged(client, studio):
    pid, n = studio["pid"], studio["n"]
    r = client.post(f"/api/projects/{pid}/audio/chapters/{n}/render")
    assert r.status_code == 400  # no narrator yet
    client.put(f"/api/projects/{pid}/audio/cast", json={"provider": "elevenlabs", "voice": "narr"})
    client.put(f"/api/projects/{pid}/audio/cast",
               json={"codex_entry_id": studio["iris"]["id"], "provider": "elevenlabs", "voice": "iris"})
    client.post(f"/api/projects/{pid}/audio/pronunciations", json={"term": "Iris", "say_as": "EYE-ris"})
    r = client.post(f"/api/projects/{pid}/audio/chapters/{n}/render").json()
    assert r["status"] == "done" and r["track"]["size"] > 0
    voices = [v for _, v, _ in studio["calls"]]
    assert voices == ["narr", "iris", "narr"]
    assert "EYE-ris said" in studio["calls"][2][2]
    again = client.post(f"/api/projects/{pid}/audio/chapters/{n}/render").json()
    assert again["status"] == "skipped" and again["track"]["id"] == r["track"]["id"]
    forced = client.post(f"/api/projects/{pid}/audio/chapters/{n}/render", json={"force": True}).json()
    assert forced["status"] == "done"
    rows = client.get(f"/api/projects/{pid}/audio/chapters").json()
    assert rows[0]["track"]["id"] == forced["track"]["id"]

    # Range streaming
    url = r["track"]["url"]
    full = client.get(url)
    assert full.status_code == 200 and full.headers["content-type"] == "audio/mpeg"
    assert "max-age" in full.headers["cache-control"]
    part = client.get(url, headers={"Range": "bytes=0-99"})
    assert part.status_code == 206 and len(part.content) == 100

    acx = client.get(f"/api/projects/{pid}/audio/acx?measure=false").json()
    checks = {c["key"]: c for c in acx["files"][0]["checks"]}
    assert checks["bitrate"]["ok"] is False and checks["sample_rate"]["ok"] is True
    assert checks["rms"]["ok"] is None and "Not measured" in checks["rms"]["detail"]
    assert acx["launch_checklist"]

    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/projects/{pid}/audio/export").content))
    assert "manifest.json" in z.namelist() and any(x.endswith(".mp3") for x in z.namelist())


def test_cast_pronunciations_and_suggest(client, studio):
    pid = studio["pid"]
    cast = client.get(f"/api/projects/{pid}/audio/cast").json()
    assert cast[0]["name"] == "Narrator" and cast[1]["name"] == "Iris Vale"
    p = client.post(f"/api/projects/{pid}/audio/pronunciations", json={"term": "Vale", "say_as": "VAYL"}).json()
    assert "Iris Vale" in client.get(f"/api/projects/{pid}/audio/pronunciations/suggest").json()
    assert client.delete(f"/api/projects/{pid}/audio/pronunciations/{p['id']}").status_code == 204
    provs = {x["id"]: x for x in client.get("/api/settings/audio-providers").json()}
    assert provs["elevenlabs"]["connected"] and not provs["openai"]["connected"]
    s = client.post(f"/api/projects/{pid}/audio/sample", json={"provider": "elevenlabs", "voice": "v"})
    assert s.status_code == 200 and s.headers["content-type"] == "audio/mpeg"


def test_audio_services_never_become_writing_default(client):
    for prov in ("elevenlabs", "openai_tts"):
        c = client.post("/api/settings/connections", json={"provider": prov, "api_key": "k", "is_default": True}).json()
        assert c["is_default"] is False
        assert client.post(f"/api/settings/connections/{c['id']}/default").status_code == 400
    listed = {p["id"]: p for p in client.get("/api/settings/providers").json()}
    assert listed["elevenlabs"]["capability"] == "audio"
