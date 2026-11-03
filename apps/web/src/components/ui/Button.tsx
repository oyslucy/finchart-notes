import type { LucideIcon } from 'lucide-react'
import type { ComponentProps } from 'react'

import { cx } from '../../design/cx.ts'
import { Icon } from './Icon.tsx'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md'

const base =
  'inline-flex select-none items-center justify-center gap-1.5 whitespace-nowrap rounded-md font-medium ' +
  'transition-[background-color,border-color,color] duration-150 ease-out ' +
  'disabled:pointer-events-none disabled:opacity-45'

const variants: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-accent-fg hover:bg-accent-hover active:bg-accent-active',
  secondary:
    'border border-border bg-surface text-text hover:border-border-strong hover:bg-bg-subtle active:bg-bg-muted',
  ghost: 'text-text-secondary hover:bg-bg-muted hover:text-text active:bg-border',
  danger:
    'border border-border bg-surface text-danger hover:border-danger/40 hover:bg-danger-subtle',
}

const sizes: Record<ButtonSize, string> = {
  sm: 'h-7 px-2.5 text-[13px]',
  md: 'h-8.5 px-3.5 text-[14px]',
}

export interface ButtonProps extends ComponentProps<'button'> {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: LucideIcon
}

export function Button({
  variant = 'secondary',
  size = 'md',
  icon,
  className,
  children,
  type = 'button',
  ...props
}: ButtonProps) {
  return (
    <button type={type} className={cx(base, variants[variant], sizes[size], className)} {...props}>
      {icon && <Icon icon={icon} size={size === 'sm' ? 14 : 16} />}
      {children}
    </button>
  )
}
