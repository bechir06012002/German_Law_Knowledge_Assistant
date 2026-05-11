/** Product-level backend calls. Mirrors the FastAPI routes in `backend/app/chat/router.py`. */

import type { Citation } from '@/lib/citations'
import { apiFetch } from '@/lib/http'

export type AnswerLanguage = 'de' | 'en'

export interface Thread {
  id: string
  title: string | null
  answer_language: string
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  translated_query: string | null
  created_at: string
  /** Stored citations, so chips survive a reload rather than only existing in the stream. */
  citations: Citation[]
}

export function listThreads(): Promise<Thread[]> {
  return apiFetch<Thread[]>('/threads')
}

export function createThread(
  title?: string,
  answerLanguage: AnswerLanguage = 'de',
): Promise<Thread> {
  return apiFetch<Thread>('/threads', {
    method: 'POST',
    body: { title, answer_language: answerLanguage },
  })
}

export function threadMessages(threadId: string): Promise<Message[]> {
  return apiFetch<Message[]>(`/threads/${threadId}/messages`)
}

export function deleteThread(threadId: string): Promise<void> {
  return apiFetch<void>(`/threads/${threadId}`, { method: 'DELETE' })
}

export function whoami(): Promise<{ id: string; email: string }> {
  return apiFetch<{ id: string; email: string }>('/me')
}

/**
 * Re-render one answer in the other language.
 *
 * Reuses the citations the answer already has — the backend does not re-run retrieval, so
 * both language versions cite exactly the same decisions. Asking the question again in the
 * other language would not: it would retrieve afresh and could surface different case law.
 */
export function switchMessageLanguage(
  messageId: string,
  answerLanguage: AnswerLanguage,
): Promise<Message> {
  return apiFetch<Message>(`/messages/${messageId}/language`, {
    method: 'POST',
    body: { answer_language: answerLanguage },
  })
}
