/**
 * Auth context and its hook, separate from the provider component.
 *
 * A file that exports both a component and a hook breaks React Fast Refresh — editing the
 * hook remounts the provider and drops the session mid-development. Splitting them is the
 * fix the linter is pointing at.
 */

import type { User } from '@supabase/supabase-js'
import { createContext, useContext } from 'react'

export interface AuthState {
  user: User | null
  /** True until the first session lookup finishes, so routes do not flash the login page. */
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
