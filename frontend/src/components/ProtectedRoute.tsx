import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '@/lib/authContext'

/** Sends unauthenticated visitors to /login, remembering where they were going. */
export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  // Waiting on the first session lookup. Redirecting here would bounce signed-in users to
  // the login page on every reload.
  if (loading) {
    return (
      <div className="text-muted-foreground flex min-h-svh items-center justify-center text-sm">
        Wird geladen …
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}
