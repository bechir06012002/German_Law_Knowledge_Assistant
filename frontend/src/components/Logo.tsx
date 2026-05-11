/**
 * The Judges Said mark: a gavel striking its block.
 *
 * Inline SVG rather than an image file — it stays sharp at every size, needs no build step or
 * network request, and the dark tile is part of the mark, so it reads correctly in both light
 * and dark themes without a second variant.
 *
 * Every rotated piece is positioned with `translate(cx cy) rotate(deg)` and drawn around its
 * own origin. Rotating a rect placed by `x`/`y` pivots it around the canvas corner instead of
 * its centre, which is what threw the head and handle across the tile the first time.
 */
export default function Logo({
  size = 32,
  className,
  title = 'Judges Said',
}: {
  size?: number
  className?: string
  /** null for a decorative instance sitting next to the wordmark. */
  title?: string | null
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 336 336"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role={title ? 'img' : undefined}
      aria-label={title ?? undefined}
      aria-hidden={title ? undefined : true}
    >
      <rect width="336" height="336" rx="76" fill="#111C29" />

      {/* Sound block */}
      <rect x="78" y="243" width="184" height="33" rx="9" fill="#BE9558" />

      {/* Handle — long axis runs lower-left to upper-right */}
      <g transform="translate(106 188) rotate(-27)">
        <rect x="-76" y="-11" width="152" height="22" rx="11" fill="#A97C48" />
      </g>

      {/* Collar where the handle meets the head */}
      <g transform="translate(160 161) rotate(-27)">
        <rect x="-24" y="-14" width="48" height="28" rx="3" fill="#C9A263" />
      </g>

      {/* Head — square to the handle.
          A tall rect and a wide rect rotated by the SAME angle are 90° apart, so the head
          carries the handle's -27°. Giving it its own angle (it had +30°) put the two only
          33° apart, which is the lean that looked wrong. */}
      <g transform="translate(198 158) rotate(-27)">
        <rect x="-33" y="-65" width="66" height="130" rx="14" fill="#8B6742" />
      </g>

      {/* Impact marks */}
      <g stroke="#5A6B7C" strokeWidth="9" strokeLinecap="round">
        <line x1="270" y1="192" x2="298" y2="163" />
        <line x1="276" y1="208" x2="312" y2="201" />
        <line x1="274" y1="224" x2="306" y2="235" />
      </g>
    </svg>
  )
}

/** Mark plus wordmark, for page headers. */
export function Wordmark({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <span className={`flex items-center gap-2.5 ${className ?? ''}`}>
      <Logo size={size} title={null} />
      <span className="text-lg font-semibold tracking-tight">Judges Said</span>
    </span>
  )
}
