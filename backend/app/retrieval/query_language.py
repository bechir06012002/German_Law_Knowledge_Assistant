"""Decide the query language, and produce German search terms for the lexical leg.

The two retrieval legs behave differently across languages, and this is the crux of the
bilingual feature:

* The **semantic** leg works cross-lingually for free. A multilingual-e5 embedding of
  "fired while on sick leave" lands near German passages about `Kündigung während
  Arbeitsunfähigkeit`. It gets the original text, untranslated.
* The **lexical** leg does not. A `german`-config `tsvector` will never match the token
  "dismissal", so an English query makes full-text search contribute nothing and RRF silently
  degrades to semantic-only.

So English queries are translated to German **for the lexical leg only**.

A glossary rather than an LLM call, deliberately. The lexical leg consumes *terms*, not
prose — `websearch_to_tsquery` tokenises and stems whatever it is given — so fluent
translation buys nothing here. A glossary is free, deterministic, adds no latency, needs no
API key, and cannot hallucinate a statute that does not exist. the design contract explicitly allows
either. If recall on English queries turns out to be poor, replace `translate_terms` with a
small model call; nothing else has to change.
"""

from __future__ import annotations

import re

# German labour-law vocabulary, keyed by the English a non-lawyer would actually type.
# Multi-word keys are matched first so "sick leave" does not become "krank" + "Urlaub".
GLOSSARY: dict[str, str] = {
    "notice period": "Kündigungsfrist",
    "period of notice": "Kündigungsfrist",
    "probation period": "Probezeit",
    "probationary period": "Probezeit",
    "trial period": "Probezeit",
    "sick leave": "Arbeitsunfähigkeit Krankschreibung",
    "sick note": "Arbeitsunfähigkeitsbescheinigung",
    "sick pay": "Entgeltfortzahlung",
    "continued pay": "Entgeltfortzahlung",
    "unfair dismissal": "Kündigungsschutz unwirksame Kündigung",
    "wrongful dismissal": "unwirksame Kündigung",
    "summary dismissal": "fristlose Kündigung",
    "immediate dismissal": "fristlose Kündigung",
    "termination agreement": "Aufhebungsvertrag",
    "works council": "Betriebsrat",
    "collective agreement": "Tarifvertrag",
    "fixed term": "befristet Befristung",
    "fixed-term contract": "befristeter Arbeitsvertrag",
    "employment contract": "Arbeitsvertrag",
    "working hours": "Arbeitszeit",
    "overtime": "Überstunden",
    "overtime pay": "Überstundenvergütung",
    "holiday entitlement": "Urlaubsanspruch",
    "annual leave": "Urlaub Urlaubsanspruch",
    "parental leave": "Elternzeit",
    "maternity leave": "Mutterschutz",
    "severance": "Abfindung",
    "severance pay": "Abfindung",
    "written warning": "Abmahnung",
    "warning": "Abmahnung",
    "notice": "Kündigung",
    "dismissal": "Kündigung",
    "termination": "Kündigung",
    "fired": "Kündigung",
    "sacked": "Kündigung",
    "redundancy": "betriebsbedingte Kündigung",
    "employer": "Arbeitgeber",
    "employee": "Arbeitnehmer",
    "wage": "Lohn Vergütung",
    "wages": "Lohn Vergütung",
    "salary": "Gehalt Vergütung",
    "pay": "Vergütung",
    "bonus": "Bonus Sonderzahlung",
    "discrimination": "Diskriminierung Benachteiligung",
    "harassment": "Belästigung",
    "disability": "Schwerbehinderung",
    "pregnancy": "Schwangerschaft",
    "pregnant": "schwanger Schwangerschaft",
    "illness": "Krankheit",
    "sick": "krank Arbeitsunfähigkeit",
    "reference": "Arbeitszeugnis",
    "job reference": "Arbeitszeugnis",
    "part time": "Teilzeit",
    "part-time": "Teilzeit",
    "notice of termination": "Kündigungsschreiben",
    "labour court": "Arbeitsgericht",
    "labor court": "Arbeitsgericht",
    "trade union": "Gewerkschaft",
    "strike": "Streik",
    "apprentice": "Auszubildender",
    "training contract": "Berufsausbildungsvertrag",
    "temporary work": "Leiharbeit Zeitarbeit",
    "home office": "Homeoffice",
    "remote work": "Telearbeit Homeoffice",
    "company pension": "Betriebsrente betriebliche Altersversorgung",
}

