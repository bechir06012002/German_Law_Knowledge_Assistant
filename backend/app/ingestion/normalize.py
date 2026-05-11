"""Parse the dump's Markdown into labelled, numbered paragraphs.

Not a converter. The Open Legal Data dump ships `markdown_content` already converted from
HTML — measured over 389 decisions: zero residual HTML tags, zero entities, zero mojibake.
What it does not ship is structure that survived the conversion intact. Three things matter:

1. **Section markers are usually not Markdown headings.** Only `Tenor` is reliably `##`
   (387/389). The body sections come through as bold standalone paragraphs, letter-spaced
   exactly as the source HTML had them: `**T a t b e s t a n d:**`. Looking only at `#`
   headings labels the entire reasoning of a decision as `Tenor`, which is worse than no
   label — `section` is what a citation shows the reader.
2. **Heading level carries no meaning.** `Tenor` is `##` in 273 documents and `####` in 114.
3. **Randnummern survive as bare number lines.** `<span class="absatzRechts">17</span>`
   becomes a line containing just `17`. That is the pinpoint German lawyers cite (*Rn.*), so
   it is captured — and removed from the text, since a stray `17` would otherwise be embedded
   and indexed as if it were content.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Section labels worth keeping as citation anchors. `section` replaces the page number the
# previous project never populated, so it has to mean something to a reader.
CANONICAL_SECTIONS = (
    "Tenor",
    "Leitsatz",
    "Orientierungssatz",
    "Tatbestand",
    "Sachverhalt",
    "Entscheidungsgründe",
    "Gründe",
    "Rechtsmittelbelehrung",
)

# Navigation furniture the dump inherited from the website; not part of the decision.
_JUNK = re.compile(
    r"blob|nbsp|weitere\s*Fundstellen|Diese\s*Entscheidung\s*wird\s*zitiert"
    r"|einblenden|ausblenden|Sonstige\s*Literatur",
    re.IGNORECASE,
)

_HEADING = re.compile(r"^#{1,6}\s*(.+?)\s*$")
_RANDNUMMER = re.compile(r"^\(?(\d{1,4})\)?[.)]?$")
_DECORATION = re.compile(r"[*_`#]")

# The dump renders each numbered paragraph as a Pandoc definition list — the Randnummer is
# the term, `:   text` is the definition. That leading marker is Markdown syntax, not part of
# the decision, but nothing before this stripped it: it was stored and even quoted back as if
# it were the court's own words.
_DEFINITION_MARKER = re.compile(r"^:\s+")


def _fold(text: str) -> str:
    return (
        text.casefold()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


_SECTION_LOOKUP = {_fold(name): name for name in CANONICAL_SECTIONS}


def clean_text(text: str) -> str:
    """Fold invisible whitespace variants and collapse blank runs."""
    text = unicodedata.normalize("NFKC", text)
    for space in (" ", " ", " ", " "):
        text = text.replace(space, " ")
    text = text.replace("​", "").replace("﻿", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def canonical_section(line: str) -> str | None:
    """Map a line to a canonical section label, or None if it is not one.

    Accepts the forms this corpus actually contains: a Markdown heading, a bold paragraph,
    and the letter-spaced variant several courts emit.
    """
    label = line.strip()
    heading = _HEADING.match(label)
    if heading:
        label = heading.group(1)

    label = _DECORATION.sub("", label).strip().rstrip(":").strip()
    if not label or len(label) > 40 or _JUNK.search(label):
        return None

    # 'T a t b e s t a n d' -> 'Tatbestand'
    if re.fullmatch(r"(?:\S\s+)+\S", label):
        label = label.replace(" ", "")

    return _SECTION_LOOKUP.get(_fold(label))


@dataclass(frozen=True)
class Paragraph:
    section: str
    """Randnummer, where the decision has one — the pinpoint a German citation uses."""
    number: int | None
    text: str


def parse_paragraphs(markdown: str) -> list[Paragraph]:
    """Split into labelled paragraphs, carrying the Randnummer in force for each."""
    text = clean_text(markdown)
    if not text:
        return []

    section = "Text"
    number: int | None = None
    paragraphs: list[Paragraph] = []

    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue

        # A block can be a bare Randnummer, a section marker, or body text. Number lines and
        # markers arrive as their own blocks, so handle them before treating it as content.
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        body_lines: list[str] = []

        for line in lines:
            line = _DEFINITION_MARKER.sub("", line)
            rn = _RANDNUMMER.match(_DECORATION.sub("", line).strip())
            if rn and not body_lines:
                number = int(rn.group(1))
                continue

            label = canonical_section(line)
            if label is not None:
                # Flush what came before the marker, then switch.
                if body_lines:
                    paragraphs.append(Paragraph(section, number, " ".join(body_lines)))
                    body_lines = []
                section = label
                continue

            if _JUNK.search(line):
                continue

            body_lines.append(line)

        if body_lines:
            paragraphs.append(Paragraph(section, number, " ".join(body_lines)))

    return paragraphs


def split_sections(markdown: str) -> list[tuple[str, str]]:
    """`(section, text)` per section, in document order. Kept for callers that ignore
    Randnummern."""
    sections: list[tuple[str, str]] = []
    for paragraph in parse_paragraphs(markdown):
        if sections and sections[-1][0] == paragraph.section:
            sections[-1] = (paragraph.section, f"{sections[-1][1]}\n\n{paragraph.text}")
        else:
            sections.append((paragraph.section, paragraph.text))
    return sections
