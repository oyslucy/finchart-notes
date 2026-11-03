import { LayoutGrid, LogOut, Plus } from 'lucide-react'
import { useState, type SyntheticEvent } from 'react'
import { Link, Navigate, Outlet, useNavigate, useParams } from 'react-router'

import { Input } from '../components/ui/Field.tsx'
import { IconButton } from '../components/ui/IconButton.tsx'
import { SidebarItem, SidebarSection } from '../components/ui/SidebarItem.tsx'
import { Skeleton } from '../components/ui/Skeleton.tsx'
import { useToast } from '../components/ui/toast-context.ts'
import { useMe, useSignOut } from '../features/auth/session.ts'
import { useBoards, useCreateBoard } from '../features/boards/queries.ts'
import { errorMessage } from '../lib/api.ts'

export default function AppLayout() {
  const me = useMe()

  if (me.isPending) return null
  if (!me.data) return <Navigate to="/login" replace />

  return (
    <div className="flex min-h-dvh">
      <Sidebar username={me.data.username} />
      <main className="min-w-0 flex-1">
        <Outlet />
      </main>
    </div>
  )
}

function Sidebar({ username }: { username: string }) {
  const { boardId } = useParams()
  const boards = useBoards()
  const [creating, setCreating] = useState(false)
  const signOut = useSignOut()

  return (
    <aside
      data-print-hide
      className="sticky top-0 hidden h-dvh w-[248px] shrink-0 flex-col border-r border-border bg-bg-subtle px-2.5 py-3 md:flex"
    >
      <Link
        to="/"
        className="flex h-8 items-center px-2 text-[14px] font-semibold tracking-[-0.01em]"
      >
        finchart-notes
      </Link>

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <SidebarSection title="보드">
          {boards.isPending &&
            [0, 1, 2].map((i) => <Skeleton key={i} className="mx-2 my-1.5 h-4" />)}
          {boards.data?.map((board) => (
            <SidebarItem
              key={board.id}
              href={`/boards/${board.id}`}
              icon={LayoutGrid}
              active={board.id === boardId}
              asLink
            >
              {board.title}
            </SidebarItem>
          ))}
          {creating ? (
            <NewBoardForm
              onDone={() => {
                setCreating(false)
              }}
            />
          ) : (
            <button
              type="button"
              onClick={() => {
                setCreating(true)
              }}
              className="flex h-[30px] items-center gap-2 rounded-md px-2 text-[14px] text-text-faint transition-colors duration-150 hover:bg-bg-muted hover:text-text"
            >
              <Plus size={16} strokeWidth={1.5} aria-hidden="true" />새 보드
            </button>
          )}
        </SidebarSection>
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-border px-2 pt-2.5">
        <span className="truncate text-[12px] text-text-muted">{username}</span>
        <IconButton
          icon={LogOut}
          label="로그아웃"
          size="sm"
          onClick={() => {
            signOut.mutate()
          }}
        />
      </div>
    </aside>
  )
}

function NewBoardForm({ onDone }: { onDone: () => void }) {
  const [title, setTitle] = useState('')
  const create = useCreateBoard()
  const navigate = useNavigate()
  const toast = useToast()

  const submit = (event: SyntheticEvent) => {
    event.preventDefault()
    if (!title.trim()) return
    create.mutate(title.trim(), {
      onSuccess: (board) => {
        onDone()
        void navigate(`/boards/${board.id}`)
      },
      onError: (error) => {
        toast({
          title: '보드를 만들지 못했습니다',
          description: errorMessage(error),
          tone: 'danger',
        })
      },
    })
  }

  return (
    <form onSubmit={submit} className="px-1 py-1">
      <Input
        aria-label="새 보드 이름"
        autoFocus
        value={title}
        placeholder="보드 이름"
        className="h-8"
        disabled={create.isPending}
        onChange={(e) => {
          setTitle(e.target.value)
        }}
        onBlur={() => {
          if (!title.trim()) onDone()
        }}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onDone()
        }}
      />
    </form>
  )
}
