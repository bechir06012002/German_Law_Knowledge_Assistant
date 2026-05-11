/**
 * Decorative backdrop for the chat screen: the same dot grid and soft glow language as
 * `AuthBackground`, so the two screens feel like one product, without repeating its gavel/
 * scale motifs — the chat screen is where the user reads, so it stays quieter. `currentColor`
 * on the `--foreground` token and the `--primary`/`--chart-3` gradient tokens keep it correct
 * in both themes; purely decorative, so `aria-hidden`.
 */
export default function ChatBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-background" aria-hidden="true">
      {/* Faint full-bleed wash tying the two corner glows together */}
      <div
        className="absolute inset-0 opacity-[0.12]"
        style={{ background: 'linear-gradient(135deg, var(--primary) 0%, transparent 45%, transparent 55%, var(--chart-3) 100%)' }}
      />

      {/* Soft glows, opposite corners */}
      <div
        className="absolute -left-1/4 -top-1/4 h-[80svh] w-[80svh] rounded-full opacity-45 blur-3xl"
        style={{ background: 'radial-gradient(circle, var(--primary) 0%, transparent 70%)' }}
      />
      <div
        className="absolute -bottom-1/4 -right-1/4 h-[75svh] w-[75svh] rounded-full opacity-35 blur-3xl"
        style={{ background: 'radial-gradient(circle, var(--chart-3) 0%, transparent 70%)' }}
      />

      {/* Fine dot grid, horizontal and vertical */}
      <svg className="absolute inset-0 h-full w-full text-foreground opacity-[0.05]">
        <pattern id="chat-grid" width="28" height="28" patternUnits="userSpaceOnUse">
          <circle cx="1.5" cy="1.5" r="1.5" fill="currentColor" />
        </pattern>
        <rect width="100%" height="100%" fill="url(#chat-grid)" />
      </svg>
    </div>
  )
}
