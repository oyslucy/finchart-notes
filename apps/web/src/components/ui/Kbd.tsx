import type { ComponentProps } from 'react'

import { cx } from '../../design/cx.ts'

export function Kbd({ className, ...props }: ComponentProps<'kbd'>) {
  return (
    <kbd
      className={cx(
        'inline-flex h-5 min-w-5 items-center justify-center rounded-sm border border-border',
        'bg-bg-subtle px-1 font-sans text-[11px] leading-none font-medium text-text-muted',
        className,
      )}
      {...props}
    />
  )
}
