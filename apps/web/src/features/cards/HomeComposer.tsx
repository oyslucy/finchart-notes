import { Check, Plus } from 'lucide-react'
import { useState, type SyntheticEvent } from 'react'

import { Icon } from '../../components/ui/Icon.tsx'
import { useToast } from '../../components/ui/toast-context.ts'
import { cx } from '../../design/cx.ts'
import { errorMessage } from '../../lib/api.ts'
import type { Board } from '../../lib/types.ts'
import { useCreateBoard } from '../boards/queries.ts'
import { UploadZone } from './UploadZone.tsx'
import { useBoardDrop } from './useBoardDrop.ts'

interface HomeComposerProps {
  boards: Board[]
  selectedId: string | null
  onSelect: (boardId: string) => void
  onFiles: (files: File[]) => void
  busy: boolean
}

const chip =
  'inline-flex h-7 shrink-0 items-center gap-1 rounded-full border px-3 text-[13px] transition-colors duration-150'

/** Upload bar plus board chips: pick where the next screenshots go, then drop or paste. */
export function HomeComposer({ boards, selectedId, onSelect, onFiles, busy }: HomeComposerProps) {
  const selected = boards.find((b) => b.id === selectedId)
  return (
    <section className="rounded-lg border border-border bg-surface shadow-xs">
      <UploadZone
        variant="bare"
        onFiles={onFiles}
        busy={busy}
        hint={
          selected
            ? `‘${selected.title}’ 보드에 저장됩니다`
            : '보드가 없으면 Inbox를 만들어 저장합니다'
        }
      />
      <div
        role="radiogroup"
        aria-label="저장할 보드"
        className="flex [scrollbar-width:none] items-center gap-1.5 overflow-x-auto border-t border-border px-4 py-2.5"
      >
        <span className="mr-1 shrink-0 text-[12px] text-text-faint">저장할 보드</span>
        {boards.map((board) => (
          <BoardChip
            key={board.id}
            board={board}
            active={board.id === selectedId}
            onSelect={onSelect}
          />
        ))}
        <NewBoardChip onCreated={onSelect} />
      </div>
    </section>
  )
}

/** Selects the upload target; also a drop target for dragged cards. */
function BoardChip({
  board,
  active,
  onSelect,
}: {
  board: Board
  active: boolean
  onSelect: (boardId: string) => void
}) {
  const { over, handlers } = useBoardDrop(board)
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      onClick={() => {
        onSelect(board.id)
      }}
      {...handlers}
      className={cx(
        chip,
        over
          ? 'border-accent bg-accent-subtle text-accent ring-2 ring-[var(--focus-ring)]'
          : active
            ? 'border-accent bg-accent-subtle font-medium text-accent'
            : 'border-border text-text-secondary hover:border-border-strong hover:text-text',
      )}
    >
      {active && <Icon icon={Check} size={14} />}
      {board.title}
    </button>
  )
}

function NewBoardChip({ onCreated }: { onCreated: (boardId: string) => void }) {
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState('')
  const create = useCreateBoard()
  const toast = useToast()

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => {
          setEditing(true)
        }}
        className={cx(chip, 'border-dashed border-border-strong text-text-muted hover:text-text')}
      >
        <Icon icon={Plus} size={14} />새 보드
      </button>
    )
  }

  const submit = (event: SyntheticEvent) => {
    event.preventDefault()
    const name = title.trim()
    if (!name) {
      setEditing(false)
      return
    }
    create.mutate(name, {
      onSuccess: (board) => {
        onCreated(board.id)
        setTitle('')
        setEditing(false)
      },
      onError: (e) => {
        toast({ title: '보드를 만들지 못했습니다', description: errorMessage(e), tone: 'danger' })
      },
    })
  }

  return (
    <form onSubmit={submit} className="shrink-0">
      <input
        aria-label="새 보드 이름"
        autoFocus
        value={title}
        maxLength={200}
        placeholder="예: 반도체"
        disabled={create.isPending}
        onChange={(e) => {
          setTitle(e.target.value)
        }}
        onBlur={submit}
        onKeyDown={(e) => {
          if (e.key === 'Escape') setEditing(false)
        }}
        className="h-7 w-32 rounded-full border border-accent bg-surface px-3 text-[13px] shadow-[0_0_0_3px_var(--focus-ring)] outline-none"
      />
    </form>
  )
}
