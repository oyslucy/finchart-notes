import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api.ts'
import type { Card, CardPatch } from '../../lib/types.ts'

export const cardKeys = {
  board: (boardId: string) => ['boards', boardId, 'cards'] as const,
  recent: ['cards', 'recent'] as const,
}

export function useRecentCards() {
  return useQuery({ queryKey: cardKeys.recent, queryFn: api.listRecentCards })
}

export function useCards(boardId: string) {
  return useQuery({ queryKey: cardKeys.board(boardId), queryFn: () => api.listCards(boardId) })
}

export function useUploadCard(boardId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => api.uploadCard(boardId, file),
    onSuccess: ({ card, duplicate }) => {
      void qc.invalidateQueries({ queryKey: cardKeys.recent })
      if (duplicate && card.board_id !== boardId) return
      qc.setQueryData<Card[]>(cardKeys.board(boardId), (prev = []) =>
        prev.some((c) => c.id === card.id) ? prev : [...prev, card],
      )
    },
  })
}

export function useUpdateCard(boardId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: CardPatch }) => api.updateCard(id, patch),
    onSuccess: (card) => {
      void qc.invalidateQueries({ queryKey: cardKeys.recent })
      qc.setQueryData<Card[]>(cardKeys.board(boardId), (prev = []) =>
        prev.map((c) => (c.id === card.id ? card : c)),
      )
    },
  })
}

export function useDeleteCard(boardId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.deleteCard,
    onSuccess: (_void, id) => {
      void qc.invalidateQueries({ queryKey: cardKeys.recent })
      qc.setQueryData<Card[]>(cardKeys.board(boardId), (prev = []) =>
        prev.filter((c) => c.id !== id),
      )
    },
  })
}

export function useReorderCards(boardId: string) {
  const qc = useQueryClient()
  const key = cardKeys.board(boardId)
  return useMutation({
    mutationFn: (ids: string[]) => api.reorder(boardId, ids),
    onMutate: async (ids) => {
      await qc.cancelQueries({ queryKey: key })
      const previous = qc.getQueryData<Card[]>(key)
      if (previous) {
        const byId = new Map(previous.map((c) => [c.id, c]))
        qc.setQueryData<Card[]>(
          key,
          ids.flatMap((id, position) => {
            const card = byId.get(id)
            return card ? [{ ...card, position }] : []
          }),
        )
      }
      return { previous }
    },
    onError: (_error, _ids, context) => {
      if (context?.previous) qc.setQueryData(key, context.previous)
    },
  })
}
