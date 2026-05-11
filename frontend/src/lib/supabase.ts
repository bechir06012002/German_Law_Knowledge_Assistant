import { createClient } from '@supabase/supabase-js'

import { env } from '@/lib/env'

/**
 * The one Supabase client for the whole app.
 *
 * Anon key only — the service-role key bypasses row level security and must never reach a
 * browser. This client owns the session: it persists it, refreshes it, and is the single
 * place any code reads the access token from. Tokens are never passed through props.
 */
export const supabase = createClient(env.supabaseUrl, env.supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
})

/** The current access token, refreshed if it is about to expire. */
export async function accessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
}
