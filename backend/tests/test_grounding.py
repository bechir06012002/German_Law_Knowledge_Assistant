"""Tests for the compliance control.

Design rule: the RDG boundary must be enforced in the validator, not just the prompt. These
tests are what make that claim checkable — they run without an LLM, deterministically.
"""

from __future__ import annotations

import pytest

from app.grounding.validator import (
    Rejection,
    is_person_query,
    is_refusal,
    looks_like_prediction,
    validate,
)

RETRIEVED = {
    "c1": "Die Kündigung während der Probezeit ist nach § 622 Abs. 3 BGB mit einer Frist von zwei Wochen zulässig.",
    "c2": "Eine Arbeitsunfähigkeit steht dem Ausspruch einer Kündigung nicht entgegen.",
}


class TestPredictionRejection:
    """The RDG boundary. A false positive costs a regenerated answer; a false negative is an
    unlicensed legal service, so these patterns are deliberately broad."""

    @pytest.mark.parametrize(
        "text",
        [
            "Sie werden Ihren Prozess gewinnen.",
            "Sie dürften vor Gericht Erfolg haben.",
            "Die Erfolgsaussichten Ihrer Klage sind gut.",
            "Ihre Prozessaussichten sind günstig.",
            "Das Gericht wird Ihrer Klage stattgeben.",
            "Die Kammer dürfte die Klage abweisen.",
            "Ihre Kündigung ist wahrscheinlich unwirksam.",
            "Es besteht eine 80 % Wahrscheinlichkeit auf Erfolg.",
            "You will win your case.",
            "You are likely to succeed at the labour court.",
            "Your chances of success are high.",
            "Your case is strong.",
            "The court will rule in your favour.",
        ],
    )
    def test_predictions_are_detected(self, text):
        assert looks_like_prediction(text), f"prediction not caught: {text!r}"

    @pytest.mark.parametrize(
        "text",
        [
            "Das Arbeitsgericht Aachen hat die Klage abgewiesen.",
            "Das Gericht entschied, dass die Kündigung unwirksam war.",
            "In dieser Entscheidung hielt die Kammer die Frist für zu lang bemessen.",
            "Nach § 622 Abs. 3 BGB beträgt die Frist zwei Wochen.",
            "The court held that the dismissal was invalid.",
            "In this decision the court found the notice period too long.",
        ],
    )
    def test_describing_past_decisions_is_allowed(self, text):
        """Reporting what a court decided is information; forecasting is a legal service."""
        assert not looks_like_prediction(text), f"false positive: {text!r}"

    def test_validate_rejects_a_prediction_even_with_good_citations(self):
        result = validate(
            "Sie werden gewinnen, wie in der zitierten Entscheidung.",
            ["c1"],
            {},
            RETRIEVED,
        )
        assert not result.ok
        assert Rejection.PREDICTION in result.rejections


class TestCitationIntegrity:
    def test_cannot_cite_a_chunk_not_retrieved(self):
        result = validate("Das Gericht entschied so.", ["c1", "c99"], {}, RETRIEVED)
        assert not result.ok
        assert Rejection.UNRETRIEVED_CITATION in result.rejections

    def test_answer_with_no_citations_is_rejected(self):
        result = validate("Die Rechtslage ist kompliziert.", [], {}, RETRIEVED)
        assert not result.ok
        assert Rejection.NO_CITATIONS in result.rejections

    def test_refusal_may_have_no_citations(self):
        result = validate(
            "Ich habe keine vergleichbare Entscheidung im Bestand gefunden.", [], {}, RETRIEVED
        )
        assert result.ok

    def test_english_refusal_may_have_no_citations(self):
        result = validate("I found no comparable decision in the corpus.", [], {}, RETRIEVED)
        assert result.ok

    def test_a_good_answer_passes(self):
        result = validate(
            "Das Gericht hielt die zweiwöchige Frist für zulässig.",
            ["c1"],
            {"c1": "Die Kündigung während der Probezeit ist nach § 622 Abs. 3 BGB"},
            RETRIEVED,
        )
        assert result.ok, result.detail


