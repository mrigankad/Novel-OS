"""Manuscript helpers: word counts, version snapshots, and the sample book."""

from __future__ import annotations

import difflib
import re
from typing import Optional

from sqlmodel import Session, select

from ..models import Chapter, ChapterVersion, CodexEntry, CodexLink, PlotThread, Project

AUTO_SNAPSHOT_WORDS = 200
_WORD = re.compile(r"[\w][\w'’-]*", re.UNICODE)


def words(text: str) -> list[str]:
    return _WORD.findall(text or "")


def word_count(text: str) -> int:
    return len(words(text))


def changed_words(old: str, new: str) -> int:
    """How many words were inserted, deleted or replaced between two texts."""
    a, b = words(old), words(new)
    if abs(len(a) - len(b)) > AUTO_SNAPSHOT_WORDS:
        return abs(len(a) - len(b))
    if len(a) + len(b) > 40_000:  # very long chapters: the size delta is enough
        return abs(len(a) - len(b))
    changed = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != "equal":
            changed += max(i2 - i1, j2 - j1)
    return changed


def last_version(session: Session, chapter_id: str) -> Optional[ChapterVersion]:
    return session.exec(
        select(ChapterVersion).where(ChapterVersion.chapter_id == chapter_id)
        .order_by(ChapterVersion.created_at.desc())
    ).first()


def snapshot(session: Session, ch: Chapter, kind: str = "snapshot", note: str = "",
             produced_by: str = "author") -> ChapterVersion:
    v = ChapterVersion(chapter_id=ch.id, kind=kind, text=ch.text, word_count=ch.word_count,
                       produced_by=produced_by, note=note)
    session.add(v)
    return v


def maybe_auto_snapshot(session: Session, ch: Chapter, previous_text: str) -> Optional[ChapterVersion]:
    """Snapshot when the text has moved more than AUTO_SNAPSHOT_WORDS since the last version."""
    last = last_version(session, ch.id)
    base = last.text if last else previous_text if previous_text else ""
    if changed_words(base, ch.text) > AUTO_SNAPSHOT_WORDS:
        return snapshot(session, ch, kind="snapshot", note="Auto-snapshot")
    return None


# --------------------------------------------------------------------- sample

_CH1 = """The frost came to the north orchard on the ninth of October, three weeks before anyone had been ready for it. Iris Vale found it at six in the morning, a white fur along the lowest branches of the Bramleys, and stood in it with her coat open until her hands went numb.

Her father had planted these trees. He had planted them in rows so straight that the neighbours used to joke he had done it with a rifle sight, and for thirty years the orchard had answered him with fruit. Now he was eleven months in the churchyard at Hale, and the orchard answered no one.

Tomas Reed was already in the lower rows when she came down. He was kneeling by a young tree with his grafting knife open in his palm, the bone handle dark with years of other men's hands. He did not look up.

"It took the late blossom," he said. "On the Coxes. Not the Bramleys. The Bramleys will hold."

"Will they."

"If the wasps leave them be." He closed the knife and slid it into the pocket of his waistcoat, where it always lived. "They came early this year. Fat with it. They know something we don't."

Iris walked the row with him. The grass crunched. There was a smell she remembered from childhood, cold iron and bruised apple, and for a moment she was eight years old and her father was lifting her into the crook of a tree to see the whole orchard laid out like a hand of cards.

"The agent from Marsh and Cole is coming on Friday," she said.

Tomas stopped. He looked at the trees and not at her.

"To value it," she said. "Only to value it."

"Your father said that once." He began walking again. "About the east field. Only to value it."

She had no answer for that. The east field was houses now, red brick and gravel drives, and from the top of the orchard you could see their satellite dishes catch the sun like a row of small white faces turned toward something only they could hear.

They worked until the light came properly. Neither of them mentioned Friday again."""

