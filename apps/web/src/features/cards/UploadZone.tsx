import { ImageUp, type LucideIcon } from 'lucide-react'
import { useEffect, useRef, useState, type DragEvent, type ReactNode } from 'react'

import { Icon } from '../../components/ui/Icon.tsx'
import { Kbd } from '../../components/ui/Kbd.tsx'
import { cx } from '../../design/cx.ts'

const IMAGES = ['image/png', 'image/jpeg', 'image/webp']

function filesFrom(list: FileList | null | undefined, accept: string[]): File[] {
  return Array.from(list ?? []).filter((f) => accept.includes(f.type))
}

function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ['INPUT', 'TEXTAREA'].includes(target.tagName))
  )
}

interface UploadZoneProps {
  onFiles: (files: File[]) => void
  busy: boolean
  /** "bare" drops the frame so the zone can sit inside another panel. */
  variant?: 'framed' | 'bare'
  hint?: string
  /** Shown beside the file button, e.g. the analyses left today. */
  aside?: ReactNode
  /** MIME types to take; screenshots by default. */
  accept?: string[]
  /** What to drop, with its object particle: "스크린샷을", "뉴스 PDF를". */
  noun?: string
  icon?: LucideIcon
}

export function UploadZone({
  onFiles,
  busy,
  variant = 'framed',
  hint,
  aside,
  accept = IMAGES,
  noun = '스크린샷을',
  icon = ImageUp,
}: UploadZoneProps) {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      if (isTyping(event.target)) return
      const files = filesFrom(event.clipboardData?.files, accept)
      if (files.length) {
        event.preventDefault()
        onFiles(files)
      }
    }
    window.addEventListener('paste', onPaste)
    return () => {
      window.removeEventListener('paste', onPaste)
    }
  }, [onFiles, accept])

  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    const files = filesFrom(event.dataTransfer.files, accept)
    if (files.length) onFiles(files)
  }

  return (
    <div
      data-print-hide
      onDragOver={(e) => {
        // Only files; cards being dragged between boards must not light this up.
        if (!e.dataTransfer.types.includes('Files')) return
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => {
        setDragging(false)
      }}
      onDrop={onDrop}
      className={cx(
        'flex items-center justify-between gap-4 px-4 py-3.5 transition-colors duration-150',
        variant === 'framed' ? 'rounded-lg border' : 'rounded-t-lg',
        dragging
          ? 'border-accent bg-accent-subtle'
          : variant === 'framed'
            ? 'border-border bg-surface'
            : 'bg-transparent',
      )}
    >
      <div className="flex items-center gap-3 text-[14px] text-text-muted">
        <span className="text-text-faint">
          <Icon icon={icon} size={20} />
        </span>
        <span className="flex flex-col">
          <span className="hidden sm:inline">
            {noun} 끌어다 놓거나 <Kbd>⌘</Kbd> <Kbd>V</Kbd> 로 붙여넣기
          </span>
          <span className="sm:hidden">{noun} 골라 올려 주세요</span>
          {hint && <span className="text-[12px] text-text-faint">{hint}</span>}
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {aside}
        <button
          type="button"
          disabled={busy}
          onClick={() => input.current?.click()}
          className="shrink-0 rounded-md px-2 py-1 text-[13px] font-medium text-accent hover:bg-accent-subtle disabled:opacity-45"
        >
          파일 선택
        </button>
      </div>
      <input
        ref={input}
        type="file"
        accept={accept.join(',')}
        multiple
        hidden
        onChange={(e) => {
          const files = filesFrom(e.target.files, accept)
          e.target.value = ''
          if (files.length) onFiles(files)
        }}
      />
    </div>
  )
}
