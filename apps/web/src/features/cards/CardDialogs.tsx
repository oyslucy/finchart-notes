import { useState } from 'react'

import { Button } from '../../components/ui/Button.tsx'
import { Dialog } from '../../components/ui/Dialog.tsx'
import { Textarea } from '../../components/ui/Field.tsx'
import { useToast } from '../../components/ui/toast-context.ts'
import { errorMessage } from '../../lib/api.ts'
import type { Card } from '../../lib/types.ts'
import { useDeleteCard, useUpdateCard } from './queries.ts'

interface DialogProps {
  card: Card
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function NoteDialog({ card, open, onOpenChange }: DialogProps) {
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

export function DeleteCardDialog({
  card,
  open,
  onOpenChange,
  onDeleted,
}: DialogProps & { onDeleted: () => void }) {
  const remove = useDeleteCard(card.board_id)
  const toast = useToast()

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="카드를 삭제할까요?"
      description="잘라 둔 이미지와 해설이 함께 삭제됩니다."
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
            variant="danger"
            disabled={remove.isPending}
            onClick={() => {
              remove.mutate(card.id, {
                onSuccess: () => {
                  onOpenChange(false)
                  onDeleted()
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
  )
}