class TestQuoteIntegrity:
    def test_verbatim_quote_passes(self):
        result = validate(
            "Das Gericht führte aus:", ["c2"],
            {"c2": "Eine Arbeitsunfähigkeit steht dem Ausspruch einer Kündigung nicht entgegen."},
            RETRIEVED,
        )
        assert result.ok

    def test_rewrapped_quote_still_passes(self):
        """Whitespace may be re-wrapped; wording may not."""
        result = validate(
            "Das Gericht führte aus:", ["c2"],
            {"c2": "Eine Arbeitsunfähigkeit steht dem Ausspruch\n  einer Kündigung nicht entgegen."},
            RETRIEVED,
        )
        assert result.ok

    def test_invented_quote_is_rejected(self):
        result = validate(
            "Das Gericht führte aus:", ["c2"],
            {"c2": "Eine Krankheit macht jede Kündigung automatisch unwirksam."},
            RETRIEVED,
        )
        assert not result.ok
        assert Rejection.QUOTE_NOT_IN_SOURCE in result.rejections

    def test_translated_quote_is_rejected(self):
        """A translated quote is a paraphrase presented as evidence — validated against the
        German source regardless of the answer language."""
        result = validate(
            "The court held:", ["c2"],
            {"c2": "An incapacity for work does not preclude a dismissal."},
            RETRIEVED,
        )
        assert not result.ok
        assert Rejection.QUOTE_NOT_IN_SOURCE in result.rejections


class TestPersonQueries:
    @pytest.mark.parametrize(
        "question",
        [
            "Hat jemand schon einmal gegen diese Firma geklagt?",
            "Welche Verfahren gibt es gegen den Arbeitgeber Müller?",
            "Has anyone ever sued this company?",
            "List all cases against employer Siemens",
        ],
    )
    def test_person_queries_are_detected(self, question):
        assert is_person_query(question)

    @pytest.mark.parametrize(
        "question",
        [
            "Mein Arbeitgeber hat mir während der Probezeit gekündigt.",
            "Wie haben Gerichte über Überstundenvergütung entschieden?",
            "What do courts say about dismissal during sick leave?",
        ],
    )
    def test_ordinary_questions_are_not_person_queries(self, question):
        assert not is_person_query(question)


class TestRefusalDetection:
    def test_german_refusal(self):
        assert is_refusal("Ich habe keine vergleichbare Entscheidung gefunden.")

    def test_english_refusal(self):
        assert is_refusal("No comparable decision was found in the corpus.")

    def test_a_normal_answer_is_not_a_refusal(self):
        assert not is_refusal("Das Arbeitsgericht Aachen hat die Klage abgewiesen.")


class TestBilingualGrounding:
    """Design rule: an English answer summarizes a German passage; it never replaces it.

    The validator is the thing that makes that true, so it must behave identically whatever
    language the prose is in.
    """

    def test_english_answer_over_german_passage_passes(self):
        result = validate(
            "The court held that a two-week notice period during probation is permissible.",
            ["c1"],
            {"c1": "Die Kündigung während der Probezeit ist nach § 622 Abs. 3 BGB"},
            RETRIEVED,
        )
        assert result.ok, result.detail

    def test_english_answer_with_english_quote_is_rejected(self):
        """The failure this prevents: a translated quote passed off as the source."""
        result = validate(
            "The court held:",
            ["c1"],
            {"c1": "Dismissal during probation is permitted under § 622(3) BGB"},
            RETRIEVED,
        )
        assert not result.ok
        assert Rejection.QUOTE_NOT_IN_SOURCE in result.rejections

    def test_prediction_is_caught_in_both_languages_equally(self):
        german = validate("Die Erfolgsaussichten sind gut.", ["c1"], {}, RETRIEVED)
        english = validate("Your chances of success are good.", ["c1"], {}, RETRIEVED)
        assert Rejection.PREDICTION in german.rejections
        assert Rejection.PREDICTION in english.rejections

    def test_english_answer_may_quote_german_verbatim_alongside(self):
        """An unofficial translation *beside* the German is allowed; the quote stays German."""
        result = validate(
            'The court held that incapacity does not preclude dismissal '
            '(original: "Eine Arbeitsunfähigkeit steht dem Ausspruch einer Kündigung nicht entgegen.").',
            ["c2"],
            {"c2": "Eine Arbeitsunfähigkeit steht dem Ausspruch einer Kündigung nicht entgegen."},
            RETRIEVED,
        )
        assert result.ok, result.detail
