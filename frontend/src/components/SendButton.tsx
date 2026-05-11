import { Button } from '@/components/ui/button'

/** Icon-only submit control for a prompt box: an upward arrow, never the word "Send". */
export default function SendButton({
  disabled,
  ariaLabel,
}: {
  disabled?: boolean
  ariaLabel: string
}) {
  return (
    <Button
      type="submit"
      size="icon"
      disabled={disabled}
      aria-label={ariaLabel}
      className="rounded-full"
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M12 19V5" />
        <path d="M5 12l7-7 7 7" />
      </svg>
    </Button>
  )
}
