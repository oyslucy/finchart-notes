import type { ReactNode } from 'react'

import { cx } from '../../design/cx.ts'
import { Skeleton } from './Skeleton.tsx'

export interface ChartCardData {
  title: string
  chartType: string
  period: string | null
  imageUrl: string | null
  takeaways: string[]
  interpretation: string
  caveats: string[]
  note?: string | null
}

interface ChartCardProps {
  card: ChartCardData
  actions?: ReactNode
  className?: string
}

/** One card per screenshot. Sections are separated by hairlines, never nested boxes. */
export function ChartCard({ card, actions, className }: ChartCardProps) {
  return (
    <article className={cx('rounded-lg border border-border bg-surface', className)}>
      <header className="flex items-start justify-between gap-4 px-5 pt-4 pb-3">
        <div className="flex min-w-0 flex-col gap-1">
          <h3 className="text-[17px] leading-snug">{card.title}</h3>
          <p className="flex items-center gap-1.5 text-[12px] text-text-muted tabular">
            <span>{card.chartType}</span>
            {card.period && (
              <>
                <span aria-hidden="true" className="text-text-faint">
                  ·
                </span>
                <span>{card.period}</span>
              </>
            )}
          </p>
        </div>
        {actions && <div className="-mr-1.5 flex shrink-0 items-center gap-0.5">{actions}</div>}
      </header>

      <figure className="mx-5 overflow-hidden rounded-md border border-border bg-bg-subtle">
        {card.imageUrl ? (
          <img src={card.imageUrl} alt={card.title} className="block w-full" loading="lazy" />
        ) : (
          <div className="aspect-[16/9]" />
        )}
      </figure>

      <CardSection label="핵심 관찰">
        <ol className="flex flex-col gap-1.5">
          {card.takeaways.map((t, i) => (
            <li key={t} className="grid grid-cols-[16px_1fr] gap-1.5 text-[14px] leading-[1.6]">
              <span className="pt-px text-[12px] text-text-faint tabular">{i + 1}</span>
              <span>{t}</span>
            </li>
          ))}
        </ol>
      </CardSection>

      <CardSection label="해설">
        <p className="text-[14px] leading-[1.7] text-text-secondary">{card.interpretation}</p>
      </CardSection>

      {card.caveats.length > 0 && (
        <CardSection label="주의">
          <ul className="flex flex-col gap-1">
            {card.caveats.map((c) => (
              <li key={c} className="text-[13px] leading-[1.6] text-text-muted">
                {c}
              </li>
            ))}
          </ul>
        </CardSection>
      )}

      {card.note && (
        <CardSection label="메모">
          <p className="text-[14px] leading-[1.6] whitespace-pre-wrap">{card.note}</p>
        </CardSection>
      )}
    </article>
  )
}

function CardSection({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="mx-5 flex flex-col gap-1.5 border-t border-border py-3.5 first-of-type:mt-4">
      <h4 className="text-[12px] font-medium tracking-normal text-text-faint">{label}</h4>
      <div className="min-w-0">{children}</div>
    </section>
  )
}

export function ChartCardSkeleton() {
  return (
    <div
      className="rounded-lg border border-border bg-surface"
      aria-busy="true"
      aria-label="카드 불러오는 중"
    >
      <div className="flex flex-col gap-2 px-5 pt-4 pb-3">
        <Skeleton className="h-5 w-2/3" />
        <Skeleton className="h-3 w-1/3" />
      </div>
      <Skeleton className="mx-5 aspect-[16/9] rounded-md" />
      {[0, 1].map((i) => (
        <div
          key={i}
          className={cx(
            'mx-5 flex flex-col gap-2 border-t border-border py-3.5',
            i === 0 && 'mt-4',
          )}
        >
          <Skeleton className="h-3 w-10" />
          <div className="flex flex-col gap-2">
            <Skeleton className="h-3.5 w-full" />
            <Skeleton className="h-3.5 w-5/6" />
          </div>
        </div>
      ))}
    </div>
  )
}
