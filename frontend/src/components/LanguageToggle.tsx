import { cn } from '@/lib/utils'
import type { Language } from '@/lib/language'

/** DE / EN switch. Used for both the interface language and a thread's answer language. */
export default function LanguageToggle({
  value,
  onChange,
  label,
  disabled = false,
}: {
  value: Language
  onChange: (language: Language) => void
  label: string
  disabled?: boolean
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-muted-foreground text-xs">{label}</span>
      <div role="group" aria-label={label} className="border-border flex rounded-md border p-0.5">
        {(['de', 'en'] as const).map((code) => (
          <button
            key={code}
            type="button"
            disabled={disabled}
            aria-pressed={value === code}
            onClick={() => onChange(code)}
            className={cn(
              'rounded px-2 py-0.5 text-xs font-medium disabled:opacity-50',
              value === code ? 'bg-primary text-primary-foreground' : 'hover:bg-muted',
            )}
          >
            {code.toUpperCase()}
          </button>
        ))}
      </div>
    </div>
  )
}