_CH2 = """The river was high after the rain, brown and fast and full of leaves, and Tomas went down to it in the afternoon to cut willow for the new stakes. Iris followed him because she could not stand the house. The agent had telephoned twice. She had not picked up.

He worked at the bank with the grafting knife, taking the whips clean and quick, bundling them with twine. She watched his hands. They were the steadiest thing she knew.

"Did he ever tell you why he planted the north orchard first?" she asked.

"He told me a lot of things." Tomas sliced, bundled, sliced. "Most of them about wasps."

"Tell me one."

He considered this. "He said a wasp will only sting you if it thinks you're the one who's afraid. So he'd stand very still in the middle of them. Arms out. Like a scarecrow. He'd let them walk on his face." He shook his head. "Your mother used to scream at him from the gate."

Iris laughed, and it surprised her, and the laugh went out across the water and came back thinner.

Tomas reached for a long whip at the edge of the bank. The clay gave under his boot. He did not fall, quite; he caught himself on the willow with one hand, but the other hand opened, and the knife went out of it in a small bright arc and into the brown water without a sound.

For a long moment neither of them moved.

"It's all right," Iris said. "We'll find it. When the water drops."

"It won't drop." Tomas was looking at the place where the river had closed over it. "Not before spring. And by spring it'll be in the sea."

He had carried that knife for forty-one years. It had been his uncle's before that. She knew this the way she knew the names of the trees, without ever having been told.

"I'll buy you another."

"You can buy a knife." He picked up the bundle of willow and settled it on his shoulder. "You can't buy that one."

They walked back up through the orchard in the failing light. The wasps were thick on the windfalls, drunk and slow, and Tomas walked straight through them with his empty hand hanging at his side, and not one of them touched him."""

_CH3 = """The man from Marsh and Cole wore a waxed jacket that had never seen weather. He called the trees "the stock" and the rows "the plantation" and he walked them with a measuring wheel that clicked every metre, so that the whole of Friday morning was punctuated by small dry sounds, like someone counting under their breath.

Iris walked beside him and answered his questions. Yes, the Bramleys were sixty years old. Yes, there was a well. No, the cottage was not included; Tomas had a life tenancy, it was in the deeds. The man wrote this down with an expression of polite regret.

"Development land is where the value is," he said, at the top of the north orchard, looking down over the rows to the red roofs of the east field. "With the frost the way it's been, the fruit side of things, honestly, I'd be surprised if it covered the rates."

"The frost took the late blossom," Iris said. "The Bramleys held."

"Mm." The wheel clicked. "Well."

When he had gone she went down to the cottage. Tomas had lit the stove and the kitchen smelled of woodsmoke and sour apples. He was at the table sorting scion wood into bundles by variety, writing the names on brown luggage labels in his square careful hand.

"Well?" he said.

"He says it's worth more without the trees."

Tomas nodded slowly, as if this were a reasonable thing for a person to say about a living orchard. Behind him, on the windowsill above the sink, the grafting knife lay where it always lay at the end of a day, its bone handle catching the last of the light.

Iris looked at it. Then she looked at Tomas, at his hands moving among the labelled bundles, and found that she could not say anything at all.

"I'm not selling," she said finally. It came out smaller than she meant.

"I know," said Tomas. "I knew on Tuesday."

"How?"

"You let the wasps walk on you." He did not look up. "At the gate. You stood still. He used to do that."

Outside the frost was coming again, early, settling over the rows like something that had every right to be there."""

_SAMPLE_CHAPTERS = [
    dict(number=1, act=1, title="First Frost", pov="Iris Vale", status="drafted", text=_CH1,
         synopsis="An early frost hits the north orchard. Iris and Tomas assess the damage; Iris admits an agent is coming to value the land.",
         beats=["Frost on the Bramleys at dawn", "Tomas with the grafting knife", "Memory of her father", "The agent is coming Friday"]),
    dict(number=2, act=1, title="The River", pov="Iris Vale", status="drafted", text=_CH2,
         synopsis="Cutting willow at the river, Tomas tells Iris about her father and the wasps, then loses his grafting knife in the flood water.",
         beats=["Avoiding the agent's calls", "The wasp story", "The knife goes into the river", "You can't buy that one"]),
    dict(number=3, act=1, title="Valuation", pov="Iris Vale", status="drafted", text=_CH3,
         synopsis="The valuer from Marsh and Cole walks the orchard. Iris decides not to sell.",
         beats=["The measuring wheel", "Worth more without the trees", "Tomas sorting scion wood", "I'm not selling"]),
    dict(number=4, act=2, title="Scion Wood", pov="Tomas Reed", status="planned",
         synopsis="Tomas teaches Iris to graft with a borrowed knife. The developer makes an offer through her brother.",
         beats=["A borrowed knife that feels wrong", "First graft", "Her brother's phone call", "Tomas's tenancy is questioned"]),
    dict(number=5, act=2, title="Wasp Year", pov="Iris Vale", status="planned",
         synopsis="A wasp nest in the barn wall forces a reckoning with her father's habits and Tomas's health.",
         beats=["The nest in the barn", "Tomas falls ill", "Iris stands still among the wasps", "The river drops"]),
    dict(number=6, act=2, title="Blossom", pov="Iris Vale", status="planned",
         synopsis="Spring. The grafts take. Iris finds the knife when the river finally drops, and decides what the orchard is for.",
         beats=["The grafts take", "The river at its lowest", "The knife in the gravel", "Blossom on the north orchard"]),
]


