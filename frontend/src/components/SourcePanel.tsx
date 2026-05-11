import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { useUiLanguage } from '@/lib/uiLanguageContext'
import {
  type Citation,
  type NormRef,
  type StatuteText,
  fetchStatute,
  formatNormRef,
  uniqueNormRefs,
} from '@/lib/citations'

/**
 * The passage an answer relied on, shown in full.
 *
 * This panel is the product's whole value: a user must be able to check every claim against
 * the actual German text in one click. Nothing here is translated.
 */
export default function SourcePanel({
  citation,
  onClose,
}: {
  citation: Citation
  onClose: () => void
}) {
  const { copy } = useUiLanguage()
  const [statute, setStatute] = useState<StatuteText | null>(null)
  const [loadingRef, setLoadingRef] = useState<string | null>(null)
  const [showTranslation, setShowTranslation] = useState(false)

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function openStatute(ref: NormRef) {
    setLoadingRef(formatNormRef(ref))
    try {
      setStatute(await fetchStatute(ref.book, ref.section))
    } finally {
      setLoadingRef(null)
    }
  }

  const refs = uniqueNormRefs(citation.normRefs)

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/20"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        role="dialog"
        aria-label={copy('source')}
        className="bg-background fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col overflow-x-hidden border-l shadow-lg"
      >
        <header className="flex items-start justify-between gap-4 border-b p-5">
          <div className="space-y-1">
            {/* Verbatim German, in both answer languages — the user may type this into a
                court portal or quote it to a lawyer. */}
            <h2 className="text-base font-semibold">{citation.court}</h2>
            <p className="text-muted-foreground font-mono text-sm">{citation.fileNumber}</p>
            <p className="text-muted-foreground text-sm">
              {[citation.decisionType, citation.decisionDate].filter(Boolean).join(' · ')}
            </p>
            {citation.ecli && (
              <p className="text-muted-foreground font-mono text-xs break-all">
                {citation.ecli}
              </p>
            )}
          </div>
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label={copy('close')}>
            ×
          </Button>
        </header>

        <div className="flex-1 space-y-5 overflow-y-auto p-5">
          <div className="space-y-2">
            {/* The section label, never a page number: German decisions have named sections
                and no page concept. */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="bg-muted rounded-md px-2 py-0.5 text-xs font-medium">
                {citation.section ?? copy('sectionUnknown')}
              </span>
              {citation.paragraphNumber !== null && (
                <span className="bg-muted rounded-md px-2 py-0.5 text-xs font-medium">
                  Rn. {citation.paragraphNumber}
                </span>
              )}
            </div>
            {/* The passage is shown in the original German, always. Design rule: a translated
                quote is a paraphrase presented as evidence. A translation may sit *beside*
                the German, clearly labelled, never instead of it. */}
            <div className="space-y-1">
              <p className="text-muted-foreground text-xs font-medium">
                {copy('originalGerman')}
              </p>
              <p className="text-sm leading-relaxed break-words whitespace-pre-wrap" lang="de">
                {citation.text}
              </p>
            </div>

            <button
              type="button"
              onClick={() => setShowTranslation((shown) => !shown)}
              className="text-muted-foreground text-xs underline underline-offset-4"
            >
              {showTranslation ? copy('hideTranslation') : copy('showTranslation')}
            </button>

            {showTranslation && (
              <div className="border-muted-foreground/30 space-y-1 border-l-2 pl-3">
                <p className="text-muted-foreground text-xs">{copy('unofficialTranslation')}</p>
                <p className="text-muted-foreground text-sm leading-relaxed">
                  <a
                    href={`https://translate.google.com/?sl=de&tl=en&op=translate&text=${encodeURIComponent(citation.text)}`}
                    target="_blank"
                    rel="noreferrer"
                    className="underline underline-offset-4"
                  >
                    {copy('showTranslation')}
                  </a>
                </p>
              </div>
            )}
          </div>

          {refs.length > 0 && (
            <div className="space-y-2 border-t pt-4">
              <h3 className="text-sm font-medium">{copy('appliedNorms')}</h3>
              <div className="flex flex-wrap gap-1.5">
                {refs.map((ref) => (
                  <button
                    key={`${ref.book}-${ref.section}`}
                    type="button"
                    onClick={() => void openStatute(ref)}
                    className="border-border hover:bg-muted rounded-md border px-2 py-1 font-mono text-xs"
                  >
                    {loadingRef === formatNormRef(ref) ? '…' : formatNormRef(ref)}
                  </button>
                ))}
              </div>

              {statute && (
                <div className="bg-muted/50 mt-2 space-y-1 rounded-lg p-3">
                  <p className="font-mono text-xs font-medium">
                    {statute.section} {statute.book}
                  </p>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">
                    {statute.text ?? copy('statuteNotInCorpus')}
                  </p>
                </div>
              )}
            </div>
          )}

          {citation.sourceUrl && (
            <div className="border-t pt-4">
              <a
                href={citation.sourceUrl}
                target="_blank"
                rel="noreferrer"
                className="text-sm underline underline-offset-4"
              >
                {copy('openSource')}
              </a>
            </div>
          )}
        </div>

        <footer className="text-muted-foreground border-t p-4 text-xs">
          {copy('publicDomain')}
        </footer>
      </aside>
    </>
  )
}
