import { Navigate } from 'react-router'

import { Skeleton } from '../components/ui/Skeleton.tsx'
import { useBoards } from '../features/boards/queries.ts'

export default function BoardsIndexPage() {
  const boards = useBoards()

  if (boards.isPending) {
    return (
      <div className="mx-auto max-w-[760px] px-10 pt-8">
        <Skeleton className="h-8 w-1/2" />
      </div>
    )
  }
  if (boards.isError) {
    return (
      <p className="px-10 pt-10 text-[14px] text-danger">
        보드를 불러오지 못했다. {boards.error.message}
      </p>
    )
  }
  const [first] = boards.data
  if (first) return <Navigate to={`/boards/${first.id}`} replace />

  return (
    <div className="mx-auto flex max-w-[480px] flex-col gap-2 px-6 pt-32 text-center">
      <h1 className="text-[20px]">첫 보드를 만들어 보세요</h1>
      <p className="text-[14px] text-text-muted">
        왼쪽 사이드바의 ‘새 보드’를 눌러 주제별로 차트를 모은다. 예: 2026 4분기 매크로
      </p>
    </div>
  )
}
