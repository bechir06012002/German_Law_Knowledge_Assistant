import type { ReactNode } from 'react'

/**
 * A deliberately small Markdown subset for the assistant's prose: paragraphs, `**bold**`,
 * `*italic*`, `#`/`##`/`###` headings, and a `---` divider.
 *
 * The assistant's own instructions constrain it to exactly this subset, so a full CommonMark
 * renderer — a library, and its transitive footprint — would be solving a problem that does
 * not exist here. This only ever produces React elements, never raw HTML, so it is safe by
 * construction regardless of what the model (or an adversarial passage it read) puts in the
 * text.
 */
export function renderMarkdownLite(text: string): ReactNode {
  return text
    .trim()
    .split(/\n{2,}/)
    .filter(Boolean)
    .map((block, i) => {
      const trimmed = block.trim()

      if (/^(-{3,}|\*{3,})$/.test(trimmed)) {
        return <hr key={i} className="border-border my-4" />
      }

      const heading = /^(#{1,3})\s+(.+)$/.exec(trimmed)
      if (heading) {
        const content = renderInline(heading[2])
        if (heading[1].length === 1) {
          return (
            <h2 key={i} className="mt-1 text-lg font-semibold">
              {content}
            </h2>
          )
        }
        return (
          <h3 key={i} className="mt-1 text-base font-semibold">
            {content}
          </h3>
        )
      }

      // Single newlines inside a paragraph are a soft wrap, not a line break — collapse them
      // the way Markdown does, rather than preserving them literally.
      return (
        <p key={i} className="leading-relaxed">
          {renderInline(trimmed.replace(/\n/g, ' '))}
        </p>
      )
    })
}

function renderInline(text: string): ReactNode[] {
  return text
    .split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g)
    .filter(Boolean)
    .map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i}>{part.slice(2, -2)}</strong>
      }
      if (part.startsWith('*') && part.endsWith('*')) {
        return <em key={i}>{part.slice(1, -1)}</em>
      }
      return part
    })
}
