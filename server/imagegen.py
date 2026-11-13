"""
Image generation: covers, character portraits, maps and scene art.

One interface, several services. Each adapter takes a prompt and an aspect
ratio and returns image bytes; the router stores them as Media so they're
immediately usable as cover art or Codex portraits.

  google      Gemini image models (Nano Banana, the models behind Google Flow).
              Google has no public Flow API, so this is the official route.
  openai      gpt-image-1 via the Images API.
  runway      Runway API: POST /v1/text_to_image, poll /v1/tasks/{id}.
  higgsfield  Higgsfield Cloud API: POST /<model>, poll /requests/{id}/status.
  google_flow Google Flow through useapi.net (UNOFFICIAL: Google has no Flow API;
              useapi.net drives your own Flow account, using your Google AI plan's credits).

Credentials come from the matching Connection row (provider ids "gemini",
"openai", "runway", "higgsfield"); keys never leave the server.
"""

from __future__ import annotations

import base64
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

import httpx

ASPECTS = ("1:1", "2:3", "3:2", "3:4", "4:3", "9:16", "16:9")
POLL_EVERY_S = 2.0
TIMEOUT_S = 240.0


class ImageGenError(Exception):
    pass


@dataclass
class ImageProvider:
    id: str               # matches Connection.provider
    label: str
    default_model: str
    models: tuple[str, ...]
    notes: str


PROVIDERS: dict[str, ImageProvider] = {
    "gemini": ImageProvider("gemini", "Google (Nano Banana, as in Flow)", "gemini-nano-banana-2.1",
                            ("gemini-nano-banana-2.1", "gemini-3-pro-image", "gemini-3.1-flash-lite-image"),
                            "Uses your Gemini API key. These are the image models Google Flow runs on."),
    "openai": ImageProvider("openai", "OpenAI Images", "gpt-image-1", ("gpt-image-1",),
                            "Uses your OpenAI API key."),
    "runway": ImageProvider("runway", "Runway", "gen4_image", ("gen4_image",),
                            "Runway API key from dev.runwayml.com."),
    "google_flow": ImageProvider("google_flow", "Google Flow (via useapi.net)", "nano-banana-2",
                                 ("nano-banana-2", "nano-banana-pro", "nano-banana-2-lite"),
                                 "Unofficial: useapi.net drives your own Google Flow account with your Google AI "
                                 "plan's credits. Needs a useapi.net token. Google may rate-limit the account."),
    "higgsfield": ImageProvider("higgsfield", "Higgsfield", "higgsfield-ai/soul/v2/standard",
                                ("higgsfield-ai/soul/v2/standard",),
                                "Key ID and secret from cloud.higgsfield.ai, entered as KEY_ID:KEY_SECRET."),
}

# Runway takes pixel ratios, not aspect names.
RUNWAY_RATIOS = {"1:1": "1024:1024", "2:3": "1080:1620", "3:2": "1620:1080", "3:4": "1080:1440",
                 "4:3": "1440:1080", "9:16": "1080:1920", "16:9": "1920:1080"}
# Flow only has these shapes; map ours to the nearest.
FLOW_ASPECTS = {"1:1": "1:1", "2:3": "3:4", "3:4": "3:4", "9:16": "9:16", "3:2": "4:3", "4:3": "4:3", "16:9": "16:9"}
OPENAI_SIZES = {"1:1": "1024x1024", "2:3": "1024x1536", "3:4": "1024x1536", "9:16": "1024x1536",
                "3:2": "1536x1024", "4:3": "1536x1024", "16:9": "1536x1024"}

Fetch = Callable[[str], bytes]


