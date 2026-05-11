/**
 * Session state, shared through context.
 *
 * The context carries the user and a loading flag — never the access token. Token reads go
 * through the Supabase client, which is the only thing that knows whether the current one is
 * still valid.
 */

import type { Session } from '@supabase/supabase-js'
import { useEffect, useMemo, useState } from 'react'

import { AuthContext, type AuthState } from '@/lib/authContext'
import { supabase } from '@/lib/supabase'


export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })

    // Fires on sign-in, sign-out, and token refresh. Without this, an expired session keeps
    // rendering a signed-in UI whose every request 401s.
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next))
    return () => data.subscription.unsubscribe()
  }, [])

  const value = useMemo<AuthState>(
    () => ({
      user: session?.user ?? null,
      loading,
      signIn: async (email, password) => {
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
      },
      signUp: async (email, password) => {
        const { error } = await supabase.auth.signUp({ email, password })
        if (error) throw error
      },
      signOut: async () => {
        await supabase.auth.signOut()
      },
    }),
    [session, loading],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
