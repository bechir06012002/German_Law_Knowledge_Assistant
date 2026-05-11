import { useState } from 'react'

import CitationChips from '@/components/CitationChips'
import LanguageToggle from '@/components/LanguageToggle'
import { switchMessageLanguage } from '@/lib/api'
import type { Citation } from '@/lib/citations'
import type { Language } from '@/lib/language'
import { renderMarkdownLite } from '@/lib/markdownLite'
import { useUiLanguage } from '@/lib/uiLanguageContext'

/**
 * One assistant answer: prose, the language toggle, and its citations.
 *
 * The toggle calls `POST /messages/{id}/language`, which re-renders the prose from the
 * citations this answer already has. It deliberately does *not* re-ask the question: that
 * would re-run retrieval and could cite different decisions for the same situation, which is
 * exactly the trust failure the grounding contract exists to prevent.
 */
export default function AssistantMessage({
  messageId,
  text,
  citations,
  lexicalQuery,
  initialLanguage = 'de',
  onSelectCitation,
}: {
  messageId: string
  text: string
  citations: Citation[]
  lexicalQuery: string | null
  /** The language this answer was written in — the toggle must not claim 'DE' on an
   *  English answer. */
  initialLanguage?: Language
  onSelectCitation: (citation: Citation) => void
}) {
  const { copy } = useUiLanguage()
  const [answerLanguage, setAnswerLanguage] = useState<Language>(initialLanguage)
  // An override, NOT a copy of `text`. Copying it into state froze the value captured on
  // first render — which, for a streaming answer, is the empty string before any delta has
  // arrived, so the bubble stayed blank forever. The streamed text must flow straight
  // through; state only holds a re-rendered translation.
  const [override, setOverride] = useState<string | null>(null)
  const prose = override ?? text
  const [busy, setBusy] = useState(false)
  const [switched, setSwitched] = useState(false)

  // A streamed message has a client-side id and no stored citations yet; there is nothing to
  // re-render from, so the toggle stays hidden until the answer has been persisted.
  const canSwitch = citations.length > 0 && /^[0-9a-f-]{36}$/i.test(messageId)

  async function change(next: Language) {
    if (next === answerLanguage || busy) return
    setBusy(true)
    try {
      const updated = await switchMessageLanguage(messageId, next)
      setOverride(updated.content)
      setAnswerLanguage(next)
      setSwitched(true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="w-full space-y-1.5">
      <div className="space-y-3 text-sm">
        {busy ? copy('switchingLanguage') : renderMarkdownLite(prose)}
      </div>

      {lexicalQuery && (
        <p className="text-muted-foreground px-1 text-xs">
          {copy('searchedInGerman')} <span className="font-mono">{lexicalQuery}</span>
        </p>
      )}

      {canSwitch && (
        <div className="flex flex-wrap items-center gap-3 px-1">
          <LanguageToggle
            value={answerLanguage}
            onChange={(next) => void change(next)}
            label={copy('answerLanguage')}
            disabled={busy}
          />
          {switched && (
            <span className="text-muted-foreground text-xs">{copy('sameEvidence')}</span>
          )}
        </div>
      )}

      <CitationChips citations={citations} onSelect={onSelectCitation} />
    </div>
  )
}
