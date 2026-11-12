export interface Board {
  id: string
  title: string
  created_at: string
}

export interface Card {
  id: string
  board_id: string
  position: number
  title: string
  chart_type: string
  period: string | null
  takeaways: string[]
  interpretation: string
  caveats: string[]
  user_note: string | null
  model: string
  created_at: string
  pinned: boolean
  image_url: string
  thumb_url: string
}

export interface RecentCard extends Card {
  board_title: string
}

export interface CardCreateResult {
  card: Card
  duplicate: boolean
}

export interface Quota {
  limit: number
  used: number
  remaining: number
  resets_at: string
}

export type ArticleStatus = 'pending' | 'done' | 'failed'
export type ArticleFailure = 'too_long' | 'unreadable' | 'failed' | 'interrupted'

export interface ArticleSummary {
  id: string
  filename: string
  page_count: number
  status: ArticleStatus
  error: ArticleFailure | null
  language: string | null
  title: string | null
  title_ko: string | null
  source: string | null
  published: string | null
  summary: string[]
  created_at: string
  pinned: boolean
}

export interface Paragraph {
  kind: 'heading' | 'paragraph'
  original: string
  translated: string
}

export interface Article extends ArticleSummary {
  paragraphs: Paragraph[]
  pdf_url: string
}

export interface ArticleSubmitResult {
  article: Article
  duplicate: boolean
}

export type CardPatch = Partial<
  Pick<
    Card,
    'title' | 'period' | 'takeaways' | 'interpretation' | 'caveats' | 'user_note' | 'pinned'
  >
>

export const CHART_TYPE_LABEL: Record<string, string> = {
  line: '선',
  candlestick: '캔들스틱',
  bar: '막대',
  area: '영역',
  scatter: '산점도',
  pie: '원',
  heatmap: '히트맵',
  table: '표',
  mixed: '복합',
  other: '기타',
}
