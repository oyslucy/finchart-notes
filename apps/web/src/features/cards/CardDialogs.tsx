import { useState } from 'react'

import { Button } from '../../components/ui/Button.tsx'
import { Dialog } from '../../components/ui/Dialog.tsx'
import { Input, Textarea } from '../../components/ui/Field.tsx'
import { useToast } from '../../components/ui/toast-context.ts'
import { errorMessage } from '../../lib/api.ts'
import type { Card } from '../../lib/types.ts'
import { useDeleteCard, useQuota, useReanalyzeCard, useUpdateCard } from './queries.ts'

interface DialogProps {
  card: Card
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface Draft {
  title: string
  period: string
  takeaways: [string, string, string]
  interpretation: string
  caveats: [string, string]
  note: string
}

function draftFrom(card: Card): Draft {
  const t = card.takeaways
  const c = card.caveats
  return {
    title: card.title,
    period: card.period ?? '',
    takeaways: [t[0] ?? '', t[1] ?? '', t[2] ?? ''],
    interpretation: card.interpretation,
    caveats: [c[0] ?? '', c[1] ?? ''],
    note: card.user_note ?? '',
  }
}

function compact(items: string[]): string[] {
  return items.map((i) => i.trim()).filter(Boolean)
}

export function EditCardDialog({ card, open, onOpenChange }: DialogProps) {
  const [draft, setDraft] = useState<Draft>(() => draftFrom(card))
  const update = useUpdateCard(card.board_id)
  const toast = useToast()
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setDraft((d) => ({ ...d, [key]: value }))
  }

  const save = () => {
    if (!draft.title.trim()) {
      toast({ title: '제목을 입력해 주세요', tone: 'danger' })
      return
    }
    update.mutate(
      {
        id: card.id,
        patch: {
          title: draft.title.trim(),
          period: draft.period.trim() || null,
          takeaways: compact(draft.takeaways),
          interpretation: draft.interpretation.trim(),
          caveats: compact(draft.caveats),
          user_note: draft.note.trim() || null,
        },
      },
      {
        onSuccess: () => {
          onOpenChange(false)
        },
        onError: (error) => {
          toast({ title: '저장하지 못했습니다', description: errorMessage(error), tone: 'danger' })
        },
      },
    )
  }

  return (
    <Dialog
      size="lg"
      open={open}
      onOpenChange={(next) => {
        if (next) setDraft(draftFrom(card))
        onOpenChange(next)
      }}
      title="카드 수정"
      description="분석 내용을 고치거나 메모를 남길 수 있습니다."
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
          <Button variant="primary" disabled={update.isPending} onClick={save}>
            저장
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4 pb-1">
        <Input
          label="제목"
          value={draft.title}
          maxLength={200}
          onChange={(e) => {
            set('title', e.target.value)
          }}
        />
        <Input
          label="기간"
          value={draft.period}
          placeholder="예: 2026.05 ~ 2026.10"
          onChange={(e) => {
            set('period', e.target.value)
          }}
        />
        <fieldset className="flex flex-col gap-1.5">
          <legend className="pb-1.5 text-[13px] font-medium text-text-secondary">핵심 관찰</legend>
          {draft.takeaways.map((value, i) => (
            <Input
              key={i}
              aria-label={`핵심 관찰 ${String(i + 1)}`}
              value={value}
              onChange={(e) => {
                const next = [...draft.takeaways] as Draft['takeaways']
                next[i] = e.target.value
                set('takeaways', next)
              }}
            />
          ))}
        </fieldset>
        <Textarea
          label="해설"
          rows={5}
          value={draft.interpretation}
          onChange={(e) => {
            set('interpretation', e.target.value)
          }}
        />
        <fieldset className="flex flex-col gap-1.5">
          <legend className="pb-1.5 text-[13px] font-medium text-text-secondary">주의</legend>
          {draft.caveats.map((value, i) => (
            <Input
              key={i}
              aria-label={`주의 ${String(i + 1)}`}
              value={value}
              onChange={(e) => {
                const next = [...draft.caveats] as Draft['caveats']
                next[i] = e.target.value
                set('caveats', next)
              }}
            />
          ))}
        </fieldset>
        <Textarea
          label="메모"
          rows={3}
          value={draft.note}
          placeholder="이 차트에서 다시 볼 점을 적어 두세요."
          onChange={(e) => {
            set('note', e.target.value)
          }}
        />
      </div>
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

/** Confirms first: the new answer replaces any text the user edited by hand. */
export function ReanalyzeCardDialog({ card, open, onOpenChange }: DialogProps) {
  const reanalyze = useReanalyzeCard(card.board_id)
  const quota = useQuota()
  const toast = useToast()
  const remaining = quota.data?.remaining
  const exhausted = remaining === 0

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!reanalyze.isPending) onOpenChange(next)
      }}
      title="해설을 다시 받을까요?"
      description="잘라 둔 차트로 제목과 해설을 새로 받습니다. 직접 고친 내용은 새 결과로 바뀌고, 메모와 이미지는 그대로 둡니다."
      footer={
        <>
          <Button
            variant="ghost"
            disabled={reanalyze.isPending}
            onClick={() => {
              onOpenChange(false)
            }}
          >
            취소
          </Button>
          <Button
            variant="primary"
            disabled={reanalyze.isPending || exhausted}
            onClick={() => {
              reanalyze.mutate(card.id, {
                onSuccess: (updated) => {
                  onOpenChange(false)
                  toast({
                    title: '해설을 다시 받았습니다',
                    description: updated.title,
                    tone: 'success',
                  })
                },
                onError: (error) => {
                  toast({
                    title: '다시 분석하지 못했습니다',
                    description: errorMessage(error),
                    tone: 'danger',
                  })
                },
              })
            }}
          >
            {reanalyze.isPending ? '분석 중…' : '다시 분석'}
          </Button>
        </>
      }
    >
      {remaining !== undefined && (
        <p className="pb-1 text-[13px] text-text-muted">
          {exhausted
            ? '오늘 분석 횟수를 모두 썼습니다.'
            : `오늘 남은 분석 ${String(remaining)}회 중 1회를 씁니다.`}
        </p>
      )}
    </Dialog>
  )
}
