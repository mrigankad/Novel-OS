"""Named styles that drive compile output (PLAN.md P5.2).

**Not to be confused with `StyleProfile` in state_manager.** That one describes
the *prose voice* - tense, POV, sentence length - and is read by the agents.
This one describes *typography*: what a chapter title looks like on the page.
They share a word and nothing else.

The point of named styles is the one Scrivener proved: a writer should say "this
is a Block Quote", not "this is 11pt italic indented 0.5 inches", and then
change what Block Quote means once and have the whole book follow. It is also
what makes compile presets possible - the same manuscript renders as a
submission format or an ebook by swapping the sheet, not by reformatting prose.

Deliberately typographic only. Nothing here can change a word of the manuscript;
a style names an appearance, and appearance is not story truth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

# The roles a compiled manuscript actually needs. Kept small on purpose: every
# extra named style is one more thing to understand before you can export.
STYLE_ROLES = (
    "title",            # the book's title page
    "subtitle",         # byline / genre line under it
    "chapter_title",    # "Chapter One" or the chapter's name
    "body",             # ordinary prose
    "first_paragraph",  # the paragraph after a heading or scene break
    "block_quote",      # letters, epigraphs, quoted documents
    "scene_break",      # the ornament between scenes
)

ALIGNMENTS = ("left", "center", "right", "justify")
FONT_FAMILIES = ("serif", "sans", "mono")


@dataclass
class Style:
    """One named appearance."""
    font: str = "serif"
    size_pt: float = 12.0
    line_height: float = 1.5
    align: str = "left"
    bold: bool = False
    italic: bool = False
    small_caps: bool = False
    # Ems rather than points: an indent should scale with the type size, which
    # is the whole reason presets can swap sizes without re-tuning indents.
    first_line_indent_em: float = 0.0
    space_before_em: float = 0.0
    space_after_em: float = 0.0
    page_break_before: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Style":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in (data or {}).items() if k in known})


def default_styles() -> Dict[str, Style]:
    """Standard manuscript typography - the shape an editor expects to receive."""
    return {
        "title": Style(size_pt=28, line_height=1.2, align="center", bold=True,
                       space_after_em=0.5),
        "subtitle": Style(size_pt=13, align="center", italic=True,
                          space_after_em=3.0),
        "chapter_title": Style(size_pt=18, line_height=1.3, align="center",
                               bold=True, space_before_em=2.0, space_after_em=1.5,
                               page_break_before=True),
        # No indent on the body's first line by default; `first_paragraph`
        # handles the one place typography says there should not be one.
        "body": Style(size_pt=12, line_height=1.6, align="left",
                      first_line_indent_em=1.5),
        "first_paragraph": Style(size_pt=12, line_height=1.6, align="left",
                                 first_line_indent_em=0.0),
        "block_quote": Style(size_pt=11.5, line_height=1.5, align="left",
                             italic=True, space_before_em=1.0, space_after_em=1.0),
        "scene_break": Style(size_pt=12, align="center", space_before_em=1.0,
                             space_after_em=1.0),
    }


class StyleError(ValueError):
    """A stylesheet was rejected. Carries a message meant for a writer."""


@dataclass
class StyleSheet:
    """The project's named styles, plus the ornament used for scene breaks."""
    styles: Dict[str, Style] = field(default_factory=default_styles)
    scene_break_marker: str = "* * *"

    def get(self, role: str) -> Style:
        """A style by role, falling back to `body` then to the defaults.

        Compile must never fail because a sheet is missing a role - an export
        that errors on the eve of a submission deadline is worse than one that
        quietly uses body text.
        """
        if role in self.styles:
            return self.styles[role]
        if "body" in self.styles:
            return self.styles["body"]
        return default_styles().get(role, Style())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "styles": {k: v.to_dict() for k, v in self.styles.items()},
            "scene_break_marker": self.scene_break_marker,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StyleSheet":
        data = data or {}
        styles = default_styles()
        for role, raw in (data.get("styles") or {}).items():
            if role in STYLE_ROLES:
                styles[role] = Style.from_dict(raw)
        return cls(
            styles=styles,
            scene_break_marker=str(data.get("scene_break_marker") or "* * *"),
        )


def validate(sheet: StyleSheet) -> List[str]:
    """Problems with a sheet, in words a writer can act on. Empty means fine."""
    problems: List[str] = []
    for role, style in sheet.styles.items():
        if role not in STYLE_ROLES:
            problems.append(f"'{role}' is not a style this compiler knows about.")
            continue
        where = role.replace("_", " ")
        if style.font not in FONT_FAMILIES:
            problems.append(
                f"{where}: font must be one of {', '.join(FONT_FAMILIES)}."
            )
        if style.align not in ALIGNMENTS:
            problems.append(
                f"{where}: alignment must be one of {', '.join(ALIGNMENTS)}."
            )
        if not 4 <= style.size_pt <= 96:
            problems.append(f"{where}: size must be between 4 and 96 points.")
        if not 0.8 <= style.line_height <= 4:
            problems.append(f"{where}: line height must be between 0.8 and 4.")
        if not -4 <= style.first_line_indent_em <= 12:
            problems.append(f"{where}: first-line indent is out of range.")
    return problems


def parse(data: Dict[str, Any]) -> StyleSheet:
    """Build a validated sheet, or raise StyleError with every problem at once."""
    sheet = StyleSheet.from_dict(data)
    problems = validate(sheet)
    if problems:
        raise StyleError(" ".join(problems))
    return sheet
