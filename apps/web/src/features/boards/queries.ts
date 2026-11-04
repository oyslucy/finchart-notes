import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api.ts'
import type { Board } from '../../lib/types.ts'

export const boardKeys = {
  all: ['boards'] as const,
}

export function useBoards() {
  return useQuery({ queryKey: boardKeys.all, queryFn: api.listBoards })
}

export function useCreateBoard() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.createBoard,
    onSuccess: (board) => {
      qc.setQueryData<Board[]>(boardKeys.all, (prev = []) => [board, ...prev])
    },
  })
}

export function useRenameBoard() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => api.renameBoard(id, title),
    onSuccess: (board) => {
      void qc.invalidateQueries({ queryKey: ['cards', 'recent'] })
      qc.setQueryData<Board[]>(boardKeys.all, (prev = []) =>
        prev.map((b) => (b.id === board.id ? board : b)),
      )
    },
  })
}

export function useDeleteBoard() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.deleteBoard,
    onSuccess: (_void, id) => {
      void qc.invalidateQueries({ queryKey: ['cards', 'recent'] })
      qc.setQueryData<Board[]>(boardKeys.all, (prev = []) => prev.filter((b) => b.id !== id))
    },
  })
}
