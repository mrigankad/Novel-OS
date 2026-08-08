"""Extract Codex proposals from existing prose (PLAN.md P2.2).

The friction this removes is the category's worst: Sudowrite's Story Bible makes
you re-type information that is already in your draft, and NovelCrafter asks for
configuration before anything works. A writer who imports a finished 90,000-word
manuscript should not have to tell the tool who is in it.

**Deterministic, not a model call.** Entity detection here is pure text
analysis - frequency, dialogue attribution, place prepositions, honorifics. That
makes it instant, free, offline, and exactly testable, and it means importing a
manuscript costs nothing. An LLM pass can enrich the summaries later; it must
never be required to get the names.

**Proposals, never writes.** Nothing in this module touches StoryState. It
returns candidates for a human to confirm, per the cross-cutting rule that AI
proposes and the human disposes. Precision matters more than recall: a wrong
proposal costs the writer a click of annoyance, and twenty wrong proposals cost
their trust in the whole panel.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set

# Words that begin sentences constantly and would otherwise look like names.
# Kept deliberately broad: a missed character is a click away, a false one is not.
_STOPWORDS: Set[str] = {
    "a", "about", "after", "again", "against", "all", "almost", "already", "although",
    "always", "am", "an", "and", "another", "any", "anyone", "anything", "are", "as",
    "at", "back", "because", "before", "behind", "being", "below", "beneath",
    "beside", "besides", "better", "between", "beyond", "both", "but", "by", "can",
    "could", "did", "do", "does", "down", "each", "either", "else", "enough", "even",
    "every", "everyone", "everything", "except", "far", "few", "finally", "first",
    "for", "from", "further", "half", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "however", "i", "if", "in", "inside", "instead", "into",
    "is", "it", "its", "itself", "just", "last", "later", "least", "less", "let",
    "like", "little", "long", "made", "make", "many", "maybe", "me", "meanwhile",
    "might", "mine", "more", "most", "much", "must", "my", "myself", "near",
    "nearly", "neither", "never", "next", "no", "nobody", "none", "nor", "not",
    "nothing", "now", "of", "off", "on", "once", "one", "only", "onto", "or",
    "other", "others", "otherwise", "our", "ours", "out", "outside", "over",
    "perhaps", "please", "rather", "really", "same", "she", "should", "since", "so",
    "some", "somebody", "someone", "something", "sometimes", "somewhere", "soon",
    "still", "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "therefore", "these", "they", "this", "those", "though",
    "three", "through", "thus", "to", "together", "too", "toward", "towards", "two",
    "under", "until", "up", "upon", "us", "very", "was", "we", "well", "were",
    "what", "when", "where", "whether", "which", "while", "who", "whom", "whose",
    "why", "will", "with", "within", "without", "would", "yes", "yet", "you",
    "your", "yours", "yourself",
    # Days and months read exactly like proper nouns and never are characters.
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
}

# "said Mara", "Mara said", "whispered Lena" - the strongest character signal in
# fiction, because only people speak.
_SPEECH_VERBS = (
    "said", "asked", "replied", "shouted", "whispered", "murmured", "muttered",
    "answered", "called", "cried", "growled", "snapped", "sighed", "breathed",
    "laughed", "screamed", "yelled", "told", "added", "insisted", "admitted",
)

_NAME = r"[A-Z][a-z]+(?:['’-][A-Z]?[a-z]+)*"

_SAID_AFTER = re.compile(rf"\b(?:{'|'.join(_SPEECH_VERBS)})\s+({_NAME})\b")
_SAID_BEFORE = re.compile(rf"\b({_NAME})\s+(?:{'|'.join(_SPEECH_VERBS)})\b")
_HONORIFIC = re.compile(
    rf"\b(?:Mr|Mrs|Ms|Miss|Dr|Doctor|Professor|Captain|Sergeant|Lord|Lady|King|"
    rf"Queen|Prince|Princess|Sister|Brother|Father|Mother|Uncle|Aunt)\.?\s+({_NAME})\b"
)
_POSSESSIVE = re.compile(rf"\b({_NAME})['’]s\b")

# "in Ashfall", "at the Grey Harbour", "from Veren" - place signals.
_PLACE_PREP = re.compile(
    rf"\b(?:in|at|to|from|toward|towards|through|across|near|outside|inside|beyond)\s+"
    rf"(?:the\s+)?((?:{_NAME})(?:\s+{_NAME})?)\b"
)
# Named places usually carry a geographic noun somewhere in the phrase.
_PLACE_NOUNS = (
    "city", "town", "village", "harbour", "harbor", "port", "castle", "keep",
    "tower", "bridge", "river", "mountain", "mountains", "forest", "wood", "woods",
    "valley", "island", "isle", "sea", "bay", "road", "street", "market", "temple",
    "cathedral", "palace", "manor", "hall", "gate", "district", "quarter", "station",
    "county", "province", "kingdom", "empire", "realm", "desert", "plains",
)
# Deliberately NOT re.IGNORECASE: that would let [A-Z][a-z]+ match lowercase
# words, so "the lights of Grey Harbour" proposed itself as a place name.
_PLACE_NOUN_ALT = "|".join(
    p for noun in _PLACE_NOUNS for p in (noun, noun.capitalize())
)
_PLACE_NOUN_RE = re.compile(rf"\b((?:{_NAME}\s+){{1,3}}(?:{_PLACE_NOUN_ALT}))\b")

# "Lena Marrow" is one character, not a "Lena" and a "Marrow".
_FULL_NAME = re.compile(rf"\b({_NAME}\s+{_NAME})\b")

_CAPITALISED = re.compile(rf"\b{_NAME}\b")
_SENTENCE_START = re.compile(r"(?:^|[.!?\"”]\s+|\n)\s*([A-Z][a-z]+)")


@dataclass
class Proposal:
    """A candidate Codex entry awaiting human confirmation."""
    name: str
    entry_type: str            # character | location | worldbuilding | item
    mentions: int
    # Why this was proposed, in words a writer can judge: "12 mentions, speaks".
    evidence: str
    chapters: List[int] = field(default_factory=list)
    # A sentence from the manuscript, so the writer can recognise it instantly.
    excerpt: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "entry_type": self.entry_type,
            "mentions": self.mentions,
            "evidence": self.evidence,
            "chapters": list(self.chapters),
            "excerpt": self.excerpt,
        }


def _is_candidate(word: str) -> bool:
    # "It's" and "That'll" survive the name pattern, so test the stem too:
    # otherwise every contraction in the manuscript looks like a proper noun.
    stem = re.split(r"['’]", word)[0]
    return (
        len(word) > 2
        and word.lower() not in _STOPWORDS
        and stem.lower() not in _STOPWORDS
        and len(stem) > 2
    )


def _first_sentence_with(text: str, name: str, limit: int = 160) -> str:
    """A short excerpt containing `name`, so a proposal is recognisable."""
    match = re.search(rf"[^.!?\n]*\b{re.escape(name)}\b[^.!?\n]*[.!?]", text)
    if not match:
        return ""
    sentence = " ".join(match.group(0).split())
    return sentence if len(sentence) <= limit else sentence[: limit - 1] + "…"


def _sentence_start_ratio(text: str, name: str) -> float:
    """How often a word appears only because a sentence began with it.

    "Still" and "Once" survive the stopword list in some manuscripts; a word that
    is *only* ever sentence-initial is grammar, not a name.
    """
    total = len(re.findall(rf"\b{re.escape(name)}\b", text))
    if total == 0:
        return 1.0
    initial = sum(1 for m in _SENTENCE_START.finditer(text) if m.group(1) == name)
    return initial / total


def extract_proposals(
    chapters: Dict[int, str],
    *,
    known_names: Iterable[str] = (),
    min_mentions: int = 3,
    limit: int = 60,
) -> List[Proposal]:
    """Propose Codex entries from a manuscript.

    `chapters` maps chapter number to its prose. `known_names` are already in the
    story state and are filtered out, so re-running after a partial review never
    re-proposes what the writer already accepted or the pipeline already knows.
    """
    known = {n.strip().lower() for n in known_names if n and n.strip()}
    # Individual words of a known full name, so "Lena Marrow" suppresses "Lena".
    for name in list(known):
        known.update(part for part in name.split() if len(part) > 2)

    full_text = "\n\n".join(chapters[n] for n in sorted(chapters))

    counts: Counter = Counter()
    chapter_hits: Dict[str, Set[int]] = {}
    speakers: Set[str] = set()
    titled: Set[str] = set()
    possessive: Set[str] = set()
    places: Set[str] = set()
    full_names: Counter = Counter()

    for number in sorted(chapters):
        text = chapters[number] or ""
        for word in _CAPITALISED.findall(text):
            if not _is_candidate(word):
                continue
            counts[word] += 1
            chapter_hits.setdefault(word, set()).add(number)
        for pattern, sink in (
            (_SAID_AFTER, speakers), (_SAID_BEFORE, speakers),
            (_HONORIFIC, titled), (_POSSESSIVE, possessive),
        ):
            sink.update(m for m in pattern.findall(text) if _is_candidate(m))
        for phrase in _PLACE_NOUN_RE.findall(text):
            places.add(" ".join(phrase.split()))
        for phrase in _PLACE_PREP.findall(text):
            phrase = " ".join(phrase.split())
            if all(_is_candidate(w) for w in phrase.split()):
                places.add(phrase)
        for phrase in _FULL_NAME.findall(text):
            phrase = " ".join(phrase.split())
            if all(_is_candidate(w) for w in phrase.split()):
                full_names[phrase] += 1

    # A multi-word name should not also propose its parts: "Grey Harbour" is one
    # place, and "Lena Marrow" is one character rather than two people.
    compounds = {p for p in places if " " in p}
    compounds |= {n for n, c in full_names.items() if c >= min_mentions and n not in places}
    compound_parts = {w for p in compounds for w in p.split()}

    proposals: List[Proposal] = []
    for name, count in counts.most_common():
        if name.lower() in known or count < min_mentions:
            continue
        if name in compound_parts:
            continue

        corroborated = (
            name in speakers or name in titled
            or name in possessive or name in places
        )
        # A word that only ever begins a sentence is grammar, not a name - but
        # only trust that signal with enough occurrences to be a pattern, and
        # never over harder evidence like dialogue attribution.
        if not corroborated and count >= 3 and _sentence_start_ratio(full_text, name) > 0.9:
            continue

        reasons: List[str] = [f"{count} mentions"]
        if name in speakers:
            entry_type = "character"
            reasons.append("speaks")
        elif name in titled:
            entry_type = "character"
            reasons.append("has a title")
        elif name in places:
            entry_type = "location"
            reasons.append("used as a place")
        elif name in possessive:
            entry_type = "character"
            reasons.append("possessive form")
        else:
            entry_type = "worldbuilding"
            reasons.append("recurring proper noun")

        chapters_seen = sorted(chapter_hits.get(name, set()))
        if len(chapters_seen) > 1:
            reasons.append(f"in {len(chapters_seen)} chapters")

        proposals.append(Proposal(
            name=name,
            entry_type=entry_type,
            mentions=count,
            evidence=", ".join(reasons),
            chapters=chapters_seen,
            excerpt=_first_sentence_with(full_text, name),
        ))

    # Multi-word names are proposed in their own right, whichever kind they are.
    for phrase in sorted(compounds):
        if phrase.lower() in known:
            continue
        count = len(re.findall(rf"\b{re.escape(phrase)}\b", full_text))
        if count < min_mentions:
            continue
        is_place = phrase in places
        proposals.append(Proposal(
            name=phrase,
            entry_type="location" if is_place else "character",
            mentions=count,
            evidence=f"{count} mentions, "
                     + ("named place" if is_place else "full name"),
            chapters=sorted(
                n for n, t in chapters.items() if phrase in (t or "")
            ),
            excerpt=_first_sentence_with(full_text, phrase),
        ))

    # Strongest evidence first: the writer should be able to stop reading early.
    proposals.sort(key=lambda p: (-p.mentions, p.name.lower()))
    return proposals[:limit]


def known_names_from_state(state) -> List[str]:
    """Every name the project already knows, for filtering proposals."""
    names: List[str] = []
    for char in getattr(state, "characters", {}).values():
        full = getattr(char, "full_name", "") or ""
        if full:
            names.append(full)
    for entry in getattr(state, "codex", {}).values():
        name = getattr(entry, "name", "") or ""
        if name:
            names.append(name)
    return names
