import type { ToastInput } from '../../components/ui/toast-context.ts'
import { errorMessage, isRetryable } from '../../lib/api.ts'

/** The failure toast for one file; a retry button when the model or network failed. */
export function uploadFailed(file: File, error: unknown, retry: () => void): ToastInput {
  return {
    title: `${file.name} 분석 실패`,
    description: errorMessage(error),
    tone: 'danger',
    ...(isRetryable(error) && { action: { label: '다시 시도', onClick: retry } }),
  }
}
