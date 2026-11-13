"""Image generation: adapters (fake HTTP, no network/credits), Media filing, safeguards."""

import json

import httpx
import pytest

from server import imagegen
from server.routers import images as images_router

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
       b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82")


def transport(routes):
    calls = []

    def handler(req: httpx.Request):
        calls.append(req)
        for (method, frag), resp in routes.items():
            if req.method == method and frag in str(req.url):
                body = resp.pop(0) if isinstance(resp, list) else resp
                return httpx.Response(200, json=body)
        return httpx.Response(404, json={"error": "no route"})

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_runway_submits_then_polls_until_succeeded():
    client, calls = transport({
        ("POST", "/v1/text_to_image"): {"id": "task1"},
        ("GET", "/v1/tasks/task1"): [{"status": "RUNNING"}, {"status": "SUCCEEDED", "output": ["https://cdn/x.png"]}],
    })
    data = imagegen.generate("runway", "a glass orchard", aspect="2:3", api_key="rk", http=client,
                             sleep=lambda s: None, download=lambda url: PNG)
    assert data == PNG
    sent = json.loads(calls[0].content)
    assert sent == {"model": "gen4_image", "promptText": "a glass orchard", "ratio": "1080:1620"}
    assert calls[0].headers["X-Runway-Version"] == "2024-11-06"
    assert calls[0].headers["Authorization"] == "Bearer rk"


def test_higgsfield_uses_key_auth_and_reads_images_url():
    client, calls = transport({
        ("POST", "/higgsfield-ai/soul/v2/standard"): {"request_id": "r1", "status": "queued"},
        ("GET", "/requests/r1/status"): [{"status": "in_progress"}, {"status": "completed", "images": [{"url": "https://h/i.png"}]}],
    })
    got = imagegen.generate("higgsfield", "wasps at dusk", api_key="id:secret", http=client,
                            sleep=lambda s: None, download=lambda url: PNG)
    assert got == PNG
    assert calls[0].headers["Authorization"] == "Key id:secret"
    assert calls[0].headers.get("Idempotency-Key")


def test_higgsfield_nsfw_and_bad_key_are_readable():
    client, _ = transport({
        ("POST", "/higgsfield-ai"): {"request_id": "r2"},
        ("GET", "/requests/r2/status"): {"status": "nsfw"},
    })
    with pytest.raises(imagegen.ImageGenError, match="unsafe"):
        imagegen.generate("higgsfield", "x y z", api_key="a:b", http=client, sleep=lambda s: None)
    with pytest.raises(imagegen.ImageGenError, match="KEY_ID:KEY_SECRET"):
        imagegen.generate("higgsfield", "x y z", api_key="nocolon")


def test_http_errors_are_explained():
    def handler(req):
        return httpx.Response(402, json={})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(imagegen.ImageGenError, match="out of credits"):
        imagegen.generate("runway", "x y z", api_key="k", http=client, sleep=lambda s: None)


def test_generate_files_into_media_and_sets_portrait(client, project, monkeypatch):
    pid = project["id"]
    client.post("/api/settings/connections", json={"provider": "runway", "api_key": "rk"})
    entry = client.post(f"/api/projects/{pid}/codex", json={"kind": "character", "name": "Iris Vale",
                                                           "summary": "Grey-eyed, stubborn"}).json()
    monkeypatch.setattr(images_router, "SYNC", True)
    seen = {}

    def fake_generate(provider, prompt, **kw):
        seen.update(provider=provider, prompt=prompt, **kw)
        return PNG

    monkeypatch.setattr(imagegen, "generate", fake_generate)
    r = client.post(f"/api/projects/{pid}/images", json={"prompt": "Portrait of Iris", "kind": "portrait",
                                                        "aspect": "3:4", "codex_entry_id": entry["id"]})
    assert r.status_code == 202, r.text
    media_id = r.json()["media_id"]
    assert seen["provider"] == "runway" and seen["api_key"] == "rk" and seen["aspect"] == "3:4"
    media = client.get(f"/api/projects/{pid}/media").json()
    item = next(m for m in (media if isinstance(media, list) else media["items"]) if m["id"] == media_id)
    assert item["source"] == "generated" and item["kind"] == "portrait"
    assert client.get(f"/api/projects/{pid}/codex/{entry['id']}").json()["image_media_id"] == media_id


def test_prompt_drafts_from_the_book(client, project):
    pid = project["id"]
    cover = client.post(f"/api/projects/{pid}/images/prompt", json={"kind": "cover"}).json()
    assert "The Glass Orchard" in cover["prompt"] and cover["aspect"] == "2:3"
    assert "no text" in cover["prompt"]


def test_image_services_never_become_the_writing_default(client):
    r = client.post("/api/settings/connections", json={"provider": "runway", "api_key": "rk"}).json()
    assert r["is_default"] is False
    assert client.post(f"/api/settings/connections/{r['id']}/default").status_code == 400
    providers = {p["id"]: p for p in client.get("/api/settings/image-providers").json()}
    assert providers["runway"]["connected"] is True and providers["higgsfield"]["connected"] is False
    assert "rk" not in json.dumps(providers)


def test_no_image_service_connected_is_explained(client, project):
    r = client.post(f"/api/projects/{project['id']}/images", json={"prompt": "a cover please"})
    assert r.status_code == 400 and "Connect an image service" in r.json()["detail"]


def test_google_flow_via_useapi_reads_fife_url_and_pins_account():
    client, calls = transport({
        ("POST", "/v1/google-flow/images"): {"jobId": "j1", "media": [
            {"image": {"generatedImage": {"fifeUrl": "https://flow/signed.png", "seed": 7}}}]},
    })
    got = imagegen.generate("google_flow", "frost on glass apples", aspect="2:3", api_key="tok",
                            base_url="iris@example.com", http=client, download=lambda url: PNG)
    assert got == PNG
    body = json.loads(calls[0].content)
    assert body == {"prompt": "frost on glass apples", "model": "nano-banana-2", "aspectRatio": "3:4",
                    "count": 1, "email": "iris@example.com"}
    assert calls[0].headers["Authorization"] == "Bearer tok"


def test_google_flow_base64_and_rate_limit():
    import base64 as b64
    client, _ = transport({
        ("POST", "/v1/google-flow/images"): {"media": [{"image": {"generatedImage": {"encodedImage": b64.b64encode(PNG).decode()}}}]},
    })
    assert imagegen.generate("google_flow", "a map", api_key="tok", http=client) == PNG

    limited = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(429, json={})))
    with pytest.raises(imagegen.ImageGenError, match="rate-limiting"):
        imagegen.generate("google_flow", "a map", api_key="tok", http=limited)
