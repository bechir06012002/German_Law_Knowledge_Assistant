/**
 * Interface language — German by default, since the corpus and the users are German.
 *
 * Two languages and one screen do not justify an i18n framework (dependency
 * policy), so this is a plain lookup. Note this is the *interface* language; the language an
 * answer is written in is a separate, per-thread setting, and the evidence itself — court
 * names, Aktenzeichen, dates, quoted passages — always stays German.
 */

export type Language = 'de' | 'en'

export const DEFAULT_LANGUAGE: Language = 'de'

const titles: Record<Language, Record<string, string>> = {
  de: {
    login: 'Anmelden · Judges Said',
    home: 'Judges Said — Arbeitsrecht-Entscheidungen',
    chat: 'Judges Said',
  },
  en: {
    login: 'Sign in · Judges Said',
    home: 'Judges Said — German labour-law decisions',
    chat: 'Judges Said',
  },
}

export function applyLanguage(language: Language, page: keyof (typeof titles)['de']): void {
  document.documentElement.lang = language
  document.title = titles[language][page]
}
