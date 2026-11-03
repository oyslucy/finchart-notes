import { ImageUp } from 'lucide-react'
import { useEffect, useRef, useState, type DragEvent } from 'react'

import { Icon } from '../../components/ui/Icon.tsx'
import { Kbd } from '../../components/ui/Kbd.tsx'
import { cx } from '../../design/cx.ts'

const ACCEPT = ['image/png', 'image/jpeg', 'image/webp']

function imagesFrom(list: FileList | null | undefined): File[] {
  return Array.from(list ?? []).filter((f) => ACCEPT.includes(f.type))
}

function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ['INPUT', 'TEXTAREA'].includes(target.tagName))
  )
}

export function UploadZone({ onFiles, busy }: { onFiles: (files: File[]) => void; busy: boolean }) {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      if (isTyping(event.target)) return
      const files = imagesFrom(event.clipboardData?.files)
      if (files.length) {
        event.preventDefault()
        onFiles(files)
      }
    }
    window.addEventListener('paste', onPaste)
    return () => {
      window.removeEventListener('paste', onPaste)
    }
  }, [onFiles])

  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    const files = imagesFrom(event.dataTransfer.files)
    if (files.length) onFiles(files)
  }

  return (
    <div
      data-print-hide
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => {
        setDragging(false)
      }}
      onDrop={onDrop}
      className={cx(
        'flex items-center justify-between gap-4 rounded-lg border px-4 py-3.5 transition-colors duration-150',
        dragging ? 'border-accent bg-accent-subtle' : 'border-border bg-surface',
      )}
    >
      <div className="flex items-center gap-3 text-[14px] text-text-muted">
        <span className="text-text-faint">
          <Icon icon={ImageUp} size={20} />
        </span>
        <span>
          스크린샷을 끌어다 놓거나 <Kbd>⌘</Kbd> <Kbd>V</Kbd> 로 붙여넣기
        </span>
      </div>
      <button
        type="button"
        disabled={busy}
        onClick={() => input.current?.click()}
        className="shrink-0 rounded-md px-2 py-1 text-[13px] font-medium text-accent hover:bg-accent-subtle disabled:opacity-45"
      >
        파일 선택
      </button>
      <input
        ref={input}
        type="file"
        accept={ACCEPT.join(',')}
        multiple
        hidden
        onChange={(e) => {
          const files = imagesFrom(e.target.files)
          e.target.value = ''
          if (files.length) onFiles(files)
        }}
      />
    </div>
  )
}
