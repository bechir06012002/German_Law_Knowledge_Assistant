import { useChat } from '@ai-sdk/react'
import type { UIMessage } from 'ai'
import { DefaultChatTransport } from 'ai'
import { type FormEvent, useEffect, useMemo, useRef, useState } from 'react'

import AssistantMessage from '@/components/AssistantMessage'
import SourcePanel from '@/components/SourcePanel'
import SendButton from '@/components/SendButton'
import { MessagesSkeleton } from '@/components/Skeleton'
import { useAuth } from '@/lib/authContext'
import type { CopyKey } from '@/lib/i18n'
import { useUiLanguage } from '@/lib/uiLanguageContext'
import { ApiError } from '@/lib/http'
import { Button } from '@/components/ui/button'
import { type Message, threadMessages } from '@/lib/api'
import type { Citation, CitationPayload } from '@/lib/citations'
import { env } from '@/lib/env'
import { accessToken } from '@/lib/supabase'

function toUIMessage(message: Message): UIMessage {
  // Rebuild the same `data-citations` part the stream sends, so a reloaded conversation
  // renders identically to a live one. Prose without its evidence is the one thing this
  // product must never show.
  const parts: UIMessage['parts'] = [{ type: 'text', text: message.content }]
  if (message.citations?.length) {
    parts.unshift({
      type: 'data-citations',
      data: {
        queryLanguage: message.translated_query ? 'en' : 'de',
        lexicalQuery: message.translated_query ?? '',
        refused: false,
        citations: message.citations,
      },
    } as UIMessage['parts'][number])
  }
  return { id: message.id, role: message.role, parts }
}

/** Time-of-day greeting, the way the rest of the copy is bilingual: a lookup, not a library. */
function greetingKey(hour: number): 'greetingMorning' | 'greetingAfternoon' | 'greetingEvening' {
  if (hour < 12) return 'greetingMorning'
  if (hour < 18) return 'greetingAfternoon'
  return 'greetingEvening'
}

/** Text of a UI message, which the SDK splits into typed parts. */
function textOf(message: UIMessage): string {
  return message.parts
    .filter((part): part is { type: 'text'; text: string } => part.type === 'text')
    .map((part) => part.text)
    .join('')
}

/**
 * The citations the backend attached to this message.
 *
 * They arrive as a custom `data-citations` stream part, sent before the text so the chips can
 * render as soon as the answer starts. Evidence and prose travel together.
 */
function citationsOf(message: UIMessage): Citation[] {
  const part = message.parts.find((p) => p.type === 'data-citations') as
    | { type: 'data-citations'; data: CitationPayload }
    | undefined
  return part?.data.citations ?? []
}

/** The language the answer prose is in, as stated by the backend. */
function answerLanguageOf(message: UIMessage): 'de' | 'en' {
  const part = message.parts.find((p) => p.type === 'data-citations') as
    | { type: 'data-citations'; data: CitationPayload }
    | undefined
  return part?.data.answerLanguage ?? 'de'
}

/** The German search string used, when the question itself was not German. */
function lexicalQueryOf(message: UIMessage): string | null {
  const part = message.parts.find((p) => p.type === 'data-citations') as
    | { type: 'data-citations'; data: CitationPayload }
    | undefined
  if (!part || part.data.queryLanguage === 'de') return null
  return part.data.lexicalQuery || null
}

const STAGE_COPY: Record<string, CopyKey> = {
  retrieving: 'statusRetrieving',
  reading: 'statusReading',
  validating: 'statusValidating',
  revising: 'statusRevising',
}

/**
 * What the backend is doing right now, for the "Searching…" line while a turn is in flight.
 *
 * Each stage arrives as its own `data-status` part on the assistant message as `run_turn`
 * reports it (see `orchestrator.py`), so this reflects real progress — retrieval, reading the
 * decisions, validating the answer, or revising it — not a canned, timer-driven sequence.
 */
function currentStageCopy(message: UIMessage | undefined): CopyKey {
  const stageParts = (message?.parts ?? []).filter(
    (p): p is { type: 'data-status'; data: { stage: string } } => p.type === 'data-status',
  )
  const stage = stageParts.at(-1)?.data.stage
  return (stage && STAGE_COPY[stage]) || 'searching'
}

/**
 * Loads a thread's stored messages, then hands off to `ChatConversation`.
 *
 * `useChat`'s `Chat` instance is built once per `id` and never re-reads its `messages` option
 * afterwards — so if it mounted before the stored history had loaded, it would permanently seed
 * itself with an empty conversation, and an old thread's messages would never appear. Mounting
 * `ChatConversation` only once `history` has actually arrived is what avoids that race.
 */
export default function ChatPanel({
  threadId,
  initialMessage,
  onAssistantReply,
}: {
  threadId: string
  /** A question typed on the home page before this thread existed; sent once, on arrival. */
  initialMessage?: string
  /** Called once a reply finishes streaming — lets the sidebar pick up a freshly generated title. */
  onAssistantReply?: () => void
}) {
  const [history, setHistory] = useState<UIMessage[] | null>(null)

  useEffect(() => {
    setHistory(null)
    threadMessages(threadId)
      .then((messages) => setHistory(messages.map(toUIMessage)))
      .catch(() => setHistory([]))
  }, [threadId])

  if (history === null) {
    return (
      <div className="flex-1 overflow-y-auto">
        <MessagesSkeleton />
      </div>
    )
  }

  return (
    <ChatConversation
      threadId={threadId}
      initialMessages={history}
      initialMessage={initialMessage}
      onAssistantReply={onAssistantReply}
    />
  )
}

