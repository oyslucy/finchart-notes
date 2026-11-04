import { motion } from 'motion/react'
import { Link } from 'react-router'

import { appearTransition } from '../../design/motion.ts'
import { CHART_TYPE_LABEL, type Card } from '../../lib/types.ts'

const dateFormat = new Intl.DateTimeFormat('ko-KR', { month: 'numeric', day: 'numeric' })

interface ThumbnailCardProps {
  card: Card
  index: number
  boardTitle?: string
}

export function ThumbnailCard({ card, index, boardTitle }: ThumbnailCardProps) {
  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      // A short stagger for the first row only, so long grids don't feel slow.
      transition={{ ...appearTransition, delay: Math.min(index, 4) * 0.03 }}
    >
      <Link
        to={`/boards/${card.board_id}/cards/${card.id}`}
        className="group flex h-full flex-col overflow-hidden rounded-lg border border-border bg-surface transition-[border-color,box-shadow] duration-150 hover:border-border-strong hover:shadow-xs"
      >
        <div className="relative aspect-[4/3] overflow-hidden border-b border-border bg-bg-subtle">
          {/* Absolutely positioned so tall crops never stretch the 4:3 frame. */}
          <img
            src={card.thumb_url}
            alt={card.title}
            loading="lazy"
            className="absolute inset-2 size-[calc(100%-1rem)] object-contain"
          />
        </div>
        <div className="flex flex-1 flex-col gap-1 px-3.5 pt-3 pb-3">
          <h3 className="line-clamp-2 text-[14px] leading-snug font-medium">{card.title}</h3>
          <p className="truncate text-[12px] text-text-muted tabular">
            {CHART_TYPE_LABEL[card.chart_type] ?? card.chart_type}
            {card.period && ` · ${card.period}`}
          </p>
          <div className="mt-auto flex items-center justify-between gap-2 pt-2 text-[12px] text-text-faint">
            <span className="truncate">{boardTitle ?? (card.user_note ? '메모 있음' : '')}</span>
            <span className="shrink-0 tabular">{dateFormat.format(new Date(card.created_at))}</span>
          </div>
        </div>
      </Link>
    </motion.li>
  )
}

export function ThumbnailSkeleton({ label }: { label?: string }) {
  return (
    <li
      className="overflow-hidden rounded-lg border border-border bg-surface"
      aria-busy="true"
      aria-label={label}
    >
      <div className="aspect-[4/3] animate-[skeleton_1.6s_ease-in-out_infinite] bg-bg-muted" />
      <div className="flex flex-col gap-2 px-3.5 py-3">
        <div className="h-3.5 w-4/5 rounded-sm bg-bg-muted" />
        <div className="h-3 w-1/2 rounded-sm bg-bg-muted" />
        {label && <span className="pt-1 text-[12px] text-text-faint">{label}</span>}
      </div>
    </li>
  )
}

export const THUMBNAIL_GRID = 'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'
