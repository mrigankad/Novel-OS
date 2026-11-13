"""Deterministic voice traits, computed in pure Python. Fast and LLM-free."""

from __future__ import annotations

import re
from collections import Counter
from statistics import mean, pstdev

from core.style_stats import _STOP, tokenize

_SENT_RE = re.compile(r"[^.!?…]+(?:[.!?…]+[\"'”’)]*|$)")
_QUOTE_RE = re.compile(r"[\"“”]")

BURST_MAX = 5  # sentences of <= 5 words count as bursts

ADVERB_STOP = frozenset("""
only early family really likely holy belly jelly ugly lonely lovely friendly silly
daily weekly monthly yearly reply supply apply fly ally rally bully lily july italy
sly wily oily curly hilly chilly smelly costly deadly elderly kindly lively
manly orderly unlikely ghostly cowardly
""".split())

FILTER_WORDS = frozenset("""
felt feel feels feeling saw see sees seeing heard hear hears hearing noticed notice notices
realized realize realizes realised wondered wonder wonders thought think thinks
knew know knows decided seemed seem seems looked watched watch watches smelled tasted
""".split())

SENSES: dict[str, frozenset[str]] = {
    "sight": frozenset("""see saw seen look looked looking watch watched stare stared glance glanced
        light dark shadow shadows bright dim color colour red blue green gold white black grey gray
        glow glowed gleam glint shine shone gaze""".split()),
    "sound": frozenset("""hear heard sound sounds noise loud quiet silence silent whisper whispered
        hum hummed ring rang creak creaked buzz buzzed echo echoed shout shouted murmur click
        crack thud roar""".split()),
    "touch": frozenset("""touch touched cold warm hot rough smooth soft hard sharp wet dry
        skin grip gripped pressed brush brushed ache ached sting stung heavy weight
        texture""".split()),
    "smell": frozenset("""smell smelled smelt scent scented odor odour stink stank reek reeked
        fragrance perfume musk smoke smoky rot rotten sniff sniffed""".split()),
    "taste": frozenset("""taste tasted tongue sweet bitter sour salt salty savory savoury flavor
        flavour bite chew chewed swallow swallowed honey""".split()),
}

INTERIORITY = frozenset("""
thought wondered wanted hoped feared knew remembered imagined wished believed supposed
maybe perhaps somehow probably surely
""".split())

FIRST = frozenset("i me my mine myself we us our".split())
SECOND = frozenset("you your yours yourself".split())
THIRD = frozenset("he him his she her hers they them their himself herself".split())
PAST_MARK = frozenset("was were had did said went came looked felt thought".split())
PRESENT_MARK = frozenset("is are has does says goes comes looks feels thinks am".split())


