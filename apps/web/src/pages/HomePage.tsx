import { motion } from 'motion/react'

import { appear } from '../design/motion.ts'

export default function HomePage() {
  return (
    <main className="flex min-h-dvh items-center justify-center">
      <motion.h1 className="text-[26px]" {...appear}>
        finchart-notes
      </motion.h1>
    </main>
  )
}
