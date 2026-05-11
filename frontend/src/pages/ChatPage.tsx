import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'

import ChatBackground from '@/components/ChatBackground'
import ChatPanel from '@/components/ChatPanel'
import ThreadSidebar from '@/components/ThreadSidebar'
import { Wordmark } from '@/components/Logo'
import { Button } from '@/components/ui/button'
import { createThread, listThreads } from '@/lib/api'
import { DEFAULT_LANGUAGE, applyLanguage } from '@/lib/language'

export default function ChatPage() {
  const { threadId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [resolving, setResolving] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  // Bumped once the first reply in a thread lands, so the sidebar re-fetches and picks up
  // the title the backend just generated from that thread's opening question.
  const [threadsVersion, setThreadsVersion] = useState(0)

  // Carried from the home page's prompt box: the message the user already typed before a
  // thread existed. Only meaningful for the thread it was created alongside.
  const draft = (location.state as { draft?: string } | null)?.draft

  useEffect(() => applyLanguage(DEFAULT_LANGUAGE, 'chat'), [])

  // /chat with no id: open the most recent conversation, or start one. Creating the thread
  // up front rather than on first send keeps the URL and the stored thread in step, so a
  // reload mid-conversation lands in the same place.
  useEffect(() => {
    if (threadId || resolving) return
    setResolving(true)
    listThreads()
      .then((threads) => (threads.length > 0 ? threads[0] : createThread()))
      .then((thread) => navigate(`/chat/${thread.id}`, { replace: true }))
      .catch(() => setResolving(false))
  }, [threadId, resolving, navigate])

  return (
    <div className="flex h-svh overflow-hidden">
      <ChatBackground />
      <ThreadSidebar open={menuOpen} onClose={() => setMenuOpen(false)} refreshSignal={threadsVersion} />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* Only reachable below `md`, where the sidebar is off-canvas. */}
        <div className="flex items-center gap-2 border-b p-2 md:hidden">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Menü"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(true)}
          >
            ☰
          </Button>
          <Wordmark size={22} className="text-sm" />
        </div>
        {threadId ? (
          <ChatPanel
            key={threadId}
            threadId={threadId}
            initialMessage={draft}
            onAssistantReply={() => setThreadsVersion((n) => n + 1)}
          />
        ) : (
          <div className="text-muted-foreground flex flex-1 items-center justify-center text-sm">
            …
          </div>
        )}
      </div>
    </div>
  )
}
