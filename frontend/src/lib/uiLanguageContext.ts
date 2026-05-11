/** UI-language context and hook, split from the provider for the same Fast Refresh reason. */

import { createContext, useContext } from 'react'

import type { CopyKey } from '@/lib/i18n'
import type { Language } from '@/lib/language'

export interface UiLanguageState {
  language: Language
  setLanguage: (language: Language) => void
  copy: (key: CopyKey) => string
}

export const UiLanguageContext = createContext<UiLanguageState | null>(null)

export function useUiLanguage(): UiLanguageState {
  const context = useContext(UiLanguageContext)
  if (!context) throw new Error('useUiLanguage must be used inside <UiLanguageProvider>')
  return context
}
