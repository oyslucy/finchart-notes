import { MoreHorizontal, Pencil, Pin, PinOff, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { IconButton } from '../../components/ui/IconButton.tsx'
import { Menu, MenuItem, MenuSeparator } from '../../components/ui/Menu.tsx'
import { cx } from '../../design/cx.ts'
import type { Card } from '../../lib/types.ts'
import { DeleteCardDialog, EditCardDialog } from './CardDialogs.tsx'
import { useTogglePin } from './useTogglePin.ts'

/** The "⋯" menu on a thumbnail: pin, edit, delete. */
export function CardActionsMenu({ card, className }: { card: Card; className?: string }) {
  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const togglePin = useTogglePin(card)

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
