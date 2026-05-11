/**
 * Decorative backdrop for the sign-in / sign-up screen: a soft brass-on-navy glow plus a
 * faint courthouse silhouette and scales-of-justice motif, so the auth screen reads as a
 * legal product rather than a generic form. Everything renders in `currentColor` at low
 * opacity and rides the existing `--primary`/`--foreground` theme tokens, so it holds up in
 * both light and dark mode without a second variant. Purely decorative — `aria-hidden`.
 */
export default function AuthBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-background" aria-hidden="true">
      {/* Warm glow behind the card, deep navy vignette in the corners */}
      <div
        className="absolute left-1/2 top-[-10%] h-[70svh] w-[70svh] -translate-x-1/2 rounded-full opacity-40 blur-3xl"
        style={{ background: 'radial-gradient(circle, var(--primary) 0%, transparent 70%)' }}
      />
      <div
        className="absolute -bottom-1/3 -left-1/4 h-[60svh] w-[60svh] rounded-full opacity-20 blur-3xl"
        style={{ background: 'radial-gradient(circle, var(--chart-3) 0%, transparent 70%)' }}
      />

      {/* Fine dot grid for texture */}
      <svg className="absolute inset-0 h-full w-full text-foreground opacity-[0.05]">
        <pattern id="auth-grid" width="28" height="28" patternUnits="userSpaceOnUse">
          <circle cx="1.5" cy="1.5" r="1.5" fill="currentColor" />
        </pattern>
        <rect width="100%" height="100%" fill="url(#auth-grid)" />
      </svg>

      {/* Scales of justice, upper right */}
      <svg
        viewBox="0 0 200 200"
        className="absolute -right-10 -top-10 h-64 w-64 text-foreground opacity-[0.06] sm:h-80 sm:w-80"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <line x1="100" y1="20" x2="100" y2="160" />
        <line x1="40" y1="45" x2="160" y2="45" />
        <path d="M40 45 L20 90 a20 20 0 0 0 40 0 Z" />
        <path d="M160 45 L140 90 a20 20 0 0 0 40 0 Z" />
        <line x1="70" y1="180" x2="130" y2="180" />
        <line x1="100" y1="160" x2="100" y2="180" />
      </svg>

      {/* Courthouse colonnade, footer */}
      <svg
        viewBox="0 0 600 140"
        preserveAspectRatio="xMidYMax slice"
        className="absolute inset-x-0 bottom-0 h-40 w-full text-foreground opacity-[0.05] sm:h-52"
        fill="currentColor"
      >
        <rect x="0" y="118" width="600" height="10" />
        {Array.from({ length: 9 }, (_, i) => (
          <rect key={i} x={20 + i * 66} y="40" width="18" height="78" rx="2" />
        ))}
        <polygon points="0,40 300,0 600,40" />
      </svg>
    </div>
  )
}
