import { Download, Pencil, Trash2 } from 'lucide-react'
import { AnimatePresence } from 'motion/react'
import { useCallback, useState, type SyntheticEvent } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router'

import { Button } from '../components/ui/Button.tsx'
import { ChartCardSkeleton } from '../components/ui/ChartCard.tsx'
import { Dialog } from '../components/ui/Dialog.tsx'
import { IconButton } from '../components/ui/IconButton.tsx'
import { Skeleton } from '../components/ui/Skeleton.tsx'
import { useToast } from '../components/ui/toast-context.ts'
import { useBoards, useDeleteBoard, useRenameBoard } from '../features/boards/queries.ts'
import { CardItem } from '../features/cards/CardItem.tsx'
import { useCards, useReorderCards, useUploadCard } from '../features/cards/queries.ts'
import { UploadZone } from '../features/cards/UploadZone.tsx'
import { exportPdf } from '../features/cards/print.ts'
import { errorMessage } from '../lib/api.ts'
import type { Board } from '../lib/types.ts'

export default function BoardPage() {
  const { boardId = '' } = useParams()
  const boards = useBoards()
  const board = boards.data?.find((b) => b.id === boardId)

  if (boards.isSuccess && !board) return <Navigate to="/" replace />

  return (
    <div className="mx-auto flex max-w-[760px] flex-col gap-6 px-6 pt-8 pb-24 md:px-10">
      {board ? <BoardHeader board={board} /> : <Skeleton className="h-8 w-1/2" />}
      <BoardCards boardId={boardId} />
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
    <header className="flex items-center justify-between gap-4">
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
            className="w-full rounded-md bg-transparent text-[26px] font-semibold tracking-[-0.01em] outline-none"
          />
        </form>
      ) : (
        <h1 className="min-w-0 truncate text-[26px]">{board.title}</h1>
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

function BoardCards({ boardId }: { boardId: string }) {
  const cards = useCards(boardId)
  const upload = useUploadCard(boardId)
  const reorder = useReorderCards(boardId)
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

  const move = (index: number, direction: -1 | 1) => {
    if (!cards.data) return
    const ids = cards.data.map((c) => c.id)
    const target = index + direction
    const [moved] = ids.splice(index, 1)
    if (!moved || target < 0 || target > ids.length) return
    ids.splice(target, 0, moved)
    reorder.mutate(ids, {
      onError: (e) => {
        toast({ title: '순서를 바꾸지 못했습니다', description: errorMessage(e), tone: 'danger' })
      },
    })
  }

  return (
    <>
      <UploadZone onFiles={onFiles} busy={pending > 0} />
      {cards.isPending && <ChartCardSkeleton />}
      {cards.isSuccess && cards.data.length === 0 && pending === 0 && (
        <p className="py-16 text-center text-[14px] text-text-muted">
          아직 카드가 없습니다. 차트 스크린샷을 올려보세요.
        </p>
      )}
      <div className="flex flex-col gap-6">
        <AnimatePresence initial={false}>
          {cards.data?.map((card, index) => (
            <CardItem
              key={card.id}
              card={card}
              isFirst={index === 0}
              isLast={index === cards.data.length - 1}
              onMove={(direction) => {
                move(index, direction)
              }}
            />
          ))}
        </AnimatePresence>
        {Array.from({ length: pending }, (_, i) => (
          <ChartCardSkeleton key={`pending-${String(i)}`} />
        ))}
      </div>
    </>
  )
}
