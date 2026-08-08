"""Codex extraction from existing prose (PLAN.md P2.2).

Precision is the property under test. A missed character costs one manual entry;
a panel full of wrong guesses costs the writer's trust in every proposal we ever
make, so the false-positive tests matter more than the recall ones.
"""

import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parents[1] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from codex_extract import extract_proposals, known_names_from_state  # noqa: E402


def names(proposals):
    return [p.name for p in proposals]


def by_name(proposals, name):
    return next(p for p in proposals if p.name == name)


CH1 = """
Lena Marrow stood at the rail. The wind came off the water and she did not move.
"You should go inside," said Mara. "It's turning cold."
Lena shook her head. "Not yet."
Mara watched her for a moment longer, then went below.
Lena stayed until the lights of Grey Harbour disappeared behind them.
"""

CH2 = """
They reached Grey Harbour before dawn. Mara had slept; Lena had not.
"Tell me again why we came," Mara said.
"Because Kesh asked," Lena answered. "And because I owe him."
Kesh was waiting at the end of the pier, exactly where he said he would be.
Grey Harbour smelled of tar and cold iron, the way it always had.
"""


def test_speakers_are_proposed_as_characters():
    out = extract_proposals({1: CH1, 2: CH2})
    assert "Lena" in names(out)
    assert by_name(out, "Lena").entry_type == "character"
    assert by_name(out, "Mara").entry_type == "character"


def test_dialogue_attribution_is_recorded_as_evidence():
    out = extract_proposals({1: CH1, 2: CH2})
    assert "speaks" in by_name(out, "Mara").evidence


def test_multi_word_place_is_proposed_as_a_location():
    out = extract_proposals({1: CH1, 2: CH2})
    harbour = by_name(out, "Grey Harbour")
    assert harbour.entry_type == "location"


def test_a_multi_word_place_does_not_also_propose_its_parts():
    """'Grey Harbour' must not spawn a separate 'Grey' proposal."""
    out = extract_proposals({1: CH1, 2: CH2})
    assert "Grey" not in names(out)


def test_proposals_carry_chapter_numbers_and_an_excerpt():
    out = extract_proposals({1: CH1, 2: CH2})
    lena = by_name(out, "Lena")
    assert lena.chapters == [1, 2]
    assert "Lena" in lena.excerpt
    assert lena.excerpt.endswith((".", "?", "!", "…"))


def test_ranked_by_evidence_so_the_writer_can_stop_reading_early():
    out = extract_proposals({1: CH1, 2: CH2})
    assert out == sorted(out, key=lambda p: (-p.mentions, p.name.lower()))


# ------------------------------------------------------- false positives

def test_sentence_initial_words_are_not_proposed_as_names():
    text = " ".join(["Still the rain fell."] * 6) + " ".join(["Once he was gone."] * 6)
    assert names(extract_proposals({1: text})) == []


def test_common_words_that_start_sentences_are_filtered():
    text = "\n".join([
        "The door opened. She waited. They came in. But nothing happened.",
    ] * 8)
    assert names(extract_proposals({1: text})) == []


def test_weekdays_and_months_are_never_characters():
    text = "\n".join(["On Monday it rained. By March it had stopped."] * 8)
    assert names(extract_proposals({1: text})) == []


def test_a_name_mentioned_once_is_below_the_threshold():
    out = extract_proposals({1: "Ferris appeared once and never again. " + CH1})
    assert "Ferris" not in names(out)


def test_min_mentions_is_configurable():
    out = extract_proposals({1: "Ferris waited. " + CH1}, min_mentions=1)
    assert "Ferris" in names(out)


# ------------------------------------------------------------- filtering

def test_names_the_project_already_knows_are_not_reproposed():
    out = extract_proposals({1: CH1, 2: CH2}, known_names=["Lena Marrow"])
    assert "Lena" not in names(out)
    assert "Mara" in names(out)


def test_filtering_is_case_insensitive():
    out = extract_proposals({1: CH1, 2: CH2}, known_names=["mara"])
    assert "Mara" not in names(out)


def test_limit_caps_the_review_queue():
    out = extract_proposals({1: CH1, 2: CH2}, limit=2)
    assert len(out) == 2


def test_empty_manuscript_proposes_nothing():
    assert extract_proposals({}) == []
    assert extract_proposals({1: ""}) == []


def test_proposal_serialises_for_the_api():
    out = extract_proposals({1: CH1, 2: CH2})
    d = out[0].to_dict()
    assert set(d) == {"name", "entry_type", "mentions", "evidence", "chapters", "excerpt"}


def test_known_names_reads_characters_and_codex():
    class _Char:
        full_name = "Lena Marrow"

    class _Entry:
        name = "Grey Harbour"

    class _State:
        characters = {"c1": _Char()}
        codex = {"e1": _Entry()}

    assert sorted(known_names_from_state(_State())) == ["Grey Harbour", "Lena Marrow"]


def test_a_repeated_full_name_is_one_proposal_not_two():
    text = "\n".join([
        'Lena Marrow crossed the yard. "Wait," said Lena Marrow.',
        'Lena Marrow did not wait. Nobody ever waited for Lena Marrow.',
    ] * 2)
    out = extract_proposals({1: text})
    assert "Lena Marrow" in names(out)
    assert by_name(out, "Lena Marrow").entry_type == "character"
    # The halves must not also appear as people of their own.
    assert "Lena" not in names(out)
    assert "Marrow" not in names(out)


def test_contractions_are_not_mistaken_for_proper_nouns():
    text = "\n".join(["It's late. That's enough. He's gone. She's tired."] * 6)
    assert names(extract_proposals({1: text})) == []


def test_a_lowercase_phrase_before_a_place_noun_is_not_a_place():
    """'the lights of Grey Harbour' must not propose itself as a location."""
    text = "\n".join(["He watched the lights of Grey Harbour fade."] * 4)
    out = extract_proposals({1: text})
    assert "Grey Harbour" in names(out)
    assert not any("lights" in n for n in names(out))
