import { X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { Dialog as Primitive } from 'radix-ui'
import type { ReactNode } from 'react'

import { appear, fade } from '../../design/motion.ts'
import { IconButton } from './IconButton.tsx'

interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: ReactNode
  description?: ReactNode
  footer?: ReactNode
  children?: ReactNode
}

export function Dialog({ open, onOpenChange, title, description, footer, children }: DialogProps) {
  return (
    <Primitive.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <Primitive.Portal forceMount>
            <Primitive.Overlay asChild forceMount>
              <motion.div className="fixed inset-0 z-40 bg-overlay" {...fade} />
            </Primitive.Overlay>
            <div className="pointer-events-none fixed inset-0 z-50 grid place-items-center p-4">
              <Primitive.Content asChild forceMount>
                <motion.div
                  className="pointer-events-auto w-full max-w-[440px] rounded-lg border border-border bg-surface shadow-pop focus:outline-none"
                  {...appear}
                >
                  <div className="flex items-start justify-between gap-4 px-5 pt-5">
                    <div className="flex flex-col gap-1">
                      <Primitive.Title className="text-[16px] font-semibold tracking-[-0.01em]">
                        {title}
                      </Primitive.Title>
                      {description ? (
                        <Primitive.Description className="text-[13px] text-text-muted">
                          {description}
                        </Primitive.Description>
                      ) : (
                        <Primitive.Description className="sr-only">{title}</Primitive.Description>
                      )}
                    </div>
                    <Primitive.Close asChild>
                      <IconButton
                        icon={X}
                        label="닫기"
                        size="sm"
                        tooltip={false}
                        className="-mt-1 -mr-1.5"
                      />
                    </Primitive.Close>
                  </div>
                  {children && <div className="px-5 pt-4">{children}</div>}
                  {footer && (
                    <div className="mt-5 flex justify-end gap-2 border-t border-border px-5 py-3.5">
                      {footer}
                    </div>
                  )}
                  {!footer && <div className="h-5" />}
                </motion.div>
              </Primitive.Content>
            </div>
          </Primitive.Portal>
        )}
      </AnimatePresence>
    </Primitive.Root>
  )
}

export const DialogClose = Primitive.Close
