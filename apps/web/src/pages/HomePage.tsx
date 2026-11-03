import { motion } from 'motion/react'

export default function HomePage() {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-neutral-950 text-neutral-100">
      <motion.h1
        className="text-3xl font-semibold tracking-tight"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
      >
        finchart-notes
      </motion.h1>
    </main>
  )
}
