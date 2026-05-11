import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from '@/App'
import '@/index.css'
import { applyTheme, storedTheme, watchSystemTheme } from '@/lib/theme'

// Before the first paint, otherwise a dark-mode user gets a white flash on every load.
applyTheme(storedTheme())
watchSystemTheme()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
