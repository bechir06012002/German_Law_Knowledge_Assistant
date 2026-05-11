/**
 * Environment — the only place `import.meta.env` is read.
 *
 * Vite inlines these at build time, so a missing value is a build/deploy mistake, not a
 * runtime condition to handle. Failing here makes it obvious immediately instead of
 * surfacing later as an unexplained fetch to `undefined/threads`.
 */

function required(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(
      `Missing ${name}. Copy .env.example to .env and fill it in — Vite reads these at build time.`,
    )
  }
  return value
}

export const env = {
  apiBaseUrl: required('VITE_API_BASE_URL', import.meta.env.VITE_API_BASE_URL).replace(/\/$/, ''),
  supabaseUrl: required('VITE_SUPABASE_URL', import.meta.env.VITE_SUPABASE_URL),
  // Anon key only. The service-role key bypasses row level security and must never be
  // shipped to a browser.
  supabaseAnonKey: required('VITE_SUPABASE_ANON_KEY', import.meta.env.VITE_SUPABASE_ANON_KEY),
} as const
