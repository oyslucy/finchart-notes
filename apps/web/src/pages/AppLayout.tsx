import { House, LayoutGrid, LogOut, Menu, Plus, Settings, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { Dialog as DialogPrimitive } from 'radix-ui'
import { useState, type SyntheticEvent } from 'react'
import { Link, Navigate, Outlet, useLocation, useNavigate, useParams } from 'react-router'

import { Input } from '../components/ui/Field.tsx'
import { IconButton } from '../components/ui/IconButton.tsx'
import { Logo } from '../components/ui/Logo.tsx'
import { SidebarItem, SidebarSection } from '../components/ui/SidebarItem.tsx'
import { Skeleton } from '../components/ui/Skeleton.tsx'
import { useToast } from '../components/ui/toast-context.ts'
import { durations, easeOut, fade } from '../design/motion.ts'
import { useMe, useSignOut } from '../features/auth/session.ts'
import { useBoards, useCreateBoard } from '../features/boards/queries.ts'
import { CardDragProvider } from '../features/cards/CardDragProvider.tsx'
import { MoveDock } from '../features/cards/MoveDock.tsx'
import { useBoardDrop } from '../features/cards/useBoardDrop.ts'
import { cx } from '../design/cx.ts'
import { errorMessage } from '../lib/api.ts'
import type { Board } from '../lib/types.ts'

export default function AppLayout() {
  const me = useMe()

  if (me.isPending) return null
  if (!me.data) return <Navigate to="/login" replace />

  return (
    <CardDragProvider>
      <div className="flex min-h-dvh flex-col md:flex-row">
        <MobileBar username={me.data.username} />
        <aside
          data-print-hide
          className="sticky top-0 hidden h-dvh w-[248px] shrink-0 flex-col border-r border-border bg-bg-subtle px-2.5 py-3 md:flex"
        >
          <SidebarContent username={me.data.username} />
        </aside>
        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
        <MoveDock />
      </div>
    </CardDragProvider>
  )
}

function MobileBar({ username }: { username: string }) {
  const { pathname } = useLocation()
  // Remember where the drawer was opened; navigating anywhere else closes it.
  const [openedAt, setOpenedAt] = useState<string | null>(null)
  const open = openedAt === pathname
  const setOpen = (next: boolean) => {
    setOpenedAt(next ? pathname : null)
  }

  return (
    <header
      data-print-hide
      className="sticky top-0 z-30 flex h-12 items-center justify-between border-b border-border bg-bg px-3 md:hidden"
    >
      <Link to="/" className="flex items-center px-1" aria-label="finchart-notes 홈">
        <Logo />
      </Link>
      <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
        <DialogPrimitive.Trigger asChild>
          <IconButton icon={Menu} label="메뉴 열기" tooltip={false} />
        </DialogPrimitive.Trigger>
        <AnimatePresence>
          {open && (
            <DialogPrimitive.Portal forceMount>
              <DialogPrimitive.Overlay asChild forceMount>
                <motion.div className="fixed inset-0 z-40 bg-overlay" {...fade} />
              </DialogPrimitive.Overlay>
              <DialogPrimitive.Content asChild forceMount>
                <motion.nav
                  className="fixed inset-y-0 left-0 z-50 flex w-[280px] max-w-[85vw] flex-col border-r border-border bg-bg-subtle px-2.5 py-3 shadow-pop focus:outline-none"
                  initial={{ x: -24, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  exit={{ x: -24, opacity: 0 }}
                  transition={{ duration: durations.appear, ease: easeOut }}
                >
                  <DialogPrimitive.Title className="sr-only">메뉴</DialogPrimitive.Title>
                  <DialogPrimitive.Description className="sr-only">
                    보드를 고르거나 새로 만듭니다.
                  </DialogPrimitive.Description>
                  <DialogPrimitive.Close asChild>
                    <IconButton
                      icon={X}
                      label="메뉴 닫기"
                      size="sm"
                      tooltip={false}
                      className="absolute top-3 right-2.5"
                    />
                  </DialogPrimitive.Close>
                  <SidebarContent username={username} />
                </motion.nav>
              </DialogPrimitive.Content>
            </DialogPrimitive.Portal>
          )}
        </AnimatePresence>
      </DialogPrimitive.Root>
    </header>
  )
}

function SidebarContent({ username }: { username: string }) {
  const { boardId } = useParams()
  const { pathname } = useLocation()
  const boards = useBoards()
  const [creating, setCreating] = useState(false)
  const signOut = useSignOut()

  return (
    <>
      <Link to="/" className="flex h-8 items-center px-2" aria-label="finchart-notes 홈">
        <Logo />
      </Link>

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <div className="pt-3">
          <SidebarItem href="/" icon={House} active={pathname === '/'} asLink>
            홈
          </SidebarItem>
          <SidebarItem href="/settings" icon={Settings} active={pathname === '/settings'} asLink>
            설정
          </SidebarItem>
        </div>
        <SidebarSection title="보드">
          {boards.isPending &&
            [0, 1, 2].map((i) => <Skeleton key={i} className="mx-2 my-1.5 h-4" />)}
          {boards.data?.map((board) => (
            <BoardNavItem key={board.id} board={board} active={board.id === boardId} />
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
    </>
  )
}

/** A sidebar board that also accepts dragged cards. */
function BoardNavItem({ board, active }: { board: Board; active: boolean }) {
  const { over, accepts, handlers } = useBoardDrop(board)
  return (
    <SidebarItem
      href={`/boards/${board.id}`}
      icon={LayoutGrid}
      active={active}
      asLink
      {...handlers}
      className={cx(
        accepts && 'outline-1 outline-border-strong outline-dashed',
        over && 'bg-accent-subtle text-accent outline-accent',
      )}
    >
      {board.title}
    </SidebarItem>
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
