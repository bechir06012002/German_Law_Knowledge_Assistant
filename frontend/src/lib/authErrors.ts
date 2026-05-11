/**
 * Supabase auth errors, in the user's language.
 *
 * Supabase returns English strings aimed at developers ("email rate limit exceeded"). Those
 * are the first thing a user sees when something goes wrong, so they get translated.
 * Anything unmapped falls back to the original text rather than a vague "an error occurred" —
 * an untranslated message still beats an uninformative one.
 */

import { AuthError } from '@supabase/supabase-js'

import type { Language } from '@/lib/language'

const messages: Record<Language, Record<string, string>> = {
  de: {
    invalid_credentials: 'E-Mail-Adresse oder Passwort ist falsch.',
    email_not_confirmed:
      'Bitte bestätigen Sie zuerst Ihre E-Mail-Adresse. Prüfen Sie Ihr Postfach.',
    user_already_exists: 'Für diese E-Mail-Adresse existiert bereits ein Konto.',
    weak_password: 'Das Passwort ist zu schwach. Mindestens 6 Zeichen.',
    validation_failed: 'Bitte geben Sie eine gültige E-Mail-Adresse ein.',
    // Supabase's built-in mailer allows only a handful of sends per hour. Without this, a
    // user hitting it sees "email rate limit exceeded" and cannot tell it is temporary.
    over_email_send_rate_limit:
      'Zu viele Anmeldeversuche. Bitte warten Sie einige Minuten und versuchen Sie es erneut.',
    over_request_rate_limit: 'Zu viele Anfragen. Bitte warten Sie einen Moment.',
    signup_disabled: 'Die Registrierung ist derzeit deaktiviert.',
    unknown: 'Unbekannter Fehler.',
  },
  en: {
    invalid_credentials: 'That email address or password is not correct.',
    email_not_confirmed: 'Please confirm your email address first — check your inbox.',
    user_already_exists: 'An account already exists for this email address.',
    weak_password: 'That password is too weak. Use at least 6 characters.',
    validation_failed: 'Please enter a valid email address.',
    over_email_send_rate_limit:
      'Too many attempts. Please wait a few minutes and try again.',
    over_request_rate_limit: 'Too many requests. Please wait a moment.',
    signup_disabled: 'Sign-up is currently disabled.',
    unknown: 'Unknown error.',
  },
}

export function authErrorMessage(error: unknown, language: Language): string {
  const dictionary = messages[language]
  if (error instanceof AuthError) {
    return (error.code && dictionary[error.code]) || error.message
  }
  if (error instanceof Error) return error.message
  return dictionary.unknown
}
