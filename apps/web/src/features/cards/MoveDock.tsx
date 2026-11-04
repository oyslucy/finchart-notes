import { FolderInput, LayoutGrid } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'

import { Icon } from '../../components/ui/Icon.tsx'
import { cx } from '../../design/cx.ts'
import { appear } from '../../design/motion.ts'
import type { Board } from '../../lib/types.ts'
import { useBoards } from '../boards/queries.ts'
import { useCardDrag } from './drag-context.ts'
import { useBoardDrop } from './useBoardDrop.ts'

/** Appears while a card is dragged: every other board becomes a large drop target. */
export function MoveDock() {
  const { card } = useCardDrag()
  const boards = useBoards()
  const targets = (boards.data ?? []).filter((b) => b.id !== card?.board_id)

  return (
    <AnimatePresence>
      {card && targets.length > 0 && (
        <motion.div
          {...appear}
          data-print-hide
          className="pointer-events-none fixed inset-x-0 bottom-6 z-40 hidden justify-center px-6 md:flex"
        >
          <div className="pointer-events-auto flex max-w-[min(900px,100%)] flex-col gap-2 rounded-lg border border-border bg-surface p-3 shadow-pop">
            <p className="flex items-center gap-1.5 px-1 text-[12px] text-text-muted">
              <Icon icon={FolderInput} size={14} />
              놓을 보드를 고르세요
            </p>
            <div className="flex flex-wrap gap-2">
              {targets.map((board) => (
                <DockTarget key={board.id} board={board} />
              ))}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function DockTarget({ board }: { board: Board }) {
  const { over, handlers } = useBoardDrop(board)
  return (
    <div
      {...handlers}
      className={cx(
        'flex h-11 min-w-[120px] items-center gap-2 rounded-md border px-3 text-[14px] transition-colors duration-100',
        over
          ? 'border-accent bg-accent-subtle font-medium text-accent'
          : 'border-dashed border-border-strong text-text-secondary',
      )}
    >
      <Icon icon={LayoutGrid} size={16} />
      {board.title}
    </div>
  )
}