def create_sample_book(session: Session) -> Project:
    p = Project(
        title="The Glass Orchard", author="Novel OS sample", genre="Literary",
        premise=("After her father's death, Iris Vale must decide whether to sell the family's north orchard "
                 "while its old foreman, Tomas Reed, keeps it alive through a year of frost and wasps."),
        target_words=72_000, status="drafting",
        bible={"tone": "quiet, elegiac, exact", "pov": "close third", "tense": "past",
               "setting": "a failing Herefordshire orchard, present day"},
    )
    session.add(p)
    session.flush()
    for spec in (dict(x) for x in _SAMPLE_CHAPTERS):
        text = spec.pop("text", "")
        ch = Chapter(project_id=p.id, text=text, word_count=word_count(text), target_words=3000, **spec)
        session.add(ch)
        session.flush()
        if text:
            snapshot(session, ch, kind="draft", note="First draft")

    def entry(**kw) -> CodexEntry:
        e = CodexEntry(project_id=p.id, **kw)
        session.add(e)
        return e

    iris = entry(kind="character", name="Iris Vale", aliases=["Iris"], role="protagonist",
                 summary="Late thirties, back from the city after her father's death. Owns the orchard and doesn't know what to do with it.",
                 facts={"status": "alive", "age": "38", "eye_color": "grey", "desire": "to keep faith with her father without becoming him"},
                 first_chapter=1, last_chapter=3)
    tomas = entry(kind="character", name="Tomas Reed", aliases=["Tomas"], role="supporting",
                  summary="The orchard's foreman for forty years. Lives in the cottage on a life tenancy.",
                  facts={"status": "alive", "age": "67", "tenancy": "life tenancy in the cottage"},
                  first_chapter=1, last_chapter=3)
    orchard = entry(kind="location", name="North Orchard", aliases=["the orchard"],
                    summary="Bramleys and Coxes planted in rifle-straight rows by Iris's father.",
                    facts={"trees": "Bramley, Cox", "age": "sixty years"}, first_chapter=1)
    knife = entry(kind="item", name="Grafting knife", aliases=["the knife", "knife"],
                  summary="Tomas's bone-handled grafting knife, his uncle's before him.",
                  facts={"owner": "Tomas Reed", "status": "lost", "lost_chapter": "2", "location": "the river"},
                  first_chapter=1, last_chapter=2,
                  notes="Lost in the river in chapter 2. Should not reappear until the river drops (ch 6).")
    entry(kind="lore", name="Wasps", aliases=["wasp"],
          summary="Iris's father stood still among wasps; 'a wasp only stings the one who's afraid'.",
          facts={"rule": "stand still and they won't sting"})
    entry(kind="lore", name="Frost", summary="An early October frost that took the late blossom on the Coxes.",
          facts={"date": "9 October", "damage": "late blossom on the Coxes"})
    session.flush()
    session.add(CodexLink(project_id=p.id, source_id=knife.id, target_id=tomas.id, label="owned by"))
    session.add(CodexLink(project_id=p.id, source_id=tomas.id, target_id=orchard.id, label="works"))
    session.add(CodexLink(project_id=p.id, source_id=iris.id, target_id=orchard.id, label="owns"))
    session.add(PlotThread(project_id=p.id, name="Sell or keep the orchard", kind="main", priority=1,
                           planted_chapter=1, last_advanced_chapter=3, target_chapter=6))
    session.add(PlotThread(project_id=p.id, name="The lost knife", kind="mystery", priority=2,
                           planted_chapter=2, last_advanced_chapter=2, target_chapter=6,
                           notes="Recovered when the river drops in spring."))
    return p
