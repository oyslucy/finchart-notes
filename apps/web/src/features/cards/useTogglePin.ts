import { useToast } from '../../components/ui/toast-context.ts'
import { errorMessage } from '../../lib/api.ts'
import type { Card } from '../../lib/types.ts'
import { useUpdateCard } from './queries.ts'

export function useTogglePin(card: Card) {
  const update = useUpdateCard(card.board_id)
  const toast = useToast()
  return () => {
    update.mutate(
      { id: card.id, patch: { pinned: !card.pinned } },
      {
        onSuccess: (saved) => {
          toast({ title: saved.pinned ? '맨 위에 고정했습니다' : '고정을 해제했습니다' })
        },
        onError: (error) => {
          toast({ title: '바꾸지 못했습니다', description: errorMessage(error), tone: 'danger' })
        },
      },
    )
  }
}