def paragraphs(text: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n", text or "")]
    return [p for p in paras if p and not p.startswith("#")]


def sentences(text: str) -> list[str]:
    out: list[str] = []
    for para in paragraphs(text):
        out += [s.strip() for s in _SENT_RE.findall(para) if tokenize(s)]
    return out


def _per_k(n: int, words: int) -> float:
    return round(n * 1000 / words, 2) if words else 0.0


def mtld(tokens: list[str], threshold: float = 0.72) -> float:
    """Measure of Textual Lexical Diversity (forward and backward average)."""
    if len(tokens) < 10:
        return float(len(set(tokens)))

    def one(seq: list[str]) -> float:
        factors, types, count = 0.0, set(), 0
        for t in seq:
            count += 1
            types.add(t)
            if len(types) / count <= threshold:
                factors += 1
                types, count = set(), 0
        if count:
            ttr = len(types) / count
            factors += (1 - ttr) / (1 - threshold)
        return len(seq) / factors if factors else float(len(seq))

    return round((one(tokens) + one(tokens[::-1])) / 2, 1)


def compute_traits(text: str) -> dict:
    """Every measured trait for a body of prose."""
    tokens = tokenize(text)
    words = len(tokens)
    sents = sentences(text)
    lens = [len(tokenize(s)) for s in sents] or [0]
    paras = paragraphs(text)
    para_lens = [len(tokenize(p)) for p in paras] or [0]

    dialogue = sum(1 for p in paras if _QUOTE_RE.search(p))
    adverbs = sum(1 for t in tokens if t.endswith("ly") and len(t) > 4 and t not in ADVERB_STOP)
    filters = sum(1 for t in tokens if t in FILTER_WORDS)
    inter = sum(1 for t in tokens if t in INTERIORITY)

    sense_counts = {k: sum(1 for t in tokens if t in lex) for k, lex in SENSES.items()}
    total_s = sum(sense_counts.values())
    sensory = {k: round(v / total_s, 3) if total_s else 0.0 for k, v in sense_counts.items()}

    # POV and tense from narration only (quoted dialogue stripped).
    narration = tokenize(re.sub(r"[\"“][^\"”]*[\"”]", " ", text or ""))
    c = Counter(narration)
    p1, p2, p3 = (sum(c[w] for w in s) for s in (FIRST, SECOND, THIRD))
    pov = "first" if p1 > max(p3 * 0.6, p2) else "second" if p2 > max(p1, p3) else "third"
    past, present = sum(c[w] for w in PAST_MARK), sum(c[w] for w in PRESENT_MARK)
    tense = "present" if present > past else "past"

    content = [t for t in tokens if t not in _STOP and len(t) > 2]
    bigrams = Counter(zip(content, content[1:]))
    top_bi = [f"{a} {b}" for (a, b), n in bigrams.most_common(8) if n > 1][:6]
    openers = Counter(tokenize(s)[0] for s in sents)
    top_open = [{"word": w, "share": round(n / len(sents), 3)} for w, n in openers.most_common(5)] if sents else []

    raw = text or ""
    return {
        "words": words,
        "sentence_len": {"mean": round(mean(lens), 1), "sd": round(pstdev(lens), 1)},
        "burst_rate": round(sum(1 for n in lens if 0 < n <= BURST_MAX) / len(sents), 3) if sents else 0.0,
        "paragraph_len": round(mean(para_lens), 1),
        "dialogue_ratio": round(dialogue / len(paras), 3) if paras else 0.0,
        "adverbs_per_1k": _per_k(adverbs, words),
        "filter_words_per_1k": _per_k(filters, words),
        "interiority_per_1k": _per_k(inter, words),
        "sensory": sensory,
        "pov": pov,
        "tense": tense,
        "lexical_diversity": mtld(tokens),
        "punctuation": {
            "em_dash_per_1k": _per_k(len(re.findall(r"—|--", raw)), words),
            "semicolon_per_1k": _per_k(raw.count(";"), words),
            "ellipsis_per_1k": _per_k(len(re.findall(r"…|\.\.\.", raw)), words),
        },
        "bigrams": top_bi,
        "openers": top_open,
    }


# --------------------------------------------------------------- matching

def _g(path: str):
    def get(t: dict) -> float:
        v: object = t
        for k in path.split("."):
            v = v.get(k, 0) if isinstance(v, dict) else 0
        return float(v or 0)
    return get


# key, label, getter, scale (difference that counts as fully off), weight, display kind
TRAITS = [
    ("sentence_len", "Sentence length", _g("sentence_len.mean"), 8.0, 1.5, "words"),
    ("sentence_sd", "Sentence variety", _g("sentence_len.sd"), 6.0, 1.0, "num"),
    ("burst_rate", "Short bursts", _g("burst_rate"), 0.2, 1.0, "pct"),
    ("paragraph_len", "Paragraph length", _g("paragraph_len"), 40.0, 1.0, "words"),
    ("dialogue_ratio", "Dialogue", _g("dialogue_ratio"), 0.25, 1.5, "pct"),
    ("adverbs_per_1k", "Adverbs", _g("adverbs_per_1k"), 10.0, 0.8, "per1k"),
    ("filter_words_per_1k", "Filter words", _g("filter_words_per_1k"), 8.0, 0.8, "per1k"),
    ("interiority_per_1k", "Interiority", _g("interiority_per_1k"), 8.0, 0.8, "per1k"),
    ("lexical_diversity", "Lexical diversity", _g("lexical_diversity"), 50.0, 0.8, "num"),
    ("em_dash_per_1k", "Em dashes", _g("punctuation.em_dash_per_1k"), 6.0, 0.5, "per1k"),
    ("semicolon_per_1k", "Semicolons", _g("punctuation.semicolon_per_1k"), 3.0, 0.4, "per1k"),
    ("sight", "Sight", _g("sensory.sight"), 0.4, 0.3, "pct"),
    ("sound", "Sound", _g("sensory.sound"), 0.4, 0.3, "pct"),
    ("touch", "Touch", _g("sensory.touch"), 0.4, 0.3, "pct"),
]


def _fmt(v: float, kind: str) -> str:
    if kind == "pct":
        return f"{round(v * 100)}%"
    if kind == "per1k":
        return f"{v:.1f}/1k"
    if kind == "words":
        return f"{v:.0f} words"
    return f"{v:.0f}" if v >= 10 else f"{v:.1f}"


def _gap_sentence(key: str, label: str, you: str, draft: str, higher: bool, who: str) -> str:
    plain = {
        "dialogue_ratio": f"{who} needs to talk {'less' if higher else 'more'}",
        "sentence_len": "sentences run long; break some up" if higher else "sentences are clipped; let some breathe",
        "burst_rate": "there are too many short punches" if higher else "add short, falling sentences",
        "paragraph_len": "paragraphs are heavy; split them" if higher else "paragraphs are thin; let them build",
        "adverbs_per_1k": "cut adverbs and use stronger verbs" if higher else "a few more modifiers would sound like you",
        "filter_words_per_1k": "strip filter words like felt, saw, heard" if higher else "it filters less than you do",
        "interiority_per_1k": "spend less time in the head, more in action" if higher else "go further into the character's head",
    }.get(key, "pull this back toward your samples" if higher else "lean into this more")
    return f"{label} is {draft} vs your {you}, so {plain}."


def match(you: dict, draft: dict, *, who: str = "the POV character") -> dict:
    """0-100 similarity: weighted normalized distance per trait, plus plain-language gaps."""
    rows, num, den = [], 0.0, 0.0
    for key, label, get, scale, weight, kind in TRAITS:
        a, b = get(you), get(draft)
        d = min(1.0, abs(a - b) / scale)
        num += weight * d
        den += weight
        rows.append({"key": key, "label": label, "you": a, "draft": b, "you_label": _fmt(a, kind),
                     "draft_label": _fmt(b, kind), "gap": round(d, 3), "large": d >= 0.5,
                     "weight": weight})
    gaps: list[str] = []
    for k in ("pov", "tense"):
        den += 1.0
        if you.get(k) and draft.get(k) and you[k] != draft[k]:
            num += 1.0
            gaps.append(f"The draft reads as {draft[k]} {'person' if k == 'pov' else 'tense'}; you write {you[k]}.")
    score = round(100 * (1 - num / den)) if den else 100
    ranked = sorted((r for r in rows if r["gap"] >= 0.15), key=lambda r: -r["gap"] * r["weight"])
    gaps += [_gap_sentence(r["key"], r["label"], r["you_label"], r["draft_label"], r["draft"] > r["you"], who)
             for r in ranked]
    return {"score": max(0, min(100, score)), "traits": rows, "gaps": gaps[:3]}
