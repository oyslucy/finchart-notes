import { FolderInput, LayoutGrid, MoreHorizontal, Pencil, Pin, PinOff, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { IconButton } from '../../components/ui/IconButton.tsx'
import { Menu, MenuItem, MenuSeparator, MenuSub } from '../../components/ui/Menu.tsx'
import { useToast } from '../../components/ui/toast-context.ts'
import { cx } from '../../design/cx.ts'
import { errorMessage } from '../../lib/api.ts'
import type { Card } from '../../lib/types.ts'
import { useBoards } from '../boards/queries.ts'
import { DeleteCardDialog, EditCardDialog } from './CardDialogs.tsx'
import { useMoveCard } from './queries.ts'
import { useTogglePin } from './useTogglePin.ts'

/** The "⋯" menu on a thumbnail: pin, edit, delete. */
export function CardActionsMenu({ card, className }: { card: Card; className?: string }) {
  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const togglePin = useTogglePin(card)
  const boards = useBoards()
  const move = useMoveCard()
  const toast = useToast()
  const others = (boards.data ?? []).filter((b) => b.id !== card.board_id)

  return (
    <>
      <Menu
        trigger={
          <IconButton
            icon={MoreHorizontal}
            label="카드 메뉴"
            size="sm"
            tooltip={false}
            className={cx(
              'border border-border bg-surface/95 text-text-secondary shadow-xs hover:bg-surface',
              className,
            )}
          />
        }
      >
        <MenuItem icon={card.pinned ? PinOff : Pin} onSelect={togglePin}>
          {card.pinned ? '고정 해제' : '맨 위에 고정'}
        </MenuItem>
        <MenuItem
          icon={Pencil}
          onSelect={() => {
            setEditOpen(true)
          }}
        >
          수정
        </MenuItem>
        {others.length > 0 && (
          <MenuSub icon={FolderInput} label="보드 이동">
            {others.map((board) => (
              <MenuItem
                key={board.id}
                icon={LayoutGrid}
                onSelect={() => {
                  move.mutate(
                    { card, boardId: board.id },
                    {
                      onSuccess: () => {
                        toast({ title: `'${board.title}'(으)로 옮겼습니다` })
                      },
                      onError: (e) => {
                        toast({
                          title: '옮기지 못했습니다',
                          description: errorMessage(e),
                          tone: 'danger',
                        })
                      },
                    },
                  )
                }}
              >
                {board.title}
              </MenuItem>
            ))}
          </MenuSub>
        )}
        <MenuSeparator />
        <MenuItem
          icon={Trash2}
          tone="danger"
          onSelect={() => {
            setDeleteOpen(true)
          }}
        >
          삭제
        </MenuItem>
      </Menu>
      <EditCardDialog card={card} open={editOpen} onOpenChange={setEditOpen} />
      <DeleteCardDialog
        card={card}
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onDeleted={() => undefined}
      />
    </>
  )
}
