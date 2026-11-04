import { CircleAlert, CircleCheck, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { Toast as Primitive } from 'radix-ui'
import { useCallback, useState, type ReactNode } from 'react'

import { cx } from '../../design/cx.ts'
import { appear } from '../../design/motion.ts'
import { Icon } from './Icon.tsx'
import { ToastContext, type ToastInput } from './toast-context.ts'

interface ToastItem extends ToastInput {
  id: number
}

let nextId = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const push = useCallback((toast: ToastInput) => {
    setItems((prev) => [...prev.slice(-2), { ...toast, id: nextId++ }])
  }, [])
  const dismiss = (id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id))
  }

  return (
    <ToastContext value={push}>
      <Primitive.Provider swipeDirection="right" duration={4000} label="알림">
        {children}
        <AnimatePresence initial={false}>
          {items.map((item) => (
            <Primitive.Root
              key={item.id}
              forceMount
              asChild
              onOpenChange={(open) => {
                if (!open) dismiss(item.id)
              }}
            >
              <motion.li
                layout
                {...appear}
                className="flex w-[340px] items-start gap-2.5 rounded-lg border border-border bg-surface px-3.5 py-3 shadow-pop print:hidden"
              >
                <ToneIcon tone={item.tone ?? 'neutral'} />
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <Primitive.Title className="text-[14px] font-medium">
                    {item.title}
                  </Primitive.Title>
                  {item.description && (
                    <Primitive.Description className="text-[13px] text-text-muted">
                      {item.description}
                    </Primitive.Description>
                  )}
                </div>
                <Primitive.Close
                  aria-label="알림 닫기"
                  className="-mt-0.5 -mr-1 inline-flex size-6 items-center justify-center rounded-sm text-text-faint hover:bg-bg-muted hover:text-text"
                >
                  <Icon icon={X} size={14} />
                </Primitive.Close>
              </motion.li>
            </Primitive.Root>
          ))}
        </AnimatePresence>
        <Primitive.Viewport className="fixed right-4 bottom-4 z-50 flex flex-col gap-2 outline-none print:hidden" />
      </Primitive.Provider>
    </ToastContext>
  )
}

function ToneIcon({ tone }: { tone: NonNullable<ToastInput['tone']> }) {
  if (tone === 'neutral') return null
  return (
    <span className={cx('mt-0.5', tone === 'success' ? 'text-success' : 'text-danger')}>
      <Icon icon={tone === 'success' ? CircleCheck : CircleAlert} size={16} />
    </span>
  )
}
