import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api.ts'
import type { Card, CardPatch } from '../../lib/types.ts'

export const cardKeys = {
  board: (boardId: string) => ['boards', boardId, 'cards'] as const,
  recent: ['cards', 'recent'] as const,
}

export const quotaKey = ['quota'] as const

export function useQuota() {
  // Telegram uploads use the same quota, so refresh on focus and now and then.
  return useQuery({ queryKey: quotaKey, queryFn: api.quota, refetchInterval: 5 * 60_000 })
}

export function useRecentCards(query = '') {
  return useQuery({
    queryKey: [...cardKeys.recent, query],
    queryFn: () => api.listRecentCards(query),
    placeholderData: (previous) => previous,
  })
}

export function useCards(boardId: string) {
  return useQuery({ queryKey: cardKeys.board(boardId), queryFn: () => api.listCards(boardId) })
}

export function useUploadCard(boardId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => api.uploadCard(boardId, file),
    onSettled: () => qc.invalidateQueries({ queryKey: quotaKey }),
    onSuccess: ({ card, duplicate }) => {
      void qc.invalidateQueries({ queryKey: cardKeys.recent })
      if (duplicate && card.board_id !== boardId) return
      // The server puts new cards first and shifts the rest.
      qc.setQueryData<Card[]>(cardKeys.board(boardId), (prev = []) =>
        prev.some((c) => c.id === card.id)
          ? prev
          : [card, ...prev.map((c) => ({ ...c, position: c.position + 1 }))],
      )
    },
  })
}

export function useUpdateCard(boardId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: CardPatch }) => api.updateCard(id, patch),
    onSuccess: (card, { patch }) => {
      void qc.invalidateQueries({ queryKey: cardKeys.recent })
      qc.setQueryData<Card[]>(cardKeys.board(boardId), (prev = []) =>
        prev.map((c) => (c.id === card.id ? card : c)),
      )
      // Pinning changes the order, which only the server knows exactly.
      if (patch.pinned !== undefined)
        void qc.invalidateQueries({ queryKey: cardKeys.board(boardId) })
    },
  })
}

/** Asks the model again about the card's crop; the server keeps the image and the note. */
export function useReanalyzeCard(boardId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.reanalyzeCard,
    onSettled: () => qc.invalidateQueries({ queryKey: quotaKey }),
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

export function useMoveCard() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ card, boardId }: { card: Card; boardId: string }) =>
      api.moveCard(card.id, boardId),
    onSuccess: (_moved, { card, boardId }) => {
      void qc.invalidateQueries({ queryKey: cardKeys.recent })
      void qc.invalidateQueries({ queryKey: cardKeys.board(card.board_id) })
      void qc.invalidateQueries({ queryKey: cardKeys.board(boardId) })
    },
  })
}

/** Uploads to any board (home composer); creates "Inbox" when the user has no board yet. */
export function useQuickUpload() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ boardId, file }: { boardId: string | null; file: File }) => {
      const target = boardId ?? (await api.createBoard('Inbox')).id
      return { target, result: await api.uploadCard(target, file) }
    },
    onSettled: () => qc.invalidateQueries({ queryKey: quotaKey }),
    onSuccess: ({ target }) => {
      void qc.invalidateQueries({ queryKey: cardKeys.recent })
      void qc.invalidateQueries({ queryKey: cardKeys.board(target) })
      void qc.invalidateQueries({ queryKey: ['boards'], exact: true })
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
