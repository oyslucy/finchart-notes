import { useBoards } from '../features/boards/queries.ts'
import { useRecentCards } from '../features/cards/queries.ts'
import {
  THUMBNAIL_GRID as GRID,
  ThumbnailCard,
  ThumbnailSkeleton,
} from '../features/cards/ThumbnailCard.tsx'

export default function HomePage() {
  const boards = useBoards()
  const cards = useRecentCards()

  return (
    <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-6 pt-8 pb-24 md:px-10">
      <header className="flex items-baseline gap-3">
        <h1 className="text-[26px]">홈</h1>
        {cards.data && cards.data.length > 0 && (
          <span className="text-[13px] text-text-muted tabular">카드 {cards.data.length}장</span>
        )}
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

      {cards.isSuccess && cards.data.length === 0 && (
        <EmptyState hasBoards={boards.isPending || (boards.data?.length ?? 0) > 0} />
      )}

      {cards.isSuccess && cards.data.length > 0 && (
        <ul className={GRID}>
          {cards.data.map((card, index) => (
            <ThumbnailCard key={card.id} card={card} index={index} boardTitle={card.board_title} />
          ))}
        </ul>
      )}
    </div>
  )
}

function EmptyState({ hasBoards }: { hasBoards: boolean }) {
  return (
    <div className="mx-auto flex max-w-[420px] flex-col gap-2 pt-24 text-center">
      <h2 className="text-[20px]">
        {hasBoards ? '아직 카드가 없습니다' : '첫 보드를 만들어 보세요'}
      </h2>
      <p className="text-[14px] text-text-muted">
        {hasBoards
          ? '왼쪽에서 보드를 열고 차트 스크린샷을 올려보세요.'
          : '왼쪽 사이드바의 ‘새 보드’를 눌러 주제별로 차트를 모아 보세요. 예: 2026 4분기 매크로'}
      </p>
    </div>
  )
}
