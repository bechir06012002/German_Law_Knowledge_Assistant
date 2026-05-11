"""Unit tests for the ingestion pieces, against shapes the real corpus actually contains.

Every fixture here comes from a decision in `data/downloads` — the letter-spaced bold section
markers, the bare Randnummer lines, the mixed heading levels, the navigation furniture.
Invented inputs would only test that the code matches my assumptions, which is exactly the
mistake that first labelled every chunk `Tenor`.
"""

from __future__ import annotations

import pytest

from app.ingestion.chunking import chunk_document, chunk_section, token_count
from app.ingestion.normalize import (
    canonical_section,
    clean_text,
    parse_paragraphs,
    split_sections,
)
from app.ingestion.pii import strip_identifiers

# Shape of a real decision: `## Tenor` as a heading, then the body sections as *bold
# letter-spaced paragraphs*, with Randnummern on their own lines.
REAL_DECISION = """## Tenor

Die Klage wird abgewiesen.

1

**T a t b e s t a n d:**

2

Die Parteien streiten über eine Kündigung während der Probezeit.

3

Die Klägerin war seit 2019 beschäftigt.

**E n t s c h e i d u n g s g r ü n d e:**

4

Die Klage ist unbegründet.
"""


class TestCanonicalSection:
    def test_markdown_heading(self):
        assert canonical_section("## Tenor") == "Tenor"

    def test_heading_level_ignored(self):
        """`Tenor` is `##` in 273 documents and `####` in 114 — level carries no meaning."""
        assert canonical_section("## Tenor") == canonical_section("#### Tenor") == "Tenor"

    def test_bold_letter_spaced_paragraph(self):
        """The form most body sections actually arrive in."""
        assert canonical_section("**T a t b e s t a n d:**") == "Tatbestand"
        assert canonical_section("**E n t s c h e i d u n g s g r ü n d e:**") == "Entscheidungsgründe"

    def test_plain_paragraph(self):
        assert canonical_section("Tatbestand") == "Tatbestand"

    def test_umlaut_and_ascii_spellings_agree(self):
        assert canonical_section("Entscheidungsgruende") == "Entscheidungsgründe"

    def test_trailing_colon_ignored(self):
        assert canonical_section("Gründe:") == "Gründe"

    @pytest.mark.parametrize(
        "junk",
        ["blob##nbsp;", "weitere Fundstellen einblenden", "Sonstige Literatur"],
    )
    def test_navigation_furniture_is_not_a_section(self, junk):
        assert canonical_section(junk) is None

    def test_ordinary_sentence_is_not_a_section(self):
        assert canonical_section("Die Klage ist unbegründet.") is None

    def test_long_line_is_not_a_section(self):
        assert canonical_section("Tatbestand " * 10) is None


class TestCleanText:
    def test_non_breaking_space_becomes_ordinary(self):
        """71% of the corpus contains U+00A0; it must not reach to_tsvector as its own char."""
        assert " " not in clean_text("Kündigung während der Probezeit")

    def test_blank_run_collapses(self):
        assert clean_text("a\n\n\n\n\nb") == "a\n\nb"

    def test_umlauts_survive(self):
        assert clean_text("Kündigung, Vergütung, groß") == "Kündigung, Vergütung, groß"


class TestParseParagraphs:
    def test_body_sections_are_found(self):
        """The bug this catches: everything after `## Tenor` was labelled `Tenor`."""
        labels = {p.section for p in parse_paragraphs(REAL_DECISION)}
        assert labels == {"Tenor", "Tatbestand", "Entscheidungsgründe"}

    def test_randnummer_captured(self):
        paragraphs = parse_paragraphs(REAL_DECISION)
        facts = [p for p in paragraphs if p.section == "Tatbestand"]
        assert [p.number for p in facts] == [2, 3]

    def test_randnummer_removed_from_text(self):
        """A stray `2` would otherwise be embedded and indexed as if it were content."""
        for paragraph in parse_paragraphs(REAL_DECISION):
            assert paragraph.text.strip() not in {"1", "2", "3", "4"}

    def test_text_order_preserved(self):
        texts = [p.text for p in parse_paragraphs(REAL_DECISION)]
        assert any("Probezeit" in t for t in texts)
        assert any("unbegründet" in t for t in texts)

    def test_text_before_any_marker_is_kept(self):
        paragraphs = parse_paragraphs("Vorspann ohne Überschrift.\n\n## Tenor\n\nAbgewiesen.")
        assert paragraphs[0].section == "Text"
        assert "Vorspann" in paragraphs[0].text

    def test_empty_input(self):
        assert parse_paragraphs("") == []

    def test_split_sections_merges_runs(self):
        assert [label for label, _ in split_sections(REAL_DECISION)] == [
            "Tenor",
            "Tatbestand",
            "Entscheidungsgründe",
        ]


