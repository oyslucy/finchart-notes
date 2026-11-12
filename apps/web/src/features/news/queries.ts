import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useToast } from '../../components/ui/toast-context.ts'
import { api, errorMessage } from '../../lib/api.ts'
import type { Article, ArticleSummary } from '../../lib/types.ts'

export const articleKeys = {
  all: ['articles'] as const,
  list: (q: string) => ['articles', 'list', q] as const,
  one: (id: string) => ['articles', 'one', id] as const,
  quota: ['articles', 'quota'] as const,
}

// Translation runs on the server after the upload returns; poll until it settles.
const POLL_MS = 3000

export function useArticles(query = '') {
  return useQuery({
    queryKey: articleKeys.list(query),
    queryFn: () => api.listArticles(query),
    placeholderData: (previous) => previous,
    refetchInterval: (q) =>
      q.state.data?.some((a: ArticleSummary) => a.status === 'pending') ? POLL_MS : false,
  })
}

export function useArticle(id: string) {
  return useQuery({
    queryKey: articleKeys.one(id),
    queryFn: () => api.getArticle(id),
    refetchInterval: (q) => (q.state.data?.status === 'pending' ? POLL_MS : false),
  })
}

export function useTranslationQuota() {
  return useQuery({
    queryKey: articleKeys.quota,
    queryFn: api.translationQuota,
    refetchInterval: 5 * 60_000,
  })
}

function useSettle() {
  const qc = useQueryClient()
  return (article?: Article) => {
    if (article) qc.setQueryData(articleKeys.one(article.id), article)
    void qc.invalidateQueries({ queryKey: articleKeys.all })
  }
}

export function useUploadArticle() {
  const settle = useSettle()
  return useMutation({
    mutationFn: api.uploadArticle,
    onSuccess: ({ article }) => {
      settle(article)
    },
    onError: () => {
      settle()
    },
  })
}

export function useRetryArticle() {
  const settle = useSettle()
  return useMutation({
    mutationFn: api.retryArticle,
    onSettled: (article) => {
      settle(article)
    },
  })
}

/** Pinned articles stay at the top of the news list. */
export function useToggleArticlePin(article: ArticleSummary) {
  const settle = useSettle()
  const toast = useToast()
  const pin = useMutation({
    mutationFn: (pinned: boolean) => api.pinArticle(article.id, pinned),
    onSuccess: (saved) => {
      settle(saved)
      toast({ title: saved.pinned ? '맨 위에 고정했습니다' : '고정을 해제했습니다' })
    },
    onError: (error) => {
      toast({ title: '바꾸지 못했습니다', description: errorMessage(error), tone: 'danger' })
    },
  })
  return {
    toggle: () => {
      pin.mutate(!article.pinned)
    },
    pending: pin.isPending,
  }
}

export function useDeleteArticle() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.deleteArticle,
    onSuccess: (_void, id) => {
      qc.removeQueries({ queryKey: articleKeys.one(id) })
      void qc.invalidateQueries({ queryKey: articleKeys.all })
    },
  })
}

export const FAILURE_MESSAGE: Record<string, string> = {
  too_long: '기사가 너무 길어 번역하지 못했습니다. 페이지를 나눠 올려 주세요.',
  unreadable: 'PDF에서 기사를 읽지 못했습니다.',
  failed: '번역 중 오류가 발생했습니다.',
  interrupted: '서버가 다시 시작되어 번역이 중단되었습니다.',
}