def _download(url: str) -> bytes:
    with httpx.Client(timeout=60.0, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.content


def generate(provider: str, prompt: str, *, aspect: str = "2:3", model: str = "", api_key: str = "",
             base_url: str = "", http: Optional[httpx.Client] = None, sleep=time.sleep,
             download: Fetch = _download) -> bytes:
    """Return the image bytes for one generation, or raise ImageGenError with a readable message."""
    if provider not in PROVIDERS:
        raise ImageGenError(f"{provider} can't generate images.")
    if not prompt.strip():
        raise ImageGenError("Describe the image first.")
    aspect = aspect if aspect in ASPECTS else "2:3"
    model = model or PROVIDERS[provider].default_model
    if not api_key:
        raise ImageGenError(f"Add your {PROVIDERS[provider].label} key in Connections first.")
    try:
        if provider == "gemini":
            return _google(prompt, aspect, model, api_key)
        if provider == "openai":
            return _openai(prompt, aspect, model, api_key, base_url)
        own = http is None
        client = http or httpx.Client(timeout=30.0)
        try:
            if provider == "google_flow":
                return _google_flow(client, prompt, aspect, model, api_key, base_url, download)
            if provider == "runway":
                return _runway(client, prompt, aspect, model, api_key, sleep, download)
            return _higgsfield(client, prompt, model, api_key, sleep, download)
        finally:
            if own:
                client.close()
    except ImageGenError:
        raise
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        hint = {401: "the key was refused", 403: "the key isn't allowed to do this",
                402: "your account is out of credits", 429: "rate limited, try again in a minute"}.get(code, "")
        raise ImageGenError(f"{PROVIDERS[provider].label} returned HTTP {code}" + (f": {hint}" if hint else ".")) from e
    except httpx.HTTPError as e:
        raise ImageGenError(f"Couldn't reach {PROVIDERS[provider].label}: {e}") from e


# --------------------------------------------------------------------------- adapters

def _google(prompt: str, aspect: str, model: str, key: str) -> bytes:
    from google import genai  # type: ignore

    client = genai.Client(api_key=key)
    if hasattr(client, "interactions"):  # current SDKs: Interactions API
        out = client.interactions.create(
            model=model, input=prompt,
            response_format={"type": "image", "mime_type": "image/png", "aspect_ratio": aspect},
        )
        data = getattr(getattr(out, "output_image", None), "data", None)
        if data:
            return base64.b64decode(data) if isinstance(data, str) else data
    # Older SDKs: generate_content with image output.
    from google.genai import types  # type: ignore

    resp = client.models.generate_content(
        model=model, contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"],
                                           image_config=types.ImageConfig(aspect_ratio=aspect)),
    )
    for cand in resp.candidates or []:
        for part in (cand.content.parts if cand.content else []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return inline.data
    raise ImageGenError("Google returned no image (the prompt may have been blocked).")


def _openai(prompt: str, aspect: str, model: str, key: str, base_url: str) -> bytes:
    from openai import OpenAI  # type: ignore

    client = OpenAI(api_key=key, base_url=base_url or None)
    resp = client.images.generate(model=model, prompt=prompt, size=OPENAI_SIZES[aspect], n=1)
    item = resp.data[0]
    if getattr(item, "b64_json", None):
        return base64.b64decode(item.b64_json)
    if getattr(item, "url", None):
        return _download(item.url)
    raise ImageGenError("OpenAI returned no image.")


def _google_flow(c: httpx.Client, prompt: str, aspect: str, model: str, token: str, account: str,
                 download) -> bytes:
    """useapi.net's Flow wrapper. Synchronous: the response already holds the image.
    `account` (the connection's base_url field) optionally pins one Google account email."""
    body: dict = {"prompt": prompt, "model": model, "aspectRatio": FLOW_ASPECTS[aspect], "count": 1}
    if account and "@" in account:
        body["email"] = account.strip()
    r = c.post("https://api.useapi.net/v1/google-flow/images", json=body, timeout=180.0,
               headers={"Authorization": f"Bearer {token}"})
    if r.status_code == 429:
        raise ImageGenError("Google is rate-limiting your Flow account right now. Try again in a few minutes.")
    r.raise_for_status()
    media = (r.json() or {}).get("media") or []
    img = (media[0].get("image") or {}).get("generatedImage") if media else None
    if not img:
        raise ImageGenError("Google Flow returned no image (the prompt may have been blocked).")
    if img.get("fifeUrl"):
        return download(img["fifeUrl"])
    if img.get("encodedImage"):
        return base64.b64decode(img["encodedImage"])
    raise ImageGenError("Google Flow returned an image with no data.")


def _runway(c: httpx.Client, prompt: str, aspect: str, model: str, key: str, sleep, download) -> bytes:
    base = "https://api.dev.runwayml.com"
    headers = {"Authorization": f"Bearer {key}", "X-Runway-Version": "2024-11-06"}
    r = c.post(f"{base}/v1/text_to_image", headers=headers,
               json={"model": model, "promptText": prompt[:1000], "ratio": RUNWAY_RATIOS[aspect]})
    r.raise_for_status()
    task_id = r.json()["id"]
    deadline = time.monotonic() + TIMEOUT_S
    while time.monotonic() < deadline:
        t = c.get(f"{base}/v1/tasks/{task_id}", headers=headers)
        t.raise_for_status()
        body = t.json()
        status = str(body.get("status", "")).upper()
        if status == "SUCCEEDED":
            out = body.get("output") or []
            if not out:
                raise ImageGenError("Runway finished but returned no image.")
            return download(out[0])
        if status in ("FAILED", "CANCELLED"):
            raise ImageGenError(f"Runway: {body.get('failure') or status.lower()}")
        sleep(POLL_EVERY_S)
    raise ImageGenError("Runway took too long. Try again.")


def _higgsfield(c: httpx.Client, prompt: str, model: str, key: str, sleep, download) -> bytes:
    if ":" not in key:
        raise ImageGenError("Enter the Higgsfield key as KEY_ID:KEY_SECRET.")
    base = "https://api.higgsfield.ai"
    headers = {"Authorization": f"Key {key}", "Idempotency-Key": uuid.uuid4().hex}
    r = c.post(f"{base}/{model.strip('/')}", headers=headers, json={"prompt": prompt})
    r.raise_for_status()
    rid = r.json()["request_id"]
    auth = {"Authorization": f"Key {key}"}
    deadline = time.monotonic() + TIMEOUT_S
    while time.monotonic() < deadline:
        s = c.get(f"{base}/requests/{rid}/status", headers=auth)
        s.raise_for_status()
        body = s.json()
        status = body.get("status")
        if status == "completed":
            images = body.get("images") or []
            if not images or not images[0].get("url"):
                raise ImageGenError("Higgsfield finished but returned no image.")
            return download(images[0]["url"])
        if status == "nsfw":
            raise ImageGenError("Higgsfield declined this prompt as unsafe.")
        if status in ("failed", "canceled"):
            raise ImageGenError(f"Higgsfield: generation {status}.")
        sleep(POLL_EVERY_S)
    raise ImageGenError("Higgsfield took too long. Try again.")
