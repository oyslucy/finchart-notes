import { Tooltip as Primitive } from 'radix-ui'
import type { ReactElement, ReactNode } from 'react'

import { Kbd } from './Kbd.tsx'

export const TooltipProvider = Primitive.Provider

interface TooltipProps {
  content: ReactNode
  shortcut?: string | undefined
  side?: 'top' | 'right' | 'bottom' | 'left'
  children: ReactElement
}

export function Tooltip({ content, shortcut, side = 'top', children }: TooltipProps) {
  return (
    <Primitive.Root>
      <Primitive.Trigger asChild>{children}</Primitive.Trigger>
      <Primitive.Portal>
        <Primitive.Content
          side={side}
          sideOffset={6}
          className="z-50 flex items-center gap-2 rounded-sm bg-text px-2 py-1 text-[12px] font-medium text-bg shadow-pop data-[state=delayed-open]:animate-[tooltip-in_120ms_ease-out]"
        >
          {content}
          {shortcut && <Kbd className="border-transparent bg-bg/15 text-bg">{shortcut}</Kbd>}
        </Primitive.Content>
      </Primitive.Portal>
    </Primitive.Root>
  )
}
