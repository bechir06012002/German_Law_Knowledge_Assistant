/**
 * Citation types, mirroring the backend's `data-citations` stream part.
 *
 * Everything here is evidence, and evidence stays German — court, Aktenzeichen, ECLI, the
 * section label and the passage text are never translated or reformatted, whatever language
 * the answer prose is in.
 */

import { apiFetch } from '@/lib/http'

export interface NormRef {
  book: string
  section: string
}

export interface Citation {
  chunkId: string
  court: string | null
  fileNumber: string | null
  /** Already German-formatted by the backend, e.g. "10.08.2023". */
  decisionDate: string | null
  decisionType: string | null
  ecli: string | null
  /** `Tenor`, `Tatbestand`, `Entscheidungsgründe` — never a page number. German decisions
   *  have named sections and no page concept. */
  section: string | null
  /** Randnummer — the pinpoint a German citation uses (Rn.). Null where the court has none. */
  paragraphNumber: number | null
  sourceUrl: string | null
  normRefs: NormRef[]
  text: string
}

export interface CitationPayload {
  queryLanguage: string
  /** The language the prose is written in, stated by the backend. Not inferred: an English
   *  answer legitimately contains German court names and quoted passages. */
  answerLanguage: 'de' | 'en' 
  /** The German string the lexical search actually used — shown when the question was not
   *  German, so a user can see that "notice period" became `Kündigungsfrist`. */
  lexicalQuery: string
  refused: boolean
  citations: Citation[]
}

/** `{book: "kschg", section: "1"}` -> `§ 1 KSchG`, the form a German lawyer writes. */
export function formatNormRef(ref: NormRef): string {
  const section = ref.section.replace(/^§+\s*/, '')
  return `§ ${section} ${ref.book.toUpperCase()}`
}

/** Distinct statutes for a citation, in a stable order, capped for display. */
export function uniqueNormRefs(refs: NormRef[], limit = 6): NormRef[] {
  const seen = new Set<string>()
  const out: NormRef[] = []
  for (const ref of refs) {
    const key = `${ref.book}|${ref.section}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push(ref)
    if (out.length >= limit) break
  }
  return out
}

export interface StatuteText {
  book: string
  section: string
  text: string | null
}

export function fetchStatute(book: string, section: string): Promise<StatuteText> {
  const clean = section.replace(/^§+\s*/, '')
  return apiFetch<StatuteText>(
    `/statutes/${encodeURIComponent(book)}/${encodeURIComponent(clean)}`,
  )
}
