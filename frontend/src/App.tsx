import { Suspense, lazy } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import ProtectedRoute from '@/components/ProtectedRoute'
import { AuthProvider } from '@/lib/auth'
import { UiLanguageProvider } from '@/lib/uiLanguage'
import HomePage from '@/pages/HomePage'
import LoginPage from '@/pages/LoginPage'

// The chat page pulls in the AI SDK, which is most of the bundle. Someone landing on the
// login screen has no use for it yet, so it loads on demand.
const ChatPage = lazy(() => import('@/pages/ChatPage'))

export default function App() {
  return (
    <UiLanguageProvider>
      <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={null}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/chat"
            element={
              <ProtectedRoute>
                <ChatPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/chat/:threadId"
            element={
              <ProtectedRoute>
                <ChatPage />
              </ProtectedRoute>
            }
          />
        </Routes>
        </Suspense>
      </BrowserRouter>
      </AuthProvider>
    </UiLanguageProvider>
  )
}
