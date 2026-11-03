import type { LucideIcon } from 'lucide-react'
import type { ComponentProps, ReactNode } from 'react'

import { cx } from '../../design/cx.ts'
import { Icon } from './Icon.tsx'

export interface SidebarItemProps extends ComponentProps<'a'> {
  icon?: LucideIcon
  active?: boolean
  count?: number
}

export function SidebarItem({
  icon,
  active,
  count,
  className,
  children,
  ...props
}: SidebarItemProps) {
  return (
    <a
      aria-current={active ? 'page' : undefined}
      className={cx(
        'group flex h-[30px] items-center gap-2 rounded-md px-2 text-[14px]',
        'transition-[background-color,color] duration-150 ease-out',
        active
          ? 'bg-bg-muted font-medium text-text'
          : 'text-text-secondary hover:bg-bg-subtle hover:text-text',
        className,
      )}
      {...props}
    >
      {icon && (
        <span className={active ? 'text-text' : 'text-text-faint group-hover:text-text-muted'}>
          <Icon icon={icon} size={16} />
        </span>
      )}
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {count !== undefined && <span className="text-[12px] text-text-faint tabular">{count}</span>}
    </a>
  )
}

export function SidebarSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-px">
      <div className="px-2 pt-4 pb-1.5 text-[11px] font-medium tracking-[0.04em] text-text-faint uppercase">
        {title}
      </div>
      {children}
    </div>
  )
}
