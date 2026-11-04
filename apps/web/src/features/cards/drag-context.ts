import { createContext, useContext } from 'react'

import type { Board, Card } from '../../lib/types.ts'

export const CARD_DRAG_TYPE = 'application/x-finchart-card'

export interface CardDrag {
  card: Card | null
  start: (card: Card) => void
  end: () => void
  /** Moves the dragged card into `board`, with an undo toast. */
  drop: (board: Board) => void
}

export const CardDragContext = createContext<CardDrag>({
  card: null,
  start: () => undefined,
  end: () => undefined,
  drop: () => undefined,
})

export function useCardDrag(): CardDrag {
  return useContext(CardDragContext)
}
