import { useEffect, useState } from 'react'

import { resolveTheme, setTheme, storedTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'

const OPTIONS: { value: 'light' | 'dark'; label: string; title: string }[] = [
  { value: 'light', label: '☀', title: 'Light' },
  { value: 'dark', label: '☾', title: 'Dark' },
]

/**
 * Light / dark, two buttons only. A first-time visitor still gets the OS-appropriate theme
 * (see `resolveTheme`) — this just shows which of the two that resolved to, rather than
 * offering a third "system" button. Clicking either one makes the choice explicit.
 */
export default function ThemeToggle() {
  const [theme, setLocal] = useState<'light' | 'dark'>('light')

  // Read in an effect, not in useState: on a server-rendered or pre-hydration pass there is
  // no localStorage, and this component should not be the thing that breaks.
  useEffect(() => setLocal(resolveTheme(storedTheme())), [])

  return (
    <div role="group" aria-label="Theme" className="border-border flex rounded-md border p-0.5">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          title={option.title}
          aria-label={option.title}
          aria-pressed={theme === option.value}
          onClick={() => {
            setTheme(option.value)
            setLocal(option.value)
          }}
          className={cn(
            'rounded px-1.5 py-0.5 text-xs',
            theme === option.value ? 'bg-primary text-primary-foreground' : 'hover:bg-muted',
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
