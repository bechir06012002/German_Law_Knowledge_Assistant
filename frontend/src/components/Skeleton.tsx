import { cn } from '@/lib/utils'

/**
 * A loading placeholder shaped like the content it replaces.
 *
 * Better than a spinner here because thread titles and messages have predictable shapes, so
 * the layout does not jump when the real content arrives.
 */
export function Skeleton({
  className,
  style,
}: {
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <div
      aria-hidden="true"
      style={style}
      className={cn('bg-muted animate-pulse rounded-md', className)}
    />
  )
}

export function ThreadListSkeleton() {
  return (
    <div className="space-y-1 px-2" role="status" aria-label="Loading">
      {[70, 55, 80, 45].map((width, index) => (
        <Skeleton key={index} className="h-7" style={{ width: `${width}%` }} />
      ))}
    </div>
  )
}

export function MessagesSkeleton() {
  return (
    <div className="mx-auto max-w-3xl space-y-4 px-4 py-8 sm:px-6" role="status" aria-label="Loading">
      <div className="flex justify-end">
        <Skeleton className="h-10 w-2/3 rounded-2xl" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-24 w-5/6 rounded-2xl" />
        <div className="flex gap-1.5">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-6 w-36" />
        </div>
      </div>
    </div>
  )
}
