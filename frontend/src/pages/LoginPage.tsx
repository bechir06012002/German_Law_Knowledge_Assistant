import { type FormEvent, useEffect, useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'

import AuthBackground from '@/components/AuthBackground'
import LanguageToggle from '@/components/LanguageToggle'
import Logo from '@/components/Logo'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/authContext'
import { authErrorMessage } from '@/lib/authErrors'
import { applyLanguage } from '@/lib/language'
import { useUiLanguage } from '@/lib/uiLanguageContext'

type Mode = 'signin' | 'signup'

export default function LoginPage() {
  const { user, loading, signIn, signUp } = useAuth()
  const { language, setLanguage, copy } = useUiLanguage()
  const location = useLocation()
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Follows the toggle, so the tab title and <html lang> match what is on screen.
  useEffect(() => applyLanguage(language, 'login'), [language])

  if (!loading && user) {
    // Default to the app, not the marketing page — signing in should land you where your
    // thread history is, unless a protected route sent you here from somewhere specific.
    const from = (location.state as { from?: string } | null)?.from
    return <Navigate to={from ?? '/chat'} replace />
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      if (mode === 'signin') {
        await signIn(email, password)
      } else {
        await signUp(email, password)
        // This project has email confirmation enabled, so sign-up does not sign you in —
        // say so plainly instead of leaving the user on a form that looks like it failed.
        setNotice(copy('signUpConfirmNotice'))
      }
    } catch (cause) {
      setError(authErrorMessage(cause, language))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="relative mx-auto flex min-h-svh max-w-sm flex-col justify-center gap-6 px-6 py-12">
      <AuthBackground />

      <div className="fixed left-4 top-4 sm:left-6 sm:top-6">
        <LanguageToggle
          value={language}
          onChange={setLanguage}
          label={copy('interfaceLanguage')}
        />
      </div>

      <div className="border-border bg-card/90 space-y-6 rounded-3xl border p-8 shadow-xl shadow-black/5 backdrop-blur-sm">
        {/* Centred on the form's own width, so the mark sits over the middle of the fields
            below rather than hanging off their left edge. */}
        <div className="space-y-3 text-center">
          <Logo size={56} className="mx-auto" />
          <h1 className="text-2xl font-semibold tracking-tight">
            {mode === 'signin' ? copy('signIn') : copy('signUp')}
          </h1>
          <p className="text-muted-foreground text-sm">
            {copy('authSubtitle')}
          </p>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <div className="space-y-1.5">
            <label htmlFor="email" className="text-sm font-medium">
              {copy('emailLabel')}
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="border-input bg-background focus-visible:border-ring focus-visible:ring-ring/50 h-9 w-full rounded-lg border px-3 text-sm outline-none focus-visible:ring-3"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="text-sm font-medium">
              {copy('passwordLabel')}
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={6}
              autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="border-input bg-background focus-visible:border-ring focus-visible:ring-ring/50 h-9 w-full rounded-lg border px-3 text-sm outline-none focus-visible:ring-3"
            />
          </div>

          {error && (
            <p role="alert" className="text-destructive text-sm">
              {error}
            </p>
          )}
          {notice && (
            <p role="status" className="text-muted-foreground text-sm">
              {notice}
            </p>
          )}

          <Button type="submit" disabled={busy} className="w-full">
            {busy ? copy('pleaseWait') : mode === 'signin' ? copy('signIn') : copy('signUp')}
          </Button>
        </form>

        <div className="text-muted-foreground flex justify-between text-sm">
          <button
            type="button"
            className="underline underline-offset-4"
            onClick={() => {
              setMode(mode === 'signin' ? 'signup' : 'signin')
              setError(null)
              setNotice(null)
            }}
          >
            {mode === 'signin' ? copy('toSignUp') : copy('toSignIn')}
          </button>
          <Link to="/" className="underline underline-offset-4">
            {copy('back')}
          </Link>
        </div>
      </div>
    </main>
  )
}
