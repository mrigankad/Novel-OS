"""
Chapter rendering helpers: dialogue attribution, voice segments, MP3 inspection and the ACX check.

Attribution is deliberately conservative. A paragraph's quotes go to a character only when the
tag right after the first quote names a cast character (`"…," Iris said` / `"…" said Iris` /
`"…?" Iris asked`). Pronouns, unknown names, or quotes without a tag stay with the narrator.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

WPM = 155
VERBS = ("said", "asked", "replied", "whispered", "called", "shouted", "murmured", "answered", "added",
         "snapped", "cried", "muttered", "told", "says", "asks")
_QUOTE = re.compile(r"[\"“]([^\"”]+)[\"”]")
_VERB = "|".join(VERBS)


def text_sha(text: str, *extra: str) -> str:
    h = hashlib.sha256((text or "").encode("utf-8"))
    for e in extra:
        h.update(b"\x00" + (e or "").encode("utf-8"))
    return h.hexdigest()


def strip_markdown(text: str) -> str:
    t = re.sub(r"^#{1,6}\s*", "", text or "", flags=re.M)
    t = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", t)
    t = re.sub(r"^\s*([-*_]\s*){3,}$", "", t, flags=re.M)  # scene breaks
    return t


def speaker_for(paragraph: str, names: dict[str, str]) -> Optional[str]:
    """Cast key of the attributed speaker, or None (narrator) when unsure.
    `names` maps lowercase names/first names/aliases to a cast key."""
    m = _QUOTE.search(paragraph)
    if not m or not names:
        return None
    after = paragraph[m.end():m.end() + 60]
    tag = re.match(rf"\s*(?:({_VERB})\s+([A-Z][\w'-]*(?:\s[A-Z][\w'-]*)?)|([A-Z][\w'-]*(?:\s[A-Z][\w'-]*)?)\s+({_VERB}))\b",
                   after)
    if not tag:
        return None
    who = (tag.group(2) or tag.group(3) or "").strip()
    for cand in (who, who.split()[0]):
        key = names.get(cand.lower())
        if key:
            return key
    return None


def segments(text: str, names: dict[str, str]) -> list[tuple[Optional[str], str]]:
    """[(cast key or None for narrator, text)], consecutive same-voice runs merged."""
    out: list[tuple[Optional[str], str]] = []

    def push(key: Optional[str], piece: str, sep: str) -> None:
        piece = piece.strip()
        if not piece:
            return
        if out and out[-1][0] == key:
            out[-1] = (key, out[-1][1] + sep + piece)
        else:
            out.append((key, piece))

    for para in [p.strip() for p in re.split(r"\n\s*\n", strip_markdown(text)) if p.strip()]:
        who = speaker_for(para, names)
        if who is None:
            push(None, para, "\n\n")
            continue
        pos, first = 0, True
        for m in _QUOTE.finditer(para):
            push(None, para[pos:m.start()], "\n\n" if first else " ")
            push(who, m.group(1), "\n\n" if first and not para[:m.start()].strip() else " ")
            pos, first = m.end(), False
        push(None, para[pos:].lstrip(" ,"), " ")
    return out


def estimate_seconds(text: str) -> float:
    return round(len((text or "").split()) / WPM * 60, 1)


# --------------------------------------------------------------- MP3 inspection (no deps)

_BITRATES = {  # MPEG-1 / MPEG-2(.5) Layer III, kbps
    1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
}
_RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def mp3_info(data: bytes) -> dict:
    """Walk Layer III frames: duration, bitrates seen (CBR if one), sample rate."""
    i = 0
    if data[:3] == b"ID3" and len(data) > 10:
        size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
        i = 10 + size
    frames, seconds, rates, bitrates = 0, 0.0, set(), set()
    n = len(data)
    while i + 4 <= n:
        if data[i] != 0xFF or (data[i + 1] & 0xE0) != 0xE0:
            i += 1
            continue
        b1, b2 = data[i + 1], data[i + 2]
        version = (b1 >> 3) & 3  # 3 = MPEG1, 2 = MPEG2, 0 = MPEG2.5
        layer = (b1 >> 1) & 3   # 1 = Layer III
        br_idx, sr_idx, pad = (b2 >> 4) & 15, (b2 >> 2) & 3, (b2 >> 1) & 1
        if version == 1 or layer != 1 or br_idx in (0, 15) or sr_idx == 3:
            i += 1
            continue
        kbps = _BITRATES[1 if version == 3 else 2][br_idx]
        sr = _RATES[version][sr_idx]
        samples = 1152 if version == 3 else 576
        length = (samples // 8) * kbps * 1000 // sr + pad
        if length < 4:
            i += 1
            continue
        frames += 1
        seconds += samples / sr
        rates.add(sr)
        bitrates.add(kbps)
        i += length
    return {"frames": frames, "duration_s": round(seconds, 1), "sample_rates": sorted(rates),
            "bitrates": sorted(bitrates), "cbr": len(bitrates) == 1}


def loudness(path: str) -> Optional[dict]:
    """RMS, peak and noise floor in dBFS via pydub + ffmpeg, or None when unavailable."""
    try:
        from pydub import AudioSegment  # type: ignore

        seg = AudioSegment.from_file(path, format="mp3")
    except Exception:  # noqa: BLE001 - pydub or ffmpeg missing, or undecodable
        return None
    chunks = [seg[i:i + 500].dBFS for i in range(0, len(seg), 500)]
    finite = sorted(c for c in chunks if c != float("-inf"))
    floor = finite[max(0, len(finite) // 20)] if finite else float("-inf")
    return {"rms_db": round(seg.dBFS, 1), "peak_db": round(seg.max_dBFS, 1),
            "noise_floor_db": round(floor, 1) if finite else None}


def acx_check(path: str, data: bytes, measure: bool = True) -> dict:
    """Check one chapter file against ACX's published requirements."""
    info = mp3_info(data)
    checks = []

    def add(key: str, label: str, ok: Optional[bool], detail: str) -> None:
        checks.append({"key": key, "label": label, "ok": ok, "detail": detail})

    br = info["bitrates"]
    add("bitrate", "192 kbps or higher, constant bitrate", (bool(br) and info["cbr"] and br[0] >= 192) if br else None,
        f"{'/'.join(map(str, br))} kbps{' CBR' if info['cbr'] else ' VBR'}" if br else "Couldn't read frames")
    sr = info["sample_rates"]
    add("sample_rate", "44.1 kHz sample rate", sr == [44100] if sr else None,
        f"{'/'.join(str(s) for s in sr)} Hz" if sr else "Couldn't read frames")
    add("length", "Each file 120 minutes or shorter", info["duration_s"] <= 7200,
        f"{info['duration_s'] / 60:.1f} min")
    lv = loudness(path) if measure else None
    if lv is None:
        for key, label in (("rms", "RMS between -23 and -18 dB"), ("peak", "Peaks at or below -3 dB"),
                           ("noise", "Noise floor at or below -60 dB")):
            add(key, label, None, "Not measured (needs pydub and ffmpeg)")
    else:
        add("rms", "RMS between -23 and -18 dB", -23 <= lv["rms_db"] <= -18, f"{lv['rms_db']} dB")
        add("peak", "Peaks at or below -3 dB", lv["peak_db"] <= -3, f"{lv['peak_db']} dB")
        nf = lv["noise_floor_db"]
        add("noise", "Noise floor at or below -60 dB", None if nf is None else nf <= -60,
            "silent" if nf is None else f"{nf} dB (quietest 5% of half-seconds)")
    return {"info": info, "checks": checks}


LAUNCH_CHECKLIST = [
    "Opening credits: title, author and narrator read at the start of the first file",
    "Closing credits: 'The end' and the same names at the end of the last file",
    "0.5 to 1 second of room tone at the head and 1 to 5 seconds at the tail of each file",
    "One chapter per file, each announcing its chapter title",
    "A retail sample of 1 to 5 minutes, no explicit content",
    "Square cover art, at least 2400 x 2400 px",
    "Disclose AI narration where the retailer requires it (ACX and Audible have rules for synthetic voices)",
]
