import { type FormEvent, useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import Logo from '@/components/Logo'
import { buttonVariants } from '@/components/ui/button'
import LanguageToggle from '@/components/LanguageToggle'
import SendButton from '@/components/SendButton'
import ThemeToggle from '@/components/ThemeToggle'
import { useAuth } from '@/lib/authContext'
import { DEFAULT_LANGUAGE, applyLanguage } from '@/lib/language'
import { useUiLanguage } from '@/lib/uiLanguageContext'
import { cn } from '@/lib/utils'

export default function HomePage() {
  const { user, loading } = useAuth()
  const { language, setLanguage, copy } = useUiLanguage()
  const navigate = useNavigate()
  const [input, setInput] = useState('')

  useEffect(() => applyLanguage(DEFAULT_LANGUAGE, 'home'), [])

  // A signed-in visitor belongs in the app, where their thread history is one glance away —
  // not back on the marketing page they signed in from.
  if (!loading && user) {
    return <Navigate to="/chat" replace />
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!input.trim()) return
    navigate('/login', { state: { from: '/chat' } })
  }

  return (
    <div className="flex min-h-svh flex-col">
      <header className="flex items-center justify-between px-4 py-4 sm:px-6">
        <span className="flex items-center gap-2.5">
          <Logo size={28} title={null} />
          <span className="text-sm font-semibold tracking-tight">{copy('appName')}</span>
        </span>
        <div className="flex items-center gap-3">
          <LanguageToggle value={language} onChange={setLanguage} label={copy('interfaceLanguage')} />
          <ThemeToggle />
          {!loading && (
            <Link to="/login" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
              {copy('signIn')}
            </Link>
          )}
        </div>
      </header>

      <main className="flex flex-1 flex-col items-center justify-center px-4 pb-20">
        <div className="w-full max-w-2xl space-y-8">
          <div className="space-y-3 text-center">
            <Logo size={60} title={null} className="mx-auto" />
            <h1 className="text-6xl font-semibold tracking-tight sm:text-7xl">{copy('appName')}</h1>
            <p className="text-muted-foreground text-balance">{copy('tagline')}</p>
          </div>

          <form
            onSubmit={submit}
            className="border-border bg-card rounded-3xl border p-3 shadow-sm transition-shadow focus-within:shadow-md"
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  submit(e)
                }
              }}
              rows={3}
              placeholder={copy('inputPlaceholder')}
              className="placeholder:text-muted-foreground w-full resize-none bg-transparent px-2 py-1.5 text-base outline-none"
            />
            <div className="flex items-center justify-end px-1 pt-1">
              <SendButton disabled={!input.trim()} ariaLabel={copy('send')} />
            </div>
          </form>
        </div>
      </main>

      {/* The user-facing half of the RDG boundary; the enforced half is the backend
          grounding validator. Visible from the first screen, not buried in a footer. */}
      <footer className="border-t px-4 py-4">
        <p className="text-muted-foreground mx-auto max-w-2xl text-center text-xs text-balance">
          <strong className="text-foreground font-medium">{copy('disclaimerShort')}</strong> —{' '}
          {copy('disclaimerLong')}
        </p>
      </footer>
    </div>
  )
}
