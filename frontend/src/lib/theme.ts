/**
 * Light / dark theme.
 *
 * shadcn ships a complete `.dark` token set, but nothing ever applied the class, so dark mode
 * was unreachable — the tokens existed and the app was permanently light. This honours the
 * OS preference and remembers an explicit choice.
 */

export type Theme = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'judges-said:theme'

export function resolveTheme(theme: Theme): 'light' | 'dark' {
  if (theme !== 'system') return theme
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle('dark', resolveTheme(theme) === 'dark')
}

export function storedTheme(): Theme {
  const value = localStorage.getItem(STORAGE_KEY)
  return value === 'light' || value === 'dark' ? value : 'system'
}

export function setTheme(theme: Theme): void {
  localStorage.setItem(STORAGE_KEY, theme)
  applyTheme(theme)
}

/** Follow the OS while the user has not chosen explicitly. */
export function watchSystemTheme(): () => void {
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const onChange = () => {
    if (storedTheme() === 'system') applyTheme('system')
  }
  media.addEventListener('change', onChange)
  return () => media.removeEventListener('change', onChange)
}
