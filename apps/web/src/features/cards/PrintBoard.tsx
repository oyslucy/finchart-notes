import type { ReactNode } from 'react'

import { CHART_TYPE_LABEL, type Card } from '../../lib/types.ts'

const CARDS_PER_PAGE = 2
const today = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'long' })

function pairs<T>(items: T[]): T[][] {
  const out: T[][] = []
  for (let i = 0; i < items.length; i += CARDS_PER_PAGE)
    out.push(items.slice(i, i + CARDS_PER_PAGE))
  return out
}

/** Print-only layout: A4 pages with the board title and two cards (chart + reading) each. */
export function PrintBoard({
  title,
  cards,
  subtitle,
}: {
  title: string
  cards: Card[]
  subtitle?: string | undefined
}) {
  const pages = pairs(cards)
  const printedOn = today.format(new Date())
  return (
    <div className="hidden print:block">
      {pages.map((page, i) => (
        <section key={page[0]?.id ?? i} className="print-page">
          <header className="flex items-baseline justify-between border-b border-[#d6d2cc] pb-[3mm]">
            <h1 className="text-[16pt] leading-tight font-semibold tracking-[-0.01em]">{title}</h1>
            <span className="text-[8pt] text-[#6f6a63] tabular">
              {subtitle ? `${subtitle} · ` : ''}
              {printedOn} · {i + 1} / {pages.length}
            </span>
          </header>
          {page.map((card) => (
            <PrintCard key={card.id} card={card} />
          ))}
        </section>
      ))}
    </div>
  )
}

function PrintCard({ card }: { card: Card }) {
  return (
    <article className="print-card">
      <div className="print-card__image">
        <img src={card.image_url} alt={card.title} loading="eager" />
      </div>
      <div className="flex min-h-0 flex-col gap-[2.5mm] overflow-hidden text-[8.5pt] leading-[1.5]">
        <div>
          <h2 className="text-[11pt] leading-snug font-semibold tracking-[-0.01em]">
            {card.title}
          </h2>
          <p className="text-[7.5pt] text-[#6f6a63] tabular">
            {CHART_TYPE_LABEL[card.chart_type] ?? card.chart_type}
            {card.period && ` · ${card.period}`}
          </p>
        </div>
        <PrintSection label="핵심 관찰">
          <ol className="flex flex-col gap-[1mm]">
            {card.takeaways.map((t, i) => (
              <li key={t} className="grid grid-cols-[3.5mm_1fr]">
                <span className="text-[#958f87] tabular">{i + 1}</span>
                <span>{t}</span>
              </li>
            ))}
          </ol>
        </PrintSection>
        <PrintSection label="해설">
          <p className="text-[#47433f]">{card.interpretation}</p>
        </PrintSection>
        {card.caveats.length > 0 && (
          <PrintSection label="주의">
            <ul className="text-[7.5pt] text-[#6f6a63]">
              {card.caveats.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </PrintSection>
        )}
        {card.user_note && (
          <PrintSection label="메모">
            <p className="whitespace-pre-wrap">{card.user_note}</p>
          </PrintSection>
        )}
      </div>
    </article>
  )
}

function PrintSection({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="border-t border-[#e4e1dc] pt-[1.5mm]">
      <h3 className="pb-[0.5mm] text-[7pt] font-medium tracking-normal text-[#958f87]">{label}</h3>
      {children}
    </section>
  )
}
