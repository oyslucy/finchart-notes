import { useMemo, useState } from 'react'

import { Button } from '../../components/ui/Button.tsx'
import { Dialog } from '../../components/ui/Dialog.tsx'
import { cx } from '../../design/cx.ts'
import type { Card } from '../../lib/types.ts'

type Mode = 'period' | 'pick'
type Preset = '1w' | '1m' | '3m' | 'all'

const PRESETS: [Preset, string][] = [
  ['1w', '1주'],
  ['1m', '1개월'],
  ['3m', '3개월'],
  ['all', '전체'],
]
const CARDS_PER_PAGE = 2
const dateLabel = new Intl.DateTimeFormat('ko-KR', { month: 'numeric', day: 'numeric' })

function isoDate(d: Date): string {
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

function presetRange(preset: Preset, cards: Card[]): [string, string] {
  const today = new Date()
  const from = new Date(today)
  if (preset === '1w') from.setDate(from.getDate() - 7)
  if (preset === '1m') from.setMonth(from.getMonth() - 1)
  if (preset === '3m') from.setMonth(from.getMonth() - 3)
  if (preset === 'all') {
    const oldest = cards.reduce((min, c) => Math.min(min, Date.parse(c.created_at)), Date.now())
    return [isoDate(new Date(oldest)), isoDate(today)]
  }
  return [isoDate(from), isoDate(today)]
}

/** Inclusive local-day range check on a card's creation time. */
function inRange(card: Card, from: string, to: string): boolean {
  const created = new Date(card.created_at)
  const start = new Date(`${from}T00:00:00`)
  const end = new Date(`${to}T23:59:59.999`)
  return created >= start && created <= end
}

export interface ExportSelection {
  cards: Card[]
  label: string
}

interface ExportDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  cards: Card[]
  onExport: (selection: ExportSelection) => void
}

export function ExportDialog({ open, onOpenChange, cards, onExport }: ExportDialogProps) {
  const [mode, setMode] = useState<Mode>('period')
  const [preset, setPreset] = useState<Preset | null>('1m')
  // The parent remounts this dialog on every open (key), so initial state is the reset.
  const [[from, to], setRange] = useState(() => presetRange('1m', cards))
  const [picked, setPicked] = useState<Set<string>>(
    () => new Set(cards.filter((c) => inRange(c, from, to)).map((c) => c.id)),
  )

  const periodCards = useMemo(() => cards.filter((c) => inRange(c, from, to)), [cards, from, to])
  const selected = mode === 'period' ? periodCards : cards.filter((c) => picked.has(c.id))
  const pages = Math.ceil(selected.length / CARDS_PER_PAGE)

  const togglePick = (id: string) => {
    setPicked((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }
  const allPicked = cards.length > 0 && picked.size === cards.length

  return (
    <Dialog
      size="lg"
      open={open}
      onOpenChange={onOpenChange}
      title="PDF로 내보내기"
      description="한 쪽에 카드 2장씩, 차트와 해설을 함께 출력합니다."
      footer={
        <div className="flex w-full items-center justify-between gap-3">
          <span className="text-[13px] text-text-muted tabular" aria-live="polite">
            {selected.length}장 · {pages}쪽
          </span>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              onClick={() => {
                onOpenChange(false)
              }}
            >
              취소
            </Button>
            <Button
              variant="primary"
              disabled={selected.length === 0}
              onClick={() => {
                onExport({
                  cards: selected,
                  label:
                    mode === 'period'
                      ? `${from} ~ ${to}`
                      : `선택한 카드 ${String(selected.length)}장`,
                })
              }}
            >
              PDF로 내보내기
            </Button>
          </div>
        </div>
      }
    >
      <div className="flex flex-col gap-4 pb-1">
        <div
          role="tablist"
          aria-label="출력 범위"
          className="flex gap-4 border-b border-border text-[14px]"
        >
          {(
            [
              ['period', '기간'],
              ['pick', '직접 선택'],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={mode === value}
              onClick={() => {
                setMode(value)
              }}
              className={cx(
                '-mb-px border-b pb-2 transition-colors duration-150',
                mode === value
                  ? 'border-text font-medium text-text'
                  : 'border-transparent text-text-muted hover:text-text',
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {mode === 'period' ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={preset === value}
                  onClick={() => {
                    setPreset(value)
                    setRange(presetRange(value, cards))
                  }}
                  className={cx(
                    'h-7 rounded-full border px-3 text-[13px] transition-colors duration-150',
                    preset === value
                      ? 'border-accent bg-accent-subtle font-medium text-accent'
                      : 'border-border text-text-secondary hover:border-border-strong',
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2 text-[14px]">
              <DateInput
                label="시작일"
                value={from}
                max={to}
                onChange={(v) => {
                  setPreset(null)
                  setRange([v, to])
                }}
              />
              <span className="text-text-faint">~</span>
              <DateInput
                label="종료일"
                value={to}
                min={from}
                onChange={(v) => {
                  setPreset(null)
                  setRange([from, v])
                }}
              />
            </div>
            <p className="text-[13px] text-text-muted">
              카드를 올린 날짜 기준으로 {periodCards.length}장이 포함됩니다.
            </p>
          </div>
        ) : (
          <div className="flex flex-col">
            <label className="flex h-9 items-center gap-2.5 border-b border-border px-1 text-[13px] text-text-secondary">
              <input
                type="checkbox"
                checked={allPicked}
                ref={(el) => {
                  if (el) el.indeterminate = picked.size > 0 && !allPicked
                }}
                onChange={() => {
                  setPicked(allPicked ? new Set() : new Set(cards.map((c) => c.id)))
                }}
                className="size-4 accent-[var(--accent)]"
              />
              전체 선택
            </label>
            <ul className="max-h-[46dvh] overflow-y-auto">
              {cards.map((card) => (
                <li key={card.id}>
                  <label className="flex cursor-pointer items-center gap-3 rounded-md px-1 py-2 hover:bg-bg-subtle">
                    <input
                      type="checkbox"
                      checked={picked.has(card.id)}
                      onChange={() => {
                        togglePick(card.id)
                      }}
                      className="size-4 shrink-0 accent-[var(--accent)]"
                    />
                    <img
                      src={card.thumb_url}
                      alt=""
                      className="h-10 w-14 shrink-0 rounded-sm border border-border bg-bg-subtle object-contain"
                    />
                    <span className="min-w-0 flex-1 truncate text-[14px]">{card.title}</span>
                    <span className="shrink-0 text-[12px] text-text-faint tabular">
                      {dateLabel.format(new Date(card.created_at))}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Dialog>
  )
}

function DateInput({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string
  value: string
  min?: string
  max?: string
  onChange: (value: string) => void
}) {
  return (
    <input
      type="date"
      aria-label={label}
      value={value}
      min={min}
      max={max}
      onChange={(e) => {
        if (e.target.value) onChange(e.target.value)
      }}
      className="h-9 rounded-md border border-border bg-surface px-2.5 text-[14px] tabular hover:border-border-strong focus:border-accent focus:shadow-[0_0_0_3px_var(--focus-ring)] focus:outline-none"
    />
  )
}
