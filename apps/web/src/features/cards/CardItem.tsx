import { ArrowDown, ArrowUp, NotebookPen, Trash2 } from 'lucide-react'
import { motion } from 'motion/react'
import { useState } from 'react'

import { Button } from '../../components/ui/Button.tsx'
import { ChartCard } from '../../components/ui/ChartCard.tsx'
import { Dialog } from '../../components/ui/Dialog.tsx'
import { Textarea } from '../../components/ui/Field.tsx'
import { IconButton } from '../../components/ui/IconButton.tsx'
import { useToast } from '../../components/ui/toast-context.ts'
import { appear } from '../../design/motion.ts'
import { errorMessage } from '../../lib/api.ts'
import { CHART_TYPE_LABEL, type Card } from '../../lib/types.ts'
import { useDeleteCard, useUpdateCard } from './queries.ts'

interface CardItemProps {
  card: Card
  onMove: (direction: -1 | 1) => void
  isFirst: boolean
  isLast: boolean
}

export function CardItem({ card, onMove, isFirst, isLast }: CardItemProps) {
  const [noteOpen, setNoteOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const remove = useDeleteCard(card.board_id)
  const toast = useToast()

  return (
    <motion.div
      layout
      {...appear}
      id={`card-${card.id}`}
      className="scroll-mt-6 break-inside-avoid"
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
        actions={
          <div data-print-hide className="flex items-center gap-0.5">
            <IconButton
              icon={ArrowUp}
              label="위로"
              size="sm"
              disabled={isFirst}
              onClick={() => {
                onMove(-1)
              }}
            />
            <IconButton
              icon={ArrowDown}
              label="아래로"
              size="sm"
              disabled={isLast}
              onClick={() => {
                onMove(1)
              }}
            />
            <IconButton
              icon={NotebookPen}
              label="메모"
              size="sm"
              onClick={() => {
                setNoteOpen(true)
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
          </div>
        }
      />
      <NoteDialog card={card} open={noteOpen} onOpenChange={setNoteOpen} />
      <Dialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="카드를 삭제할까요?"
        description="잘라 둔 이미지와 해설이 함께 삭제됩니다."
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
                remove.mutate(card.id, {
                  onSuccess: () => {
                    setDeleteOpen(false)
                  },
                  onError: (error) => {
                    toast({
                      title: '삭제하지 못했습니다',
                      description: errorMessage(error),
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
    </motion.div>
  )
}

function NoteDialog({
  card,
  open,
  onOpenChange,
}: {
  card: Card
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [note, setNote] = useState(card.user_note ?? '')
  const update = useUpdateCard(card.board_id)
  const toast = useToast()

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (next) setNote(card.user_note ?? '')
        onOpenChange(next)
      }}
      title="메모"
      description={card.title}
      footer={
        <>
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
            disabled={update.isPending}
            onClick={() => {
              update.mutate(
                { id: card.id, patch: { user_note: note.trim() || null } },
                {
                  onSuccess: () => {
                    onOpenChange(false)
                  },
                  onError: (error) => {
                    toast({
                      title: '저장하지 못했습니다',
                      description: errorMessage(error),
                      tone: 'danger',
                    })
                  },
                },
              )
            }}
          >
            저장
          </Button>
        </>
      }
    >
      <Textarea
        aria-label="메모"
        autoFocus
        rows={5}
        value={note}
        placeholder="이 차트에서 다시 볼 점을 적어 두세요."
        onChange={(e) => {
          setNote(e.target.value)
        }}
      />
    </Dialog>
  )
}
