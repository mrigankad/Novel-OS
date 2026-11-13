"""
Text-to-speech: one interface, an adapter per service.

  openai      gpt-4o-mini-tts (fallback tts-1-hd) through the openai SDK,
              client.audio.speech.create(model, voice, input, response_format="mp3", instructions=...).
              `instructions` (narration tone) only works on gpt-4o-mini-tts. Input limit is 4096 chars,
              so we chunk at 4000.
  elevenlabs  POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128,
              header xi-api-key, JSON {text, model_id: "eleven_multilingual_v2", voice_settings}.
              GET /v1/voices lists the account's voices. We chunk at 5000.

Long text is split on paragraph, then sentence, then word boundaries, and the MP3 bytes of each
chunk are concatenated. MPEG audio is a stream of self-contained frames, so concatenated MP3s
play back correctly (a player may show a slightly off duration if a chunk carries an ID3/Xing header).

Credentials come from Connection rows ("openai_tts" or "openai", and "elevenlabs"). Keys never reach
the browser.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import httpx


class TTSError(Exception):
    pass


@dataclass
class TTSProvider:
    id: str
    label: str
    max_chars: int
    default_model: str
    voices: tuple[str, ...]  # built-in voices (ElevenLabs lists them per account)


OPENAI_VOICES = ("alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse")

PROVIDERS: dict[str, TTSProvider] = {
    "openai": TTSProvider("openai", "OpenAI TTS", 4000, "gpt-4o-mini-tts", OPENAI_VOICES),
    "elevenlabs": TTSProvider("elevenlabs", "ElevenLabs", 5000, "eleven_multilingual_v2", ()),
}
# Connection.provider ids that hold the key for each TTS provider, in preference order.
KEY_SOURCES = {"openai": ("openai_tts", "openai"), "elevenlabs": ("elevenlabs",)}

ELEVEN = "https://api.elevenlabs.io"
DEFAULT_VOICE_SETTINGS = {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True}

_SENTENCE = re.compile(r"(?<=[.!?…])[\"'”’)\]]*\s+")


def _split_hard(piece: str, limit: int) -> list[str]:
    """Split one over-long sentence on words (hard-cutting a giant word if needed)."""
    out, cur = [], ""
    for w in piece.split():
        while len(w) > limit:
            if cur:
                out.append(cur)
                cur = ""
            out.append(w[:limit])
            w = w[limit:]
        cand = f"{cur} {w}" if cur else w
        if len(cand) > limit:
            out.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        out.append(cur)
    return out


def chunk_text(text: str, limit: int) -> list[str]:
    """Chunks of at most `limit` chars, broken on paragraph, then sentence, then word boundaries."""
    if limit < 1:
        raise ValueError("limit must be positive")
    units: list[tuple[str, str]] = []  # (piece, joiner before it)
    for para in [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]:
        if len(para) <= limit:
            units.append((para, "\n\n"))
            continue
        first = True
        for sent in [s.strip() for s in re.split(r"(?<=[.!?…])\s+", para) if s.strip()]:
            for piece in ([sent] if len(sent) <= limit else _split_hard(sent, limit)):
                units.append((piece, "\n\n" if first else " "))
                first = False
    chunks: list[str] = []
    cur = ""
    for piece, joiner in units:
        cand = f"{cur}{joiner}{piece}" if cur else piece
        if len(cand) > limit:
            chunks.append(cur)
            cur = piece
        else:
            cur = cand
    if cur:
        chunks.append(cur)
    return chunks


def synthesize(provider: str, text: str, *, voice: str, api_key: str, style: str = "", model: str = "",
               http: Optional[httpx.Client] = None) -> bytes:
    """MP3 bytes for `text`, chunked and concatenated, or TTSError with a readable message."""
    if provider not in PROVIDERS:
        raise TTSError(f"{provider} can't read aloud.")
    if not api_key:
        raise TTSError(f"Add your {PROVIDERS[provider].label} key in Connections first.")
    if not voice:
        raise TTSError("Choose a voice first.")
    chunks = chunk_text(text, PROVIDERS[provider].max_chars)
    if not chunks:
        return b""
    try:
        if provider == "openai":
            return b"".join(_openai(c, voice, style, model, api_key) for c in chunks)
        own = http is None
        client = http or httpx.Client(timeout=120.0)
        try:
            return b"".join(_eleven(client, c, voice, model, api_key) for c in chunks)
        finally:
            if own:
                client.close()
    except TTSError:
        raise
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        hint = {401: "the key was refused", 402: "your account is out of credits",
                422: "the request was rejected", 429: "rate limited, try again in a minute"}.get(code, "")
        raise TTSError(f"{PROVIDERS[provider].label} returned HTTP {code}" + (f": {hint}" if hint else ".")) from e
    except httpx.HTTPError as e:
        raise TTSError(f"Couldn't reach {PROVIDERS[provider].label}: {e}") from e


def _openai(text: str, voice: str, style: str, model: str, key: str) -> bytes:
    from openai import OpenAI  # type: ignore

    client = OpenAI(api_key=key)
    model = model or "gpt-4o-mini-tts"
    kwargs: dict = {"model": model, "voice": voice, "input": text, "response_format": "mp3"}
    if style and model == "gpt-4o-mini-tts":
        kwargs["instructions"] = style
    try:
        resp = client.audio.speech.create(**kwargs)
    except Exception as e:  # noqa: BLE001 - fall back when the account lacks gpt-4o-mini-tts
        if model != "gpt-4o-mini-tts" or "model" not in str(e).lower():
            raise TTSError(f"OpenAI TTS failed: {str(e)[:200]}") from e
        kwargs.pop("instructions", None)
        kwargs["model"] = "tts-1-hd"
        resp = client.audio.speech.create(**kwargs)
    return resp.read() if hasattr(resp, "read") else resp.content


def _eleven(c: httpx.Client, text: str, voice_id: str, model: str, key: str) -> bytes:
    r = c.post(f"{ELEVEN}/v1/text-to-speech/{voice_id}", params={"output_format": "mp3_44100_128"},
               headers={"xi-api-key": key, "Accept": "audio/mpeg"},
               json={"text": text, "model_id": model or "eleven_multilingual_v2",
                     "voice_settings": DEFAULT_VOICE_SETTINGS})
    r.raise_for_status()
    return r.content


def list_voices(provider: str, api_key: str = "", http: Optional[httpx.Client] = None) -> list[dict]:
    if provider == "openai":
        return [{"id": v, "name": v.capitalize(), "hint": ""} for v in OPENAI_VOICES]
    if provider != "elevenlabs" or not api_key:
        return []
    own = http is None
    client = http or httpx.Client(timeout=20.0)
    try:
        r = client.get(f"{ELEVEN}/v1/voices", headers={"xi-api-key": api_key})
        r.raise_for_status()
        return [{"id": v.get("voice_id"), "name": v.get("name") or v.get("voice_id"),
                 "hint": ", ".join(str(x) for x in (v.get("labels") or {}).values())[:80]}
                for v in (r.json() or {}).get("voices", []) if v.get("voice_id")]
    except httpx.HTTPError as e:
        raise TTSError(f"Couldn't list ElevenLabs voices: {e}") from e
    finally:
        if own:
            client.close()
