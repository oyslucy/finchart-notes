import { Search, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { Icon } from '../components/ui/Icon.tsx'
import { Kbd } from '../components/ui/Kbd.tsx'
import { useToast } from '../components/ui/toast-context.ts'
import { useBoards } from '../features/boards/queries.ts'
import { HomeComposer } from '../features/cards/HomeComposer.tsx'
import { useQuickUpload, useRecentCards } from '../features/cards/queries.ts'
import {
  THUMBNAIL_GRID as GRID,
  ThumbnailCard,
  ThumbnailSkeleton,
} from '../features/cards/ThumbnailCard.tsx'
import { errorMessage } from '../lib/api.ts'
import { useDebounced } from '../lib/useDebounced.ts'

const BOARD_KEY = 'finchart-home-board'

function readStoredBoard(): string | null {
  try {
    return localStorage.getItem(BOARD_KEY)
  } catch {
    return null
  }
}

/** Uploads files one after another to the chosen board and tracks how many are left. */
function useComposerUploads(boardId: string | null, onBoardCreated: (id: string) => void) {
  const upload = useQuickUpload()
  const toast = useToast()
  const [pending, setPending] = useState(0)

  const onFiles = useCallback(
    (files: File[]) => {
      setPending((n) => n + files.length)
      let target = boardId
      void files.reduce(async (previous, file) => {
        await previous
        try {
          const { target: used, result } = await upload.mutateAsync({ boardId: target, file })
          if (target !== used) {
            target = used
            onBoardCreated(used)
          }
          toast(
            result.duplicate
              ? { title: '이미 올린 이미지라 기존 분석을 불러왔습니다' }
              : { title: '카드를 추가했습니다', description: result.card.title, tone: 'success' },
          )
        } catch (error) {
          toast({
            title: `${file.name} 분석 실패`,
            description: errorMessage(error),
            tone: 'danger',
          })
        } finally {
          setPending((n) => n - 1)
        }
      }, Promise.resolve())
    },
    [boardId, upload, toast, onBoardCreated],
  )

  return { onFiles, pending }
}

function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ['INPUT', 'TEXTAREA'].includes(target.tagName))
  )
}

export default function HomePage() {
  const boards = useBoards()
  const [input, setInput] = useState('')
  const query = useDebounced(input.trim(), 250)
  const cards = useRecentCards(query)
  const searchRef = useRef<HTMLInputElement>(null)
  const [storedBoard, setStoredBoard] = useState(readStoredBoard)
  const boardList = boards.data ?? []
  const selectedBoard = boardList.find((b) => b.id === storedBoard)?.id ?? boardList[0]?.id ?? null
  const selectBoard = useCallback((id: string) => {
    setStoredBoard(id)
    try {
      localStorage.setItem(BOARD_KEY, id)
    } catch {
      // Not persisted in private mode; the choice still applies for this visit.
    }
  }, [])
  const { onFiles, pending } = useComposerUploads(selectedBoard, selectBoard)

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === '/' && !isTyping(event.target)) {
        event.preventDefault()
        searchRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  }, [])

  const count = cards.data?.length ?? 0
  const searching = query.length > 0

  return (
    <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-4 pt-6 pb-24 md:px-10 md:pt-8">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-baseline gap-3">
          <h1 className="text-[26px]">홈</h1>
          {cards.isSuccess && (
            <span className="text-[13px] text-text-muted tabular" aria-live="polite">
              {searching ? `‘${query}’ 검색 결과 ${String(count)}장` : `카드 ${String(count)}장`}
            </span>
          )}
        </div>

        <div className="relative w-full sm:w-[320px]">
          <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-text-faint">
            <Icon icon={Search} size={16} />
          </span>
          <input
            ref={searchRef}
            type="search"
            aria-label="카드 검색"
            value={input}
            placeholder="제목, 해설, 메모, 보드 이름 검색"
            onChange={(e) => {
              setInput(e.target.value)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Escape') setInput('')
            }}
            className="h-9 w-full rounded-md border border-border bg-surface pr-9 pl-9 text-[14px] placeholder:text-text-faint hover:border-border-strong focus:border-accent focus:shadow-[0_0_0_3px_var(--focus-ring)] focus:outline-none [&::-webkit-search-cancel-button]:hidden"
          />
          {input ? (
            <button
              type="button"
              aria-label="검색어 지우기"
              onClick={() => {
                setInput('')
                searchRef.current?.focus()
              }}
              className="absolute top-1/2 right-2 inline-flex size-6 -translate-y-1/2 items-center justify-center rounded-sm text-text-faint hover:bg-bg-muted hover:text-text"
            >
              <Icon icon={X} size={14} />
            </button>
          ) : (
            <Kbd className="absolute top-1/2 right-2.5 hidden -translate-y-1/2 sm:inline-flex">
              /
            </Kbd>
          )}
        </div>
      </header>

      <HomeComposer
        boards={boardList}
        selectedId={selectedBoard}
        onSelect={selectBoard}
        onFiles={onFiles}
        busy={pending > 0}
      />

      <h2 className="-mb-2 text-[15px] text-text-secondary">
        {searching ? '검색 결과' : '최근 카드'}
      </h2>

      {cards.isPending && (
        <ul className={GRID}>
          {Array.from({ length: 8 }, (_, i) => (
            <ThumbnailSkeleton key={i} />
          ))}
        </ul>
      )}

      {cards.isError && (
        <p className="text-[14px] text-danger">카드를 불러오지 못했습니다. {cards.error.message}</p>
      )}

      {cards.isSuccess && count === 0 && pending === 0 && (
        <EmptyState
          searching={searching}
          hasBoards={boards.isPending || (boards.data?.length ?? 0) > 0}
        />
      )}

      {cards.isSuccess && (count > 0 || pending > 0) && (
        <ul className={GRID}>
          {!searching &&
            Array.from({ length: pending }, (_, i) => (
              <ThumbnailSkeleton
                key={`pending-${String(i)}`}
                label={i === 0 ? '분석 중' : '대기 중'}
              />
            ))}
          {cards.data.map((card, index) => (
            <ThumbnailCard key={card.id} card={card} index={index} boardTitle={card.board_title} />
          ))}
        </ul>
      )}
    </div>
  )
}

function EmptyState({ searching, hasBoards }: { searching: boolean; hasBoards: boolean }) {
  const [title, body] = searching
    ? [
        '검색 결과가 없습니다',
        '다른 단어로 찾아보세요. 제목, 해설, 핵심 관찰, 메모, 보드 이름에서 찾습니다.',
      ]
    : hasBoards
      ? ['아직 카드가 없습니다', '위에서 보드를 고르고 차트 스크린샷을 올려보세요.']
      : [
          '첫 스크린샷을 올려보세요',
          '위 칸에 끌어다 놓거나 붙여넣으면 됩니다. 보드가 없으면 Inbox를 만들어 저장합니다.',
        ]
  return (
    <div className="mx-auto flex max-w-[420px] flex-col gap-2 pt-12 text-center">
      <h2 className="text-[20px]">{title}</h2>
      <p className="text-[14px] text-text-muted">{body}</p>
    </div>
  )
}
