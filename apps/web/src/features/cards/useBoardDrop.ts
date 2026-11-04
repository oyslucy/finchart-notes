import { useState, type DragEvent } from 'react'

import type { Board } from '../../lib/types.ts'
import { CARD_DRAG_TYPE, useCardDrag } from './drag-context.ts'

/** Drop-target props for `board`; only lights up for cards from a different board. */
export function useBoardDrop(board: Board) {
  const drag = useCardDrag()
  const [over, setOver] = useState(false)
  const accepts = drag.card !== null && drag.card.board_id !== board.id

  return {
    accepts,
    over: over && accepts,
    handlers: {
      onDragOver: (event: DragEvent) => {
        if (!accepts || !event.dataTransfer.types.includes(CARD_DRAG_TYPE)) return
        event.preventDefault()
        event.dataTransfer.dropEffect = 'move'
        setOver(true)
      },
      onDragLeave: () => {
        setOver(false)
      },
      onDrop: (event: DragEvent) => {
        event.preventDefault()
        setOver(false)
        drag.drop(board)
      },
    },
  }
}
