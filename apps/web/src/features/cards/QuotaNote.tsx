import { cx } from '../../design/cx.ts'
import { useQuota } from './queries.ts'

const LOW = 5

function resetTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' })
}

/** "오늘 27회 남음" next to an upload bar; turns accent when few are left, red at none. */
export function QuotaNote({ className }: { className?: string }) {
  const quota = useQuota()
  if (!quota.data) return null
  const { remaining, limit, resets_at } = quota.data
  return (
    <span
      title={`하루 ${String(limit)}회까지 분석할 수 있습니다. 매일 ${resetTime(resets_at)}에 다시 채워집니다.`}
      className={cx(
        'shrink-0 text-[12px] whitespace-nowrap tabular',
        remaining === 0
          ? 'text-danger'
          : remaining <= LOW
            ? 'font-medium text-accent'
            : 'text-text-faint',
        className,
      )}
    >
      {remaining === 0
        ? `오늘 횟수 소진 · ${resetTime(resets_at)} 초기화`
        : `오늘 ${String(remaining)}회 남음`}
    </span>
  )
}
