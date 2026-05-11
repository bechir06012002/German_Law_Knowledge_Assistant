"""Unit tests for fusion and cross-lingual query handling. No database needed."""

from __future__ import annotations

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.query_language import (
    detect_language,
    lexical_query,
    translate_terms,
    tsquery_terms,
)


class TestReciprocalRankFusion:
    def test_agreement_beats_a_single_strong_leg(self):
        """The whole point of RRF: a document both legs like outranks one leg's favourite."""
        fused = reciprocal_rank_fusion(
            {"semantic": ["only-semantic", "both"], "lexical": ["only-lexical", "both"]}
        )
        assert fused[0].key == "both"

    def test_missing_from_one_leg_is_not_fatal(self):
        fused = reciprocal_rank_fusion({"semantic": ["a"], "lexical": ["b"]})
        assert {f.key for f in fused} == {"a", "b"}

    def test_ranks_are_recorded_per_leg(self):
        fused = reciprocal_rank_fusion({"semantic": ["x", "y"], "lexical": ["y"]})
        by_key = {f.key: f for f in fused}
        assert by_key["y"].ranks == {"semantic": 2, "lexical": 1}
        assert by_key["x"].ranks == {"semantic": 1}

    def test_scores_ignore_leg_score_magnitude(self):
        """Only ranks are used — cosine and ts_rank_cd are not comparable numbers."""
        fused = reciprocal_rank_fusion({"semantic": ["a", "b", "c"]}, k=60)
        assert fused[0].score == 1 / 61
        assert fused[1].score == 1 / 62

    def test_order_is_deterministic(self):
        legs = {"semantic": ["a", "b"], "lexical": ["b", "a"]}
        assert [f.key for f in reciprocal_rank_fusion(legs)] == [
            f.key for f in reciprocal_rank_fusion(legs)
        ]

    def test_empty_input(self):
        assert reciprocal_rank_fusion({"semantic": [], "lexical": []}) == []


class TestDetectLanguage:
    def test_plain_german(self):
        assert detect_language("Mein Arbeitgeber hat mir gekündigt.") == "de"

    def test_plain_english(self):
        assert detect_language("My employer dismissed me during probation.") == "en"

    def test_german_without_umlauts(self):
        assert detect_language("Der Arbeitgeber hat die Kuendigung nicht begruendet") == "de"

    def test_short_german_phrase(self):
        assert detect_language("Kündigung Probezeit") == "de"

    def test_ambiguous_defaults_to_german(self):
        """The corpus and most users are German, so German wins ties."""
        assert detect_language("Homeoffice") == "de"


class TestTranslateTerms:
    def test_multiword_phrase_wins_over_its_parts(self):
        """'sick leave' must not become 'krank' + 'Urlaub'."""
        assert "Arbeitsunfähigkeit" in translate_terms("fired while on sick leave")
        assert "Urlaub" not in translate_terms("fired while on sick leave")

    def test_common_labour_terms(self):
        german = translate_terms("what is the notice period during the probation period")
        assert "Kündigungsfrist" in german
        assert "Probezeit" in german

    def test_english_words_are_dropped(self):
        """An English token in a german tsquery matches nothing — keeping it only adds noise."""
        german = translate_terms("my employer gave me a written warning yesterday")
        assert "yesterday" not in german.lower()
        assert "Abmahnung" in german

    def test_duplicates_collapse(self):
        german = translate_terms("dismissal and termination and notice")
        assert german.split().count("Kündigung") == 1


class TestTsqueryTerms:
    """Regression tests for the bug that made the lexical leg return zero rows.

    `websearch_to_tsquery`/`plainto_tsquery` AND their terms, so a whole sentence required
    every word to appear in one 350-token chunk. Measured: 0 rows for 9 of 10 realistic
    questions, and RRF silently became semantic-only.
    """

    def test_terms_are_ored_not_anded(self):
        assert " | " in tsquery_terms("Kündigung während der Probezeit")

    def test_question_words_and_pronouns_are_dropped(self):
        result = tsquery_terms("Mein Arbeitgeber hat mir während der Probezeit gekündigt")
        assert "Arbeitgeber" in result and "Probezeit" in result and "gekündigt" in result
        for noise in ("Mein", "hat", "mir", "während", "der"):
            assert noise not in result.split(" | ")

    def test_duplicates_collapse(self):
        assert tsquery_terms("Kündigung Kündigung kündigung").count("|") == 0

    def test_only_noise_yields_empty(self):
        """The caller skips the leg rather than sending Postgres a malformed query."""
        assert tsquery_terms("ich habe das nicht") == ""

    def test_punctuation_cannot_reach_the_tsquery(self):
        """Only letters and hyphens survive, so there is no tsquery syntax left to inject."""
        result = tsquery_terms("Kündigung! & (Probezeit) | 'quote' <-> :3")
        assert set(result) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÄÖÜäöüß- |")

    def test_short_words_are_dropped(self):
        assert "ab" not in tsquery_terms("ab Kündigung")

    def test_umlauts_survive(self):
        assert "Überstundenvergütung" in tsquery_terms("Überstundenvergütung")


class TestLexicalQuery:
    def test_german_query_passes_through_untouched(self):
        query = "Kündigung während der Probezeit bei Krankschreibung"
        assert lexical_query(query) == ("de", query)

    def test_english_query_becomes_german_terms(self):
        language, german = lexical_query("dismissal during the probation period")
        assert language == "en"
        assert "Kündigung" in german and "Probezeit" in german
        assert "dismissal" not in german.lower()

    def test_untranslatable_english_yields_no_lexical_query(self):
        """The dog-bite bug: falling back to the raw English produced the tsquery
        `walking | the | street | and | bite | leg | …` — English tokens matched against a
        German tsvector. The leg returned rows, so it looked healthy while contributing only
        noise. An empty string skips the leg and lets RRF honestly go semantic-only."""
        language, german = lexical_query(
            "i was walking on the street and a dog bit my leg, how much money do i get"
        )
        assert language == "en"
        assert german == ""

    def test_partially_translatable_english_keeps_what_it_found(self):
        language, german = lexical_query("i was on sick leave and got a warning")
        assert language == "en"
        assert "Arbeitsunfähigkeit" in german and "Abmahnung" in german
        assert "walking" not in german
