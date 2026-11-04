import { Search, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { Icon } from '../components/ui/Icon.tsx'
import { Kbd } from '../components/ui/Kbd.tsx'
import { useBoards } from '../features/boards/queries.ts'
import { useRecentCards } from '../features/cards/queries.ts'
import {
  THUMBNAIL_GRID as GRID,
  ThumbnailCard,
  ThumbnailSkeleton,
} from '../features/cards/ThumbnailCard.tsx'
import { useDebounced } from '../lib/useDebounced.ts'

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

      {cards.isSuccess && count === 0 && (
        <EmptyState
          searching={searching}
          hasBoards={boards.isPending || (boards.data?.length ?? 0) > 0}
        />
      )}

      {cards.isSuccess && count > 0 && (
        <ul className={GRID}>
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
      ? ['아직 카드가 없습니다', '왼쪽에서 보드를 열고 차트 스크린샷을 올려보세요.']
      : [
          '첫 보드를 만들어 보세요',
          '왼쪽 사이드바의 ‘새 보드’를 눌러 주제별로 차트를 모아 보세요. 예: 2026 4분기 매크로',
        ]
  return (
    <div className="mx-auto flex max-w-[420px] flex-col gap-2 pt-20 text-center">
      <h2 className="text-[20px]">{title}</h2>
      <p className="text-[14px] text-text-muted">{body}</p>
    </div>
  )
}
