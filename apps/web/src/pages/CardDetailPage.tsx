import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Pencil,
  Pin,
  PinOff,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router'

import { ChartCard, ChartCardSkeleton } from '../components/ui/ChartCard.tsx'
import { IconButton } from '../components/ui/IconButton.tsx'
import { Kbd } from '../components/ui/Kbd.tsx'
import { useToast } from '../components/ui/toast-context.ts'
import { durations, easeOut } from '../design/motion.ts'
import { useBoards } from '../features/boards/queries.ts'
import {
  DeleteCardDialog,
  EditCardDialog,
  ReanalyzeCardDialog,
} from '../features/cards/CardDialogs.tsx'
import { useCards, useReorderCards } from '../features/cards/queries.ts'
import { useTogglePin } from '../features/cards/useTogglePin.ts'
import { errorMessage } from '../lib/api.ts'
import { CHART_TYPE_LABEL, type Card } from '../lib/types.ts'

function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ['INPUT', 'TEXTAREA'].includes(target.tagName))
  )
}

export default function CardDetailPage() {
  const { boardId = '', cardId = '' } = useParams()
  const boards = useBoards()
  const cards = useCards(boardId)
  const reorder = useReorderCards(boardId)
  const navigate = useNavigate()
  const toast = useToast()
  const [editOpen, setEditOpen] = useState(false)
  const [reanalyzeOpen, setReanalyzeOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const list = cards.data ?? []
  const index = list.findIndex((c) => c.id === cardId)
  const card = list[index]
  const prev = list[index - 1]
  const next = list[index + 1]
  const boardTitle = boards.data?.find((b) => b.id === boardId)?.title ?? ''
  // Reordering only makes sense within the pinned group or within the unpinned group.
  const canMoveUp = prev !== undefined && card !== undefined && prev.pinned === card.pinned
  const canMoveDown = next !== undefined && card !== undefined && next.pinned === card.pinned
  const boardPath = `/boards/${boardId}`

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTyping(event.target) || editOpen || deleteOpen || reanalyzeOpen) return
      if (event.key === 'ArrowLeft' && prev) void navigate(`${boardPath}/cards/${prev.id}`)
      if (event.key === 'ArrowRight' && next) void navigate(`${boardPath}/cards/${next.id}`)
      if (event.key === 'Escape') void navigate(boardPath)
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  }, [prev, next, boardPath, navigate, editOpen, deleteOpen, reanalyzeOpen])

  if (cards.isSuccess && !card) return <Navigate to={boardPath} replace />

  const move = (direction: -1 | 1) => {
    const ids = list.map((c) => c.id)
    const target = index + direction
    if (target < 0 || target >= ids.length) return
    ids.splice(index, 1)
    ids.splice(target, 0, cardId)
    reorder.mutate(ids, {
      onError: (e) => {
        toast({ title: '순서를 바꾸지 못했습니다', description: errorMessage(e), tone: 'danger' })
      },
    })
  }

  return (
    <div className="mx-auto flex max-w-[1280px] flex-col gap-4 px-4 pt-5 pb-16 md:px-8">
      <nav className="flex flex-wrap items-center justify-between gap-2">
        <Link
          to={boardPath}
          className="-ml-1.5 inline-flex h-8 min-w-0 items-center gap-1.5 rounded-md px-1.5 text-[14px] text-text-secondary hover:bg-bg-muted hover:text-text"
        >
          <ArrowLeft size={16} strokeWidth={1.5} aria-hidden="true" />
          <span className="truncate">{boardTitle || '보드'}</span>
        </Link>

        {card && (
          <div className="flex items-center gap-1">
            <IconButton
              icon={ChevronsLeft}
              label="앞으로 옮기기"
              size="sm"
              disabled={!canMoveUp || reorder.isPending}
              onClick={() => {
                move(-1)
              }}
            />
            <IconButton
              icon={ChevronsRight}
              label="뒤로 옮기기"
              size="sm"
              disabled={!canMoveDown || reorder.isPending}
              onClick={() => {
                move(1)
              }}
            />
            <span className="mx-1 h-4 w-px bg-border" aria-hidden="true" />
            <PinButton card={card} />
            <IconButton
              icon={Pencil}
              label="수정"
              size="sm"
              onClick={() => {
                setEditOpen(true)
              }}
            />
            <IconButton
              icon={RefreshCw}
              label="다시 분석"
              size="sm"
              onClick={() => {
                setReanalyzeOpen(true)
              }}
            />
            <IconButton
              icon={Trash2}
              label="삭제"
              size="sm"
              onClick={() => {
                setDeleteOpen(true)
              }}
            />
            <span className="mx-1 h-4 w-px bg-border" aria-hidden="true" />
            <IconButton
              icon={ChevronLeft}
              label="이전 카드"
              shortcut="←"
              size="sm"
              disabled={!prev}
              onClick={() => {
                if (prev) void navigate(`${boardPath}/cards/${prev.id}`)
              }}
            />
            <span className="min-w-12 text-center text-[13px] text-text-muted tabular">
              {index + 1} / {list.length}
            </span>
            <IconButton
              icon={ChevronRight}
              label="다음 카드"
              shortcut="→"
              size="sm"
              disabled={!next}
              onClick={() => {
                if (next) void navigate(`${boardPath}/cards/${next.id}`)
              }}
            />
          </div>
        )}
      </nav>

      {!card ? (
        <ChartCardSkeleton />
      ) : (
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={card.id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: durations.interact, ease: easeOut }}
          >
            <ChartCard
              card={{
                title: card.title,
                chartType: CHART_TYPE_LABEL[card.chart_type] ?? card.chart_type,
                period: card.period,
                imageUrl: card.image_url,
                takeaways: card.takeaways,
                interpretation: card.interpretation,
                caveats: card.caveats,
                note: card.user_note,
              }}
            />
          </motion.div>
        </AnimatePresence>
      )}

      {card && (
        <p className="hidden items-center justify-center gap-1.5 text-[12px] text-text-faint md:flex">
          <Kbd>←</Kbd> <Kbd>→</Kbd> 카드 넘기기 · <Kbd>Esc</Kbd> 보드로
        </p>
      )}

      {card && (
        <>
          <EditCardDialog card={card} open={editOpen} onOpenChange={setEditOpen} />
          <ReanalyzeCardDialog card={card} open={reanalyzeOpen} onOpenChange={setReanalyzeOpen} />
          <DeleteCardDialog
            card={card}
            open={deleteOpen}
            onOpenChange={setDeleteOpen}
            onDeleted={() => {
              const fallback = next ?? prev
              void navigate(fallback ? `${boardPath}/cards/${fallback.id}` : boardPath, {
                replace: true,
              })
            }}
          />
        </>
      )}
    </div>
  )
}

function PinButton({ card }: { card: Card }) {
  const togglePin = useTogglePin(card)
  return (
    <IconButton
      icon={card.pinned ? PinOff : Pin}
      label={card.pinned ? '고정 해제' : '맨 위에 고정'}
      size="sm"
      className={card.pinned ? 'text-accent' : undefined}
      onClick={togglePin}
    />
  )
}
