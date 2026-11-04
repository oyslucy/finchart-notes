import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'

import { useToast } from '../../components/ui/toast-context.ts'
import { errorMessage } from '../../lib/api.ts'
import type { Board, Card } from '../../lib/types.ts'
import { CardDragContext } from './drag-context.ts'
import { useMoveCard } from './queries.ts'

/** Lives in the app shell so moves (and their undo toasts) survive drop targets unmounting. */
export function CardDragProvider({ children }: { children: ReactNode }) {
  const [card, setCardState] = useState<Card | null>(null)
  const cardRef = useRef<Card | null>(null)
  const setCard = useCallback((next: Card | null) => {
    cardRef.current = next
    setCardState(next)
  }, [])
  const move = useMoveCard()
  const toast = useToast()

  const drop = useCallback(
    (board: Board) => {
      const dragged = cardRef.current
      setCard(null)
      if (!dragged || dragged.board_id === board.id) return
      const from = dragged.board_id
      move.mutate(
        { card: dragged, boardId: board.id },
        {
          onSuccess: () => {
            toast({
              title: `'${board.title}'(으)로 옮겼습니다`,
              description: dragged.title,
              action: {
                label: '되돌리기',
                onClick: () => {
                  move.mutate({ card: { ...dragged, board_id: board.id }, boardId: from })
                },
              },
            })
          },
          onError: (e) => {
            toast({ title: '옮기지 못했습니다', description: errorMessage(e), tone: 'danger' })
          },
        },
      )
    },
    [move, toast, setCard],
  )

  const value = useMemo(
    () => ({
      card,
      start: setCard,
      end: () => {
        setCard(null)
      },
      drop,
    }),
    [card, drop, setCard],
  )

  return <CardDragContext value={value}>{children}</CardDragContext>
}