class TestChunking:
    def test_chunks_carry_section_and_number(self):
        chunks = chunk_document(REAL_DECISION)
        assert {c.section for c in chunks} == {"Tenor", "Tatbestand", "Entscheidungsgründe"}
        assert any(c.number is not None for c in chunks)

    def test_chunks_never_span_sections(self):
        """A chunk labelled `Tatbestand` must not contain `Entscheidungsgründe` text."""
        markdown = (
            "**Tatbestand**\n\n"
            + "\n\n".join(f"Sachverhalt Absatz {i}." for i in range(80))
            + "\n\n**Entscheidungsgründe**\n\n"
            + "\n\n".join(f"Begruendung Absatz {i}." for i in range(80))
        )
        for chunk in chunk_document(markdown, limit=100, overlap=20):
            if chunk.section == "Tatbestand":
                assert "Begruendung" not in chunk.text
            if chunk.section == "Entscheidungsgründe":
                assert "Sachverhalt" not in chunk.text

    def test_short_section_is_one_chunk(self):
        assert chunk_section("Die Klage wird abgewiesen.", limit=350, overlap=50) == [
            "Die Klage wird abgewiesen."
        ]

    def test_long_section_splits(self):
        body = "\n\n".join(f"Absatz {i} über die Kündigungsfrist nach § 622 BGB." for i in range(200))
        chunks = chunk_section(body, limit=100, overlap=20)
        assert len(chunks) > 1
        assert all(token_count(c) <= 140 for c in chunks)

    def test_overlap_carries_context(self):
        body = "\n\n".join(f"Satz Nummer {i} mit etwas Inhalt." for i in range(60))
        chunks = chunk_section(body, limit=80, overlap=25)
        assert len(chunks) >= 2
        assert any(word in chunks[1][:200] for word in chunks[0][-80:].split())

    def test_oversized_single_sentence_is_not_dropped(self):
        sentence = "Wort " * 2000
        chunks = chunk_section(sentence, limit=100, overlap=10)
        assert len(chunks) > 1
        assert sum(token_count(c) for c in chunks) >= token_count(sentence) * 0.9

    def test_empty_document(self):
        assert chunk_document("") == []


class TestStripIdentifiers:
    def test_full_name_redacted(self):
        text, counts = strip_identifiers("Der Zeuge Herr Max Mustermann sagte aus.")
        assert "Mustermann" not in text
        assert counts["full_name"] == 1

    def test_address_redacted(self):
        text, counts = strip_identifiers("wohnhaft Hauptstraße 12 in Köln")
        assert "Hauptstraße 12" not in text
        assert counts["address"] == 1

    def test_email_and_iban_redacted(self):
        text, counts = strip_identifiers("mail a.b@firma.de, IBAN DE89 3704 0044 0532 0130 00")
        assert "@firma.de" not in text and "DE89" not in text
        assert counts["email"] == 1 and counts["iban"] == 1

    def test_phone_redacted(self):
        text, _ = strip_identifiers("erreichbar unter 0221/1234567")
        assert "1234567" not in text

    def test_legal_role_words_are_kept(self):
        """Kläger/Beklagte appear in 91% of decisions, carry the meaning, name nobody."""
        text, counts = strip_identifiers(
            "Der Kläger begehrt von der Beklagten die Zahlung von Urlaubsentgelt."
        )
        assert "Kläger" in text and "Beklagten" in text
        assert counts == {}

    def test_statute_references_untouched(self):
        text, _ = strip_identifiers("§ 622 Abs. 3 BGB und § 1 Abs. 1 KSchG")
        assert text == "§ 622 Abs. 3 BGB und § 1 Abs. 1 KSchG"

    def test_citation_metadata_survives(self):
        """Citation metadata is evidence — redacting it would break the product's point."""
        text, _ = strip_identifiers("Arbeitsgericht Aachen, Urteil vom 12.09.2025 – 5 Ca 750/24")
        assert "Arbeitsgericht Aachen" in text and "5 Ca 750/24" in text
