import { PanelLeft } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { type Thread, createThread, deleteThread, listThreads } from '@/lib/api'
import { useAuth } from '@/lib/authContext'
import { useUiLanguage } from '@/lib/uiLanguageContext'
import LanguageToggle from '@/components/LanguageToggle'
import { ThreadListSkeleton } from '@/components/Skeleton'
import ThemeToggle from '@/components/ThemeToggle'
import Logo, { Wordmark } from '@/components/Logo'
import { cn } from '@/lib/utils'

const COLLAPSE_KEY = 'judges-said:sidebar-collapsed'

/**
 * Past conversations, newest first.
 *
 * A fixed 256px column swallows most of a phone screen, so below `md` this is a drawer the
 * chat can open. the non-goals rule out a native app, not a usable phone browser.
 *
 * On `md` and up it can also collapse to an icon-only rail — the toggle lives at its top, and
 * the app mark itself becomes the button to bring it back.
 */
export default function ThreadSidebar({
  open = false,
  onClose,
  refreshSignal,
}: {
  open?: boolean
  onClose?: () => void
  /** Bump this to re-fetch the list — e.g. once a thread's title has just been generated. */
  refreshSignal?: number
} = {}) {
  const { threadId } = useParams()
  const navigate = useNavigate()
  const { user, signOut } = useAuth()
  const { language, setLanguage, copy } = useUiLanguage()
  const [threads, setThreads] = useState<Thread[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    setCollapsed(localStorage.getItem(COLLAPSE_KEY) === '1')
  }, [])

  useEffect(() => {
    listThreads()
      .then(setThreads)
      .catch(() => setError(copy('errorLoadThreads')))
  }, [threadId, refreshSignal, copy])

  function toggleCollapsed() {
    setCollapsed((current) => {
      const next = !current
      localStorage.setItem(COLLAPSE_KEY, next ? '1' : '0')
      return next
    })
  }

  async function startNew() {
    const thread = await createThread()
    setThreads((current) => [thread, ...(current ?? [])])
    navigate(`/chat/${thread.id}`)
    onClose?.()
  }

  async function remove(id: string) {
    await deleteThread(id)
    setThreads((current) => (current ?? []).filter((t) => t.id !== id))
    if (id === threadId) navigate('/chat')
  }

  // The collapsed rail is a desktop-only preference — a mobile drawer that opened to a bare
  // icon would have no way back, since the expand button in the header is desktop-only too.
  const showCollapsed = collapsed && !open

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/20 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={cn(
          'bg-sidebar flex shrink-0 flex-col border-r transition-[width]',
          showCollapsed ? 'w-16' : 'w-64',
          // Off-canvas on phones, always visible from `md` up.
          'fixed inset-y-0 left-0 z-40 transition-transform md:static md:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
      <div className={cn('flex items-center p-3', showCollapsed ? 'justify-center' : 'justify-between')}>
        {showCollapsed ? (
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-label={copy('expandSidebar')}
            className="rounded-lg transition-opacity hover:opacity-80"
          >
            <Logo size={28} title={null} />
          </button>
        ) : (
          <>
            <Wordmark size={26} />
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={copy('collapseSidebar')}
              onClick={toggleCollapsed}
              className="hidden md:inline-flex"
            >
              <PanelLeft className="size-4" />
            </Button>
          </>
        )}
      </div>

      {!showCollapsed && (
        <>
          <div className="p-3">
            <Button className="w-full" onClick={() => void startNew()}>
              {copy('newResearch')}
            </Button>
          </div>

          <nav className="flex-1 space-y-0.5 overflow-y-auto px-2">
            {error && <p className="text-destructive px-2 text-sm">{error}</p>}
            {!error && threads === null && <ThreadListSkeleton />}
            {!error && threads?.length === 0 && (
              <p className="text-muted-foreground px-2 py-4 text-sm">
                {copy('noThreads')}
              </p>
            )}
            {(threads ?? []).map((thread) => (
              <div
                key={thread.id}
                className={cn(
                  'group/item hover:bg-muted flex items-center rounded-md',
                  thread.id === threadId && 'bg-muted font-medium',
                )}
              >
                <Link
                  to={`/chat/${thread.id}`}
                  className="flex-1 truncate px-2 py-1.5 text-left text-sm"
                  title={thread.title ?? copy('untitled')}
                  onClick={onClose}
                >
                  {thread.title ?? copy('untitled')}
                </Link>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  aria-label={copy('deleteThread')}
                  className="mr-1 shrink-0 opacity-0 group-hover/item:opacity-100"
                  onClick={() => void remove(thread.id)}
                >
                  ×
                </Button>
              </div>
            ))}
          </nav>

          <div className="text-muted-foreground space-y-2 border-t p-3 text-xs">
            <p className="truncate">{user?.email}</p>
            <div className="flex items-center justify-between gap-2">
              <LanguageToggle value={language} onChange={setLanguage} label="UI" />
              <ThemeToggle />
            </div>
            <Button variant="outline" size="sm" className="w-full" onClick={() => void signOut()}>
              {copy('signOut')}
            </Button>
          </div>
        </>
      )}
      </aside>
    </>
  )
}
