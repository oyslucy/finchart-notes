import type { LucideIcon } from 'lucide-react'
import { DropdownMenu } from 'radix-ui'
import type { ReactElement, ReactNode } from 'react'

import { cx } from '../../design/cx.ts'
import { Icon } from './Icon.tsx'

export function Menu({ trigger, children }: { trigger: ReactElement; children: ReactNode }) {
  return (
    <DropdownMenu.Root modal={false}>
      <DropdownMenu.Trigger asChild>{trigger}</DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={4}
          className="z-50 min-w-[160px] rounded-md border border-border bg-surface p-1 shadow-pop data-[state=open]:animate-[tooltip-in_120ms_ease-out]"
        >
          {children}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}

interface MenuItemProps {
  icon: LucideIcon
  children: ReactNode
  onSelect: () => void
  tone?: 'default' | 'danger'
}

export function MenuItem({ icon, children, onSelect, tone = 'default' }: MenuItemProps) {
  return (
    <DropdownMenu.Item
      onSelect={onSelect}
      className={cx(
        'flex h-8 cursor-default items-center gap-2 rounded-sm px-2 text-[13px] outline-none select-none',
        'data-[highlighted]:bg-bg-muted',
        tone === 'danger' ? 'text-danger' : 'text-text',
      )}
    >
      <span className={tone === 'danger' ? '' : 'text-text-muted'}>
        <Icon icon={icon} size={14} />
      </span>
      {children}
    </DropdownMenu.Item>
  )
}

export function MenuSub({
  icon,
  label,
  children,
}: {
  icon: LucideIcon
  label: string
  children: ReactNode
}) {
  return (
    <DropdownMenu.Sub>
      <DropdownMenu.SubTrigger className="flex h-8 cursor-default items-center gap-2 rounded-sm px-2 text-[13px] text-text outline-none select-none data-[highlighted]:bg-bg-muted data-[state=open]:bg-bg-muted">
        <span className="text-text-muted">
          <Icon icon={icon} size={14} />
        </span>
        <span className="flex-1">{label}</span>
        <span className="text-text-faint">›</span>
      </DropdownMenu.SubTrigger>
      <DropdownMenu.Portal>
        <DropdownMenu.SubContent
          sideOffset={4}
          className="z-50 max-h-[280px] min-w-[160px] overflow-y-auto rounded-md border border-border bg-surface p-1 shadow-pop"
        >
          {children}
        </DropdownMenu.SubContent>
      </DropdownMenu.Portal>
    </DropdownMenu.Sub>
  )
}

export const MenuSeparator = () => <DropdownMenu.Separator className="my-1 h-px bg-border" />
