/**
 * The interface language, shared across the app and persisted.
 *
 * Distinct from a thread's *answer* language. A user may read the interface in English while
 * an individual answer is still in German, and the evidence stays German in both cases.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'

import { t } from '@/lib/i18n'
import { DEFAULT_LANGUAGE, type Language } from '@/lib/language'
import { UiLanguageContext, type UiLanguageState } from '@/lib/uiLanguageContext'

const STORAGE_KEY = 'judges-said:ui-language'


function initial(): Language {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'de' || stored === 'en') return stored
  // German first: the corpus is German and so are most users.
  return navigator.language?.startsWith('en') ? 'en' : DEFAULT_LANGUAGE
}

export function UiLanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<Language>(initial)

  useEffect(() => {
    // Screen readers and hyphenation depend on this being right.
    document.documentElement.lang = language
  }, [language])

  const setLanguage = useCallback((next: Language) => {
    localStorage.setItem(STORAGE_KEY, next)
    setLanguageState(next)
  }, [])

  const value = useMemo<UiLanguageState>(
    () => ({ language, setLanguage, copy: (key) => t(language, key) }),
    [language, setLanguage],
  )

  return <UiLanguageContext.Provider value={value}>{children}</UiLanguageContext.Provider>
}
