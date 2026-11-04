import { Download, Pencil, Trash2 } from 'lucide-react'
import { AnimatePresence } from 'motion/react'
import { useCallback, useState, type SyntheticEvent } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router'

import { Button } from '../components/ui/Button.tsx'
import { Dialog } from '../components/ui/Dialog.tsx'
import { IconButton } from '../components/ui/IconButton.tsx'
import { Skeleton } from '../components/ui/Skeleton.tsx'
import { useToast } from '../components/ui/toast-context.ts'
import { useBoards, useDeleteBoard, useRenameBoard } from '../features/boards/queries.ts'
import { useCards, useUploadCard } from '../features/cards/queries.ts'
import {
  THUMBNAIL_GRID,
  ThumbnailCard,
  ThumbnailSkeleton,
} from '../features/cards/ThumbnailCard.tsx'
import { PrintBoard } from '../features/cards/PrintBoard.tsx'
import { UploadZone } from '../features/cards/UploadZone.tsx'
import { exportPdf } from '../features/cards/print.ts'
import { cx } from '../design/cx.ts'
import { errorMessage } from '../lib/api.ts'
import type { Board } from '../lib/types.ts'

export default function BoardPage() {
  const { boardId = '' } = useParams()
  const boards = useBoards()
  const board = boards.data?.find((b) => b.id === boardId)

  if (boards.isSuccess && !board) return <Navigate to="/" replace />

  return (
    <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-4 pt-6 pb-24 md:px-10 md:pt-8 print:m-0 print:block print:max-w-none print:p-0">
      {board ? <BoardHeader board={board} /> : <Skeleton className="h-8 w-1/2" />}
      <BoardCards key={boardId} boardId={boardId} title={board?.title ?? ''} />
    </div>
  )
}

function BoardHeader({ board }: { board: Board }) {
  const [editing, setEditing] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const rename = useRenameBoard()
  const remove = useDeleteBoard()
  const navigate = useNavigate()
  const toast = useToast()

  const submit = (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault()
    const value = new FormData(event.currentTarget).get('title')
    const title = typeof value === 'string' ? value.trim() : ''
    if (title && title !== board.title) {
      rename.mutate(
        { id: board.id, title },
        {
          onError: (e) => {
            toast({
              title: '이름을 바꾸지 못했습니다',
              description: errorMessage(e),
              tone: 'danger',
            })
          },
        },
      )
    }
    setEditing(false)
  }

  return (
    <header className="flex items-center justify-between gap-4 print:hidden">
      {editing ? (
        <form onSubmit={submit} className="flex-1">
          <input
            name="title"
            aria-label="보드 이름"
            defaultValue={board.title}
            autoFocus
            maxLength={200}
            onBlur={(e) => {
              e.currentTarget.form?.requestSubmit()
            }}
            onKeyDown={(e) => {
              if (e.key === 'Escape') setEditing(false)
            }}
            className="-mx-1.5 w-full rounded-md bg-surface px-1.5 text-[26px] font-semibold tracking-[-0.01em] shadow-[0_0_0_3px_var(--focus-ring)] outline-none"
          />
        </form>
      ) : (
        <h1 className="min-w-0 flex-1">
          <button
            type="button"
            title="눌러서 이름 바꾸기"
            onClick={() => {
              setEditing(true)
            }}
            className="-mx-1.5 max-w-full truncate rounded-md px-1.5 text-left text-[26px] font-semibold tracking-[-0.01em] transition-colors duration-150 hover:bg-bg-muted"
          >
            {board.title}
          </button>
        </h1>
      )}
      <div data-print-hide className="flex shrink-0 items-center gap-1">
        <Button size="sm" variant="ghost" icon={Download} onClick={exportPdf}>
          PDF
        </Button>
        <IconButton
          icon={Pencil}
          label="이름 바꾸기"
          size="sm"
          onClick={() => {
            setEditing(true)
          }}
        />
        <IconButton
          icon={Trash2}
          label="보드 삭제"
          size="sm"
          onClick={() => {
            setDeleteOpen(true)
          }}
        />
      </div>
      <Dialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="보드를 삭제할까요?"
        description="보드 안의 카드와 이미지가 모두 삭제되며 되돌릴 수 없습니다."
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => {
                setDeleteOpen(false)
              }}
            >
              취소
            </Button>
            <Button
              variant="danger"
              disabled={remove.isPending}
              onClick={() => {
                remove.mutate(board.id, {
                  onSuccess: () => {
                    void navigate('/', { replace: true })
                  },
                  onError: (e) => {
                    toast({
                      title: '삭제하지 못했습니다',
                      description: errorMessage(e),
                      tone: 'danger',
                    })
                  },
                })
              }}
            >
              삭제
            </Button>
          </>
        }
      />
    </header>
  )
}

function BoardCards({ boardId, title }: { boardId: string; title: string }) {
  const cards = useCards(boardId)
  const upload = useUploadCard(boardId)
  const toast = useToast()
  const [pending, setPending] = useState(0)

  const onFiles = useCallback(
    (files: File[]) => {
      setPending((n) => n + files.length)
      void files.reduce(async (previous, file) => {
        await previous
        try {
          const { duplicate } = await upload.mutateAsync(file)
          if (duplicate) toast({ title: '이미 올린 이미지라 기존 분석을 불러왔습니다' })
        } catch (error) {
          toast({
            title: `${file.name} 분석 실패`,
            description: errorMessage(error),
            tone: 'danger',
          })
        } finally {
          setPending((n) => n - 1)
        }
      }, Promise.resolve())
    },
    [upload, toast],
  )

  return (
    <>
      <UploadZone onFiles={onFiles} busy={pending > 0} />

      {cards.isSuccess && cards.data.length === 0 && pending === 0 && (
        <p className="py-16 text-center text-[14px] text-text-muted">
          아직 카드가 없습니다. 차트 스크린샷을 올려보세요.
        </p>
      )}

      <ul className={cx(THUMBNAIL_GRID, 'print:hidden')}>
        {Array.from({ length: pending }, (_, i) => (
          <ThumbnailSkeleton key={`pending-${String(i)}`} label={i === 0 ? '분석 중' : '대기 중'} />
        ))}
        {cards.isPending &&
          Array.from({ length: 4 }, (_, i) => <ThumbnailSkeleton key={`loading-${String(i)}`} />)}
        <AnimatePresence initial={false}>
          {cards.data?.map((card, index) => (
            <ThumbnailCard key={card.id} card={card} index={index} />
          ))}
        </AnimatePresence>
      </ul>

      <PrintBoard title={title} cards={cards.data ?? []} />
    </>
  )
}
