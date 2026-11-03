import type { Transition } from 'motion/react'

export const easeOut = [0.2, 0, 0, 1] as const

export const durations = {
  interact: 0.12,
  appear: 0.22,
} as const

export const appearTransition: Transition = { duration: durations.appear, ease: easeOut }

/** Entrance: fade + 8px rise. MotionConfig reducedMotion="user" drops the rise automatically. */
export const appear = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 4 },
  transition: appearTransition,
} as const

export const fade = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: durations.appear, ease: easeOut },
} as const

export const gentleSpring: Transition = { type: 'spring', stiffness: 520, damping: 40, mass: 0.8 }