# Cheap, high-signal markers. Umlauts and ß are decisive; otherwise the common function words
# separate the two languages reliably on the length of text a search box receives.
_GERMAN_MARKERS = re.compile(
    r"[äöüßÄÖÜ]|\b(?:der|die|das|und|nicht|mein|meine|ich|hat|habe|wurde|während|"
    r"gekündigt|Kündigung|Arbeitgeber|Arbeitnehmer|Urlaub|krank|wegen|ist|bin|dass)\b",
    re.IGNORECASE,
)
_ENGLISH_MARKERS = re.compile(
    r"\b(?:the|and|is|was|my|me|i|have|has|been|did|does|can|what|when|employer|"
    r"employee|dismissal|notice|work|during|because|they|their)\b",
    re.IGNORECASE,
)


def detect_language(query: str) -> str:
    """`de` or `en`. German wins ties — the corpus and most users are German."""
    german = len(_GERMAN_MARKERS.findall(query))
    english = len(_ENGLISH_MARKERS.findall(query))
    return "en" if english > german else "de"


def translate_terms(query: str) -> str:
    """English query -> German search terms for the lexical leg.

    Returns terms, not a sentence. Unmapped words are dropped rather than passed through:
    an English word in a `german` tsquery matches nothing, so keeping it only adds noise.
    """
    text = query.lower()
    found: list[str] = []

    # Longest keys first so "sick leave" is consumed before "sick".
    for english in sorted(GLOSSARY, key=len, reverse=True):
        pattern = rf"\b{re.escape(english)}\b"
        if re.search(pattern, text):
            found.append(GLOSSARY[english])
            text = re.sub(pattern, " ", text)

    # De-duplicate while keeping order; several English phrases map to the same German term.
    seen: set[str] = set()
    terms: list[str] = []
    for term in " ".join(found).split():
        if term.casefold() not in seen:
            seen.add(term.casefold())
            terms.append(term)
    return " ".join(terms)


def lexical_query(query: str) -> tuple[str, str]:
    """Return `(language, german_search_string)`. The string is `""` when there is nothing
    German to search for.

    Falling back to the raw English text was wrong. A question the glossary does not cover —
    "a dog bit my leg on the street" — produced the tsquery
    `walking | the | street | and | bite | leg | …`, English tokens matched against a German
    tsvector. That is noise dressed as a retrieval leg: it returns rows, so the leg *looks*
    healthy, while contributing nothing but random matches to the fusion.

    Returning "" instead skips the lexical leg, and RRF honestly degrades to semantic-only —
    which still works cross-lingually, because that is what multilingual-e5 is for.
    """
    language = detect_language(query)
    if language == "de":
        return language, query
    return language, translate_terms(query)


# Words that carry no retrieval signal in a question. `to_tsvector('german', …)` already
# drops German stopwords, but they have to go before the tsquery is built or an OR query
# matches everything.
_NOISE = frozenset(
    """
    ich mir mich mein meine meinem meinen meiner du dir dich dein deine er sie es ihm ihn
    ihr wir uns unser ihr euch der die das den dem des ein eine einen einem einer eines
    und oder aber wenn weil dass ob als wie was wer wo wann warum wieso welche welcher
    ist sind war waren wird werden wurde wurden hat habe haben hatte hatten kann können
    muss müssen soll sollen darf dürfen von vom zu zum zur in im an am auf für mit nach
    bei bis aus über unter vor seit ohne gegen um durch nicht kein keine nur auch noch
    schon sehr viel viele mehr sich man dann denn doch etwa
    während wegen zwischen innerhalb außerhalb trotz sowie damit dabei dafür dagegen
    daher deshalb jedoch sondern bereits immer jeder jede jedes alle allen aller
    etwas nichts mehrere vollständig
    """.split()
)

_WORD = re.compile(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-]{2,}")


def tsquery_terms(german_query: str) -> str:
    """Build an OR-ed tsquery string from a natural-language German question.

    `websearch_to_tsquery` and `plainto_tsquery` both AND their terms together, which for a
    sentence like *"Mein Arbeitgeber hat mir während der Probezeit gekündigt"* requires every
    word to appear in one 350-token chunk. Measured: that returned **zero** rows for nine of
    ten realistic questions, so the lexical leg contributed nothing and RRF quietly became
    semantic-only.

    OR-ing instead lets `ts_rank_cd` do the work it is for — a chunk matching more of the
    query's terms simply ranks higher. Returns `""` when nothing usable is left, and the
    caller then skips the leg rather than sending a malformed query.
    """
    seen: set[str] = set()
    terms: list[str] = []
    for match in _WORD.finditer(german_query):
        word = match.group(0)
        folded = word.casefold()
        if folded in _NOISE or folded in seen:
            continue
        seen.add(folded)
        # Only letters and hyphens reach this point, so the value is safe to interpolate
        # into a tsquery; there is no quoting syntax left to escape.
        terms.append(word)
    return " | ".join(terms)
