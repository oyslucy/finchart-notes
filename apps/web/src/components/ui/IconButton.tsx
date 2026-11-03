import type { LucideIcon } from 'lucide-react'
import type { ComponentProps } from 'react'

import { cx } from '../../design/cx.ts'
import { Icon } from './Icon.tsx'
import { Tooltip } from './Tooltip.tsx'

export interface IconButtonProps extends Omit<ComponentProps<'button'>, 'children'> {
  icon: LucideIcon
  /** Accessible name; also shown as the tooltip. */
  label: string
  shortcut?: string
  size?: 'sm' | 'md'
  tooltip?: boolean
}

export function IconButton({
  icon,
  label,
  shortcut,
  size = 'md',
  tooltip = true,
  className,
  type = 'button',
  ...props
}: IconButtonProps) {
  const button = (
    <button
      type={type}
      aria-label={label}
      className={cx(
        'inline-flex shrink-0 items-center justify-center rounded-md text-text-muted',
        'transition-[background-color,color] duration-150 ease-out',
        'hover:bg-bg-muted hover:text-text active:bg-border disabled:pointer-events-none disabled:opacity-45',
        size === 'sm' ? 'size-7' : 'size-8',
        className,
      )}
      {...props}
    >
      <Icon icon={icon} size={size === 'sm' ? 16 : 18} />
    </button>
  )
  if (!tooltip) return button
  return (
    <Tooltip content={label} shortcut={shortcut}>
      {button}
    </Tooltip>
  )
}
