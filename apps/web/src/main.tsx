import { QueryClientProvider } from '@tanstack/react-query'
import { MotionConfig } from 'motion/react'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router/dom'

import { queryClient } from './app/queryClient.ts'
import { router } from './app/router.tsx'
import { ToastProvider } from './components/ui/Toast.tsx'
import { TooltipProvider } from './components/ui/Tooltip.tsx'
import { applyTheme } from './design/theme.ts'
import './index.css'

applyTheme()

const root = document.getElementById('root')
if (!root) throw new Error('Root element not found')

createRoot(root).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <QueryClientProvider client={queryClient}>
        <TooltipProvider delayDuration={300}>
          <ToastProvider>
            <RouterProvider router={router} />
          </ToastProvider>
        </TooltipProvider>
      </QueryClientProvider>
    </MotionConfig>
  </StrictMode>,
)
