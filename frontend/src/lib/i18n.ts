/**
 * UI copy in German and English.
 *
 * Two dictionaries and a lookup function, deliberately — the project's dependency policy rules
 * out an i18n framework for two languages and one screen. If this ever grows a third language
 * or plural rules, revisit; until then a framework is 40 kB to do what `t[key]` does.
 *
 * This is *interface* copy only. The evidence — court names, Aktenzeichen, ECLI, dates,
 * quoted passages — is never translated and never appears here.
 */

import type { Language } from '@/lib/language'

const de = {
  appName: 'Judges Said',
  tagline:
    'Finden Sie Gerichtsentscheidungen zu Ihrer arbeitsrechtlichen Situation — mit Gericht, Aktenzeichen und den einschlägigen Normen.',

  greetingMorning: 'Guten Morgen',
  greetingAfternoon: 'Guten Tag',
  greetingEvening: 'Guten Abend',
  hello: 'Hallo',

  signIn: 'Anmelden',
  signOut: 'Abmelden',
  signUp: 'Konto erstellen',
  authSubtitle: 'Judges Said — Entscheidungen deutscher Arbeitsgerichte',
  emailLabel: 'E-Mail',
  passwordLabel: 'Passwort',
  pleaseWait: 'Bitte warten …',
  toSignUp: 'Neues Konto erstellen',
  toSignIn: 'Ich habe bereits ein Konto',
  signUpConfirmNotice:
    'Konto erstellt. Wir haben Ihnen eine E-Mail geschickt — bitte bestätigen Sie die Adresse und melden Sie sich danach an.',
  interfaceLanguage: 'Sprache',
  startResearch: 'Recherche starten',
  newResearch: 'Neue Recherche',
  back: 'Zurück',
  loading: 'Wird geladen …',
  close: 'Schließen',
  collapseSidebar: 'Seitenleiste einklappen',
  expandSidebar: 'Seitenleiste ausklappen',

  inputPlaceholder: 'Ihre Situation beschreiben …',
  send: 'Senden',
  stop: 'Stopp',
  searching: 'Entscheidungen werden durchsucht …',
  statusRetrieving: 'Entscheidungen werden durchsucht …',
  statusReading: 'Entscheidungen werden ausgewertet …',
  statusValidating: 'Antwort wird geprüft …',
  statusRevising: 'Antwort wird überarbeitet …',
  noThreads: 'Noch keine Recherchen.',
  untitled: 'Ohne Titel',
  deleteThread: 'Recherche löschen',

  answerLanguage: 'Antwortsprache',
  switchingLanguage: 'Antwort wird übersetzt …',
  sameEvidence: 'Gleiche Entscheidungen, andere Sprache.',
  searchedInGerman: 'Gesucht wurde auf Deutsch nach:',

  source: 'Fundstelle',
  appliedNorms: 'Angewandte Normen',
  sectionUnknown: 'Abschnitt unbekannt',
  openSource: 'Quelle bei Open Legal Data öffnen',
  statuteNotInCorpus: 'Dieser Gesetzestext ist nicht im Bestand enthalten.',
  showTranslation: 'Inoffizielle Übersetzung anzeigen',
  hideTranslation: 'Übersetzung ausblenden',
  unofficialTranslation:
    'Inoffizielle Übersetzung — nicht verbindlich. Maßgeblich ist der deutsche Wortlaut.',
  originalGerman: 'Originalwortlaut (Deutsch)',

  disclaimerShort: 'Keine Rechtsberatung',
  disclaimerLong:
    'Diese Anwendung zeigt vorhandene Entscheidungen und trifft keine Vorhersagen über den Ausgang eines Verfahrens.',
  publicDomain: 'Amtliches Werk, gemeinfrei nach § 5 UrhG. Keine Rechtsberatung.',

  errorAuth: 'Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.',
  errorNetwork:
    'Der Server ist nicht erreichbar. Läuft das Backend, und ist diese Adresse in ALLOWED_ORIGINS eingetragen?',
  errorTimeout: 'Die Anfrage hat zu lange gedauert. Bitte versuchen Sie es erneut.',
  errorGeneric: 'Etwas ist schiefgelaufen.',
  errorLoadThreads: 'Recherchen konnten nicht geladen werden.',
} as const

const en: Record<keyof typeof de, string> = {
  appName: 'Judges Said',
  tagline:
    'Find the court decisions that match your employment situation — with the court, the file number, and the statutes they turn on.',

  greetingMorning: 'Good morning',
  greetingAfternoon: 'Good afternoon',
  greetingEvening: 'Good evening',
  hello: 'Hello',

  signIn: 'Sign in',
  signOut: 'Sign out',
  signUp: 'Create account',
  authSubtitle: 'Judges Said — decisions of the German labour courts',
  emailLabel: 'Email',
  passwordLabel: 'Password',
  pleaseWait: 'Please wait …',
  toSignUp: 'Create a new account',
  toSignIn: 'I already have an account',
  signUpConfirmNotice:
    'Account created. We sent you an email — please confirm your address, then sign in.',
  interfaceLanguage: 'Language',
  startResearch: 'Start research',
  newResearch: 'New search',
  back: 'Back',
  loading: 'Loading …',
  close: 'Close',
  collapseSidebar: 'Collapse sidebar',
  expandSidebar: 'Expand sidebar',

  inputPlaceholder: 'Describe your situation …',
  send: 'Send',
  stop: 'Stop',
  searching: 'Searching decisions …',
  statusRetrieving: 'Searching decisions …',
  statusReading: 'Reading the decisions …',
  statusValidating: 'Checking the answer …',
  statusRevising: 'Revising the answer …',
  noThreads: 'No searches yet.',
  untitled: 'Untitled',
  deleteThread: 'Delete search',

  answerLanguage: 'Answer language',
  switchingLanguage: 'Translating the answer …',
  sameEvidence: 'Same decisions, different language.',
  searchedInGerman: 'Searched in German for:',

  source: 'Source passage',
  appliedNorms: 'Statutes applied',
  sectionUnknown: 'Section unknown',
  openSource: 'Open the source at Open Legal Data',
  statuteNotInCorpus: 'This statute is not in the corpus.',
  showTranslation: 'Show unofficial translation',
  hideTranslation: 'Hide translation',
  unofficialTranslation:
    'Unofficial translation — not authoritative. The German wording is what counts.',
  originalGerman: 'Original wording (German)',

  disclaimerShort: 'Not legal advice',
  disclaimerLong:
    'This application shows existing decisions and makes no predictions about how a case will turn out.',
  publicDomain: 'Official work, public domain under § 5 UrhG. Not legal advice.',

  errorAuth: 'Your session expired. Please sign in again.',
  errorNetwork:
    'Cannot reach the server. Is the backend running, and is this origin in ALLOWED_ORIGINS?',
  errorTimeout: 'The request took too long. Please try again.',
  errorGeneric: 'Something went wrong.',
  errorLoadThreads: 'Could not load your searches.',
}

const dictionaries = { de, en } as const

export type CopyKey = keyof typeof de

export function t(language: Language, key: CopyKey): string {
  return dictionaries[language][key]
}

/** Bind the language once, so components read `copy('send')`. */
export function translator(language: Language) {
  return (key: CopyKey) => t(language, key)
}
