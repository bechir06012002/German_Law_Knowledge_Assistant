import type { Citation } from '@/lib/citations'

/**
 * The chips under an assistant message: court · Aktenzeichen · date.
 *
 * Rendered verbatim in German whatever language the answer is in — a localized court name or
 * a reformatted Aktenzeichen would be useless to someone quoting it to a lawyer.
 */
export default function CitationChips({
  citations,
  onSelect,
}: {
  citations: Citation[]
  onSelect: (citation: Citation) => void
}) {
  if (citations.length === 0) return null

  return (
    <div className="mt-2 flex flex-wrap gap-1.5" role="list" aria-label="Fundstellen">
      {citations.map((citation, index) => (
        <button
          key={citation.chunkId}
          type="button"
          onClick={() => onSelect(citation)}
          title={`${citation.court} · ${citation.fileNumber} · ${citation.decisionDate}`}
          aria-label={[
            `Fundstelle ${index + 1}`,
            citation.court,
            citation.fileNumber,
            citation.decisionDate,
            citation.section,
            citation.paragraphNumber ? `Randnummer ${citation.paragraphNumber}` : null,
          ]
            .filter(Boolean)
            .join(', ')}
          role="listitem"
          className="border-border hover:bg-muted flex max-w-full items-center gap-1.5 rounded-md border px-2 py-1 text-left text-xs"
        >
          <span className="text-muted-foreground font-mono">{index + 1}</span>
          <span className="max-w-[16rem] truncate">{citation.court}</span>
          <span className="text-muted-foreground font-mono">{citation.fileNumber}</span>
          <span className="text-muted-foreground">{citation.decisionDate}</span>
        </button>
      ))}
    </div>
  )
}
