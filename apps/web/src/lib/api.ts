import type {
  Article,
  ArticleSubmitResult,
  ArticleSummary,
  Board,
  Card,
  CardCreateResult,
  CardPatch,
  Quota,
  RecentCard,
} from './types.ts'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')

  // The session lives in an httpOnly cookie, which same-origin fetches send automatically.
  const response = await fetch(`/api${path}`, { ...init, headers, credentials: 'same-origin' })
  if (response.status === 204) return undefined as T
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const detail =
      body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string'
        ? body.detail
        : response.statusText
    throw new ApiError(response.status, detail)
  }
  return body as T
}

export interface Me {
  username: string
}

export interface TelegramStatus {
  enabled: boolean
  linked: boolean
  telegram_username: string | null
  bot_username: string | null
}

export interface TelegramLinkToken {
  url: string
  expires_at: string
}

export const api = {
  telegramStatus: () => request<TelegramStatus>('/telegram/status'),
  telegramLinkToken: () => request<TelegramLinkToken>('/telegram/link-token', { method: 'POST' }),
  telegramUnlink: () => request<undefined>('/telegram/link', { method: 'DELETE' }),

  me: () => request<Me>('/auth/me'),
  signup: (username: string, password: string) =>
    request<Me>('/auth/signup', { method: 'POST', body: JSON.stringify({ username, password }) }),
  login: (username: string, password: string) =>
    request<Me>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => request<undefined>('/auth/logout', { method: 'POST' }),

  listBoards: () => request<Board[]>('/boards'),
  createBoard: (title: string) =>
    request<Board>('/boards', { method: 'POST', body: JSON.stringify({ title }) }),
  renameBoard: (id: string, title: string) =>
    request<Board>(`/boards/${id}`, { method: 'PATCH', body: JSON.stringify({ title }) }),
  deleteBoard: (id: string) => request<undefined>(`/boards/${id}`, { method: 'DELETE' }),

  listRecentCards: (q = '') =>
    request<RecentCard[]>(q ? `/cards?q=${encodeURIComponent(q)}` : '/cards'),
  listCards: (boardId: string) => request<Card[]>(`/boards/${boardId}/cards`),
  uploadCard: (boardId: string, file: File) => {
    const form = new FormData()
    form.append('image', file)
    return request<CardCreateResult>(`/boards/${boardId}/cards`, { method: 'POST', body: form })
  },
  updateCard: (id: string, patch: CardPatch) =>
    request<Card>(`/cards/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  reanalyzeCard: (id: string) => request<Card>(`/cards/${id}/reanalyze`, { method: 'POST' }),
  quota: () => request<Quota>('/quota'),
  deleteCard: (id: string) => request<undefined>(`/cards/${id}`, { method: 'DELETE' }),
  moveCard: (id: string, boardId: string) =>
    request<Card>(`/cards/${id}/move`, {
      method: 'POST',
      body: JSON.stringify({ board_id: boardId }),
    }),
  listArticles: (q = '') =>
    request<ArticleSummary[]>(q ? `/articles?q=${encodeURIComponent(q)}` : '/articles'),
  getArticle: (id: string) => request<Article>(`/articles/${id}`),
  uploadArticle: (file: File) => {
    const form = new FormData()
    form.append('pdf', file)
    return request<ArticleSubmitResult>('/articles', { method: 'POST', body: form })
  },
  pinArticle: (id: string, pinned: boolean) =>
    request<Article>(`/articles/${id}`, { method: 'PATCH', body: JSON.stringify({ pinned }) }),
  retryArticle: (id: string) => request<Article>(`/articles/${id}/retry`, { method: 'POST' }),
  deleteArticle: (id: string) => request<undefined>(`/articles/${id}`, { method: 'DELETE' }),
  translationQuota: () => request<Quota>('/articles/quota'),
  reorder: (boardId: string, cardIds: string[]) =>
    request<undefined>(`/boards/${boardId}/order`, {
      method: 'PUT',
      body: JSON.stringify({ card_ids: cardIds }),
    }),
}

/** Worth retrying as is: the model or the network failed, not the request itself. */
export function isRetryable(error: unknown): boolean {
  return error instanceof ApiError ? error.status >= 500 : error instanceof TypeError
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 413 && error.message === 'pdf too large')
      return 'PDF가 너무 큽니다. 20MB 이하로 올려 주세요.'
    if (error.status === 413) return '이미지가 너무 큽니다. 10MB 이하로 올려 주세요.'
    if (error.status === 415 && error.message === 'unreadable_pdf')
      return 'PDF를 열 수 없습니다. 암호가 걸려 있지 않은 PDF로 올려 주세요.'
    if (error.status === 415 && error.message === 'only pdf') return 'PDF 파일만 올릴 수 있습니다.'
    if (error.status === 415) return 'PNG, JPEG, WebP 이미지만 올릴 수 있습니다.'
    if (error.status === 422 && error.message === 'too_many_pages')
      return '쪽수가 너무 많습니다. 30쪽 이하 PDF로 올려 주세요.'
    if (error.status === 503 && error.message === 'translation_disabled')
      return '뉴스 번역 기능이 아직 설정되지 않았습니다.'
    if (error.status === 429 && error.message === 'daily_quota')
      return '오늘 쓸 수 있는 횟수를 모두 썼습니다. 초기화된 뒤 다시 시도해 주세요.'
    if (error.status === 429) return '업로드가 너무 잦습니다. 1분 뒤 다시 시도해 주세요.'
    if (error.status === 502) return '분석에 실패했습니다. 잠시 후 다시 시도해 주세요.'
    if (error.status === 403) return '이 계정은 사용이 허용되지 않았습니다.'
    return error.message
  }
  return '알 수 없는 오류가 발생했습니다.'
}