function ChatConversation({
  threadId,
  initialMessages,
  initialMessage,
  onAssistantReply,
}: {
  threadId: string
  initialMessages: UIMessage[]
  initialMessage?: string
  onAssistantReply?: () => void
}) {
  const { copy } = useUiLanguage()
  const { user } = useAuth()
  const [input, setInput] = useState('')
  const [selected, setSelected] = useState<Citation | null>(null)
  const bottom = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const sentInitial = useRef(false)

  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        // Straight at FastAPI — no proxy, no frontend route handler.
        api: `${env.apiBaseUrl}/chat/stream`,
        // A callback, not a value: the access token refreshes mid-session, and a captured
        // copy would start producing 401s that look like a lost login.
        headers: async (): Promise<Record<string, string>> => {
          const token = await accessToken()
          return token ? { Authorization: `Bearer ${token}` } : {}
        },
        // No answer_language: the backend answers in the language the question was asked
        // in. Hardcoding 'de' here is what made English questions come back in German.
        body: { thread_id: threadId },
      }),
    [threadId],
  )

  const { messages, sendMessage, status, error, stop } = useChat({
    id: threadId,
    transport,
    messages: initialMessages,
    onFinish: () => onAssistantReply?.(),
  })

  const streaming = status === 'submitted' || status === 'streaming'

  // A fresh thread from the home page's prompt box arrives with a message already typed —
  // send it once, on arrival, so a reload never replays it.
  useEffect(() => {
    if (!initialMessage || sentInitial.current) return
    sentInitial.current = true
    if (initialMessages.length === 0) void sendMessage({ text: initialMessage })
  }, [initialMessage, initialMessages, sendMessage])

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming])

  function submit(event: FormEvent) {
    event.preventDefault()
    const question = input.trim()
    if (!question || streaming) return
    setInput('')
    void sendMessage({ text: question })
    // Keyboard users would otherwise have to tab back to the box for every question.
    inputRef.current?.focus()
  }

  // A thread with nothing in it yet gets the same centred composer as the home page — a
  // conversation already under way anchors it to the bottom instead. The switch happens the
  // instant the first message is sent, since `messages` gains an entry before the reply
  // streams back.
  const isEmpty = messages.length === 0

  const composer = (
    <form
      onSubmit={submit}
      className="border-border bg-card rounded-3xl border p-2.5 shadow-sm transition-shadow focus-within:shadow-md"
    >
      <textarea
        ref={inputRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            submit(e)
          }
        }}
        rows={2}
        placeholder={copy('inputPlaceholder')}
        className="placeholder:text-muted-foreground w-full resize-none bg-transparent px-2 py-1.5 text-sm outline-none"
      />
      <div className="flex items-center justify-end px-1 pt-1">
        {streaming ? (
          <Button type="button" variant="outline" size="sm" onClick={stop}>
            {copy('stop')}
          </Button>
        ) : (
          <SendButton disabled={!input.trim()} ariaLabel={copy('send')} />
        )}
      </div>
    </form>
  )

  const disclaimer = (
    <p className="text-muted-foreground text-xs">
      <strong className="text-foreground font-medium">{copy('disclaimerShort')}</strong> —{' '}
      {copy('disclaimerLong')}
    </p>
  )

  if (isEmpty) {
    const name = user?.email?.split('@')[0]
    return (
      <div className="flex min-w-0 flex-1 flex-col items-center justify-center px-4 pb-20">
        <div className="w-full max-w-2xl space-y-6">
          <p className="text-foreground text-center text-3xl font-medium sm:text-4xl">
            {copy(greetingKey(new Date().getHours()))}, {name}!
          </p>
          {composer}
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-4 px-4 py-8 sm:px-6">
          {messages.map((message) => (
            <div
              key={message.id}
              className={message.role === 'user' ? 'flex justify-end' : 'flex justify-start'}
            >
              {message.role === 'user' ? (
                <div className="bg-primary text-primary-foreground max-w-[80%] rounded-2xl px-4 py-2 text-sm">
                  {textOf(message)}
                </div>
              ) : (
                <AssistantMessage
                  messageId={message.id}
                  text={textOf(message)}
                  citations={citationsOf(message)}
                  lexicalQuery={lexicalQueryOf(message)}
                  initialLanguage={answerLanguageOf(message)}
                  onSelectCitation={setSelected}
                />
              )}
            </div>
          ))}

          {streaming && (
            <p className="text-muted-foreground text-sm" role="status">
              {copy(currentStageCopy(messages.at(-1)))}
            </p>
          )}

          {error && (
            <p role="alert" className="text-destructive text-sm">
              {error instanceof ApiError
                ? copy(
                    error.kind === 'unauthorized'
                      ? 'errorAuth'
                      : error.kind === 'network'
                        ? 'errorNetwork'
                        : error.kind === 'timeout'
                          ? 'errorTimeout'
                          : 'errorGeneric',
                  )
                : copy('errorGeneric')}
            </p>
          )}

          <div ref={bottom} />
        </div>
      </div>

      {selected && <SourcePanel citation={selected} onClose={() => setSelected(null)} />}

      {/* Same element carries both the centering and the padding, matching the messages
          column above exactly — splitting them across two nested divs (padding outer,
          max-width inner) is what threw the composer's left edge out of alignment with it. */}
      <div className="mx-auto w-full max-w-3xl space-y-2 px-4 py-4 sm:px-6">
        {composer}
        {disclaimer}
      </div>
    </div>
  )
}
