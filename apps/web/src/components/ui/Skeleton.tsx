import type { ComponentProps } from 'react'

import { cx } from '../../design/cx.ts'

export function Skeleton({ className, ...props }: ComponentProps<'div'>) {
  return (
    <div
      aria-hidden="true"
      className={cx(
        'animate-[skeleton_1.6s_ease-in-out_infinite] rounded-sm bg-bg-muted',
        className,
      )}
      {...props}
    />
  )
}
