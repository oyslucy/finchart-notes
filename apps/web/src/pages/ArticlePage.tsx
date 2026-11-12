import { ArrowLeft, ExternalLink, LoaderCircle, RotateCw, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router'

import { Button } from '../components/ui/Button.tsx'
import { Dialog } from '../components/ui/Dialog.tsx'
import { IconButton } from '../components/ui/IconButton.tsx'
import { Skeleton } from '../components/ui/Skeleton.tsx'
import { useToast } from '../components/ui/toast-context.ts'
import { cx } from '../design/cx.ts'
import {
  FAILURE_MESSAGE,
  useArticle,
  useDeleteArticle,
  useRetryArticle,
} from '../features/news/queries.ts'
import { ApiError, errorMessage } from '../lib/api.ts'
import type { Article, Paragraph } from '../lib/types.ts'

type View = 'both' | 'translated' | 'original'

const VIEWS: { value: View; label: string }[] = [
  { value: 'both', label: '나란히' },
  { value: 'translated', label: '번역' },
  { value: 'original', label: '원문' },
]

const VIEW_KEY = 'finchart.news.view'

function readView(): View {
  try {
    const stored = localStorage.getItem(VIEW_KEY)
    return VIEWS.some((v) => v.value === stored) ? (stored as View) : 'both'
  } catch {
    return 'both'
  }
}

export default function ArticlePage() {
  const { articleId = '' } = useParams()
  const article = useArticle(articleId)
  const [deleteOpen, setDeleteOpen] = useState(false)

  if (article.error instanceof ApiError && article.error.status === 404)
    return <Navigate to="/news" replace />

  const data = article.data
  return (
    <div className="mx-auto flex max-w-[1180px] flex-col gap-6 px-4 pt-5 pb-24 md:px-8">
      <nav className="flex items-center justify-between gap-2">
        <Link
          to="/news"
          className="-ml-1.5 inline-flex h-8 items-center gap-1.5 rounded-md px-1.5 text-[14px] text-text-secondary hover:bg-bg-muted hover:text-text"
        >
          <ArrowLeft size={16} strokeWidth={1.5} aria-hidden="true" />
          뉴스
        </Link>
        {data && (
          <div className="flex items-center gap-1">
            <a
              href={data.pdf_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[13px] text-text-secondary hover:bg-bg-muted hover:text-text"
            >
              <ExternalLink size={14} aria-hidden="true" />
              원본 PDF
            </a>
            <IconButton
              icon={Trash2}
              label="삭제"
              size="sm"
              onClick={() => {
                setDeleteOpen(true)
              }}
            />
          </div>
        )}
      </nav>

      {!data ? (
        <ArticleSkeleton />
      ) : (
        <>
          <ArticleHeader article={data} />
          {data.status === 'pending' && <Pending />}
          {data.status === 'failed' && <Failed article={data} />}
          {data.status === 'done' && <ArticleBody article={data} />}
          <DeleteArticleDialog article={data} open={deleteOpen} onOpenChange={setDeleteOpen} />
        </>
      )}
    </div>
  )
}

function ArticleHeader({ article }: { article: Article }) {
  const meta = [article.source, article.published, `${String(article.page_count)}쪽`].filter(
    Boolean,
  )
  const foreign = article.language !== 'ko'
  return (
    <header className="flex max-w-[820px] flex-col gap-2">
      <p className="text-[13px] text-text-muted tabular">{meta.join(' · ')}</p>
      <h1 className="text-[26px] leading-[1.3] text-balance">
        {article.title_ko ?? article.filename}
      </h1>
      {foreign && article.title && (
        <p lang={article.language ?? undefined} className="text-[15px] text-text-muted">
          {article.title}
        </p>
      )}
      {article.summary.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1.5 rounded-lg border border-border bg-bg-subtle px-5 py-4 text-[14px] leading-relaxed">
          {article.summary.map((point, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-accent" aria-hidden="true">
                •
              </span>
              {point}
            </li>
          ))}
        </ul>
      )}
    </header>
  )
}

function ArticleBody({ article }: { article: Article }) {
  const [view, setView] = useState(readView)
  // An article already in Korean has nothing to set beside it.
  const bilingual = article.paragraphs.some((p) => p.translated.trim())
  const shown = bilingual ? view : 'original'

  const choose = (next: View) => {
    setView(next)
    try {
      localStorage.setItem(VIEW_KEY, next)
    } catch {
      // Only remembered for this visit in private mode.
    }
  }

  return (
    <section className="flex flex-col gap-4">
      {bilingual && (
        <div
          role="radiogroup"
          aria-label="보기 방식"
          className="inline-flex self-start rounded-md border border-border bg-bg-subtle p-0.5"
        >
          {VIEWS.map((v) => (
            <button
              key={v.value}
              type="button"
              role="radio"
              aria-checked={shown === v.value}
              onClick={() => {
                choose(v.value)
              }}
              className={cx(
                'h-7 rounded-[5px] px-3 text-[13px] transition-colors duration-150',
                shown === v.value
                  ? 'bg-surface font-medium text-text shadow-xs'
                  : 'text-text-muted hover:text-text',
              )}
            >
              {v.label}
            </button>
          ))}
        </div>
      )}

      {shown === 'both' && (
        <div className="hidden grid-cols-2 gap-x-10 border-b border-border pb-2 text-[12px] font-medium text-text-faint md:grid">
          <span>원문</span>
          <span>한국어 번역</span>
        </div>
      )}

      <div className={cx('flex flex-col', shown === 'both' ? 'gap-1' : 'max-w-[720px] gap-4')}>
        {article.paragraphs.map((p, i) => (
          <ParagraphRow key={i} paragraph={p} view={shown} lang={article.language} />
        ))}
      </div>
    </section>
  )
}

function ParagraphRow({
  paragraph,
  view,
  lang,
}: {
  paragraph: Paragraph
  view: View
  lang: string | null
}) {
  const heading = paragraph.kind === 'heading'
  const text = cx(
    heading ? 'text-[17px] font-semibold' : 'text-[15px] leading-[1.75]',
    'whitespace-pre-line',
  )
  const original = (
    <p
      lang={lang ?? undefined}
      className={cx(
        text,
        // Under the translation on phones it is the reference, so it steps back further
        view === 'both' && 'text-[14px] text-text-muted md:text-[15px] md:text-text-secondary',
      )}
    >
      {paragraph.original}
    </p>
  )
  const translated = <p className={text}>{paragraph.translated || paragraph.original}</p>

  if (view === 'original') return original
  if (view === 'translated') return translated
  // Side by side on wide screens, translation over a muted original on phones; a row
  // highlight keeps the two halves of a paragraph together while reading across.
  return (
    <div
      className={cx(
        '-mx-3 grid gap-x-10 gap-y-2 rounded-md px-3 py-2.5 hover:bg-bg-subtle md:grid-cols-2',
        heading && 'pt-5',
      )}
    >
      <div className="order-2 md:order-1">{original}</div>
      <div className="order-1 md:order-2">{translated}</div>
    </div>
  )
}

function Pending() {
  return (
    <div className="flex flex-col gap-4">
      <p className="inline-flex items-center gap-2 text-[14px] text-text-muted">
        <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />
        번역하고 있습니다. 1~2분 걸릴 수 있습니다.
      </p>
      <div className="grid gap-x-10 gap-y-3 md:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </div>
    </div>
  )
}

function Failed({ article }: { article: Article }) {
  const retry = useRetryArticle()
  const toast = useToast()
  return (
    <div className="flex flex-col items-start gap-3 rounded-lg border border-border px-5 py-4">
      <p className="text-[14px] text-danger">{FAILURE_MESSAGE[article.error ?? 'failed']}</p>
      <Button
        variant="secondary"
        size="sm"
        icon={RotateCw}
        disabled={retry.isPending}
        onClick={() => {
          retry.mutate(article.id, {
            onError: (error) => {
              toast({
                title: '다시 시도하지 못했습니다',
                description: errorMessage(error),
                tone: 'danger',
              })
            },
          })
        }}
      >
        다시 번역
      </Button>
    </div>
  )
}

function ArticleSkeleton() {
  return (
    <div className="flex max-w-[820px] flex-col gap-3">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="h-8 w-3/4" />
      <Skeleton className="h-24" />
    </div>
  )
}

function DeleteArticleDialog({
  article,
  open,
  onOpenChange,
}: {
  article: Article
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const remove = useDeleteArticle()
  const navigate = useNavigate()
  const toast = useToast()
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="기사를 삭제할까요?"
      description="원본 PDF와 번역이 함께 삭제됩니다."
      footer={
        <>
          <Button
            variant="ghost"
            onClick={() => {
              onOpenChange(false)
            }}
          >
            취소
          </Button>
          <Button
            variant="danger"
            disabled={remove.isPending}
            onClick={() => {
              remove.mutate(article.id, {
                onSuccess: () => {
                  onOpenChange(false)
                  void navigate('/news')
                },
                onError: (error) => {
                  toast({
                    title: '삭제하지 못했습니다',
                    description: errorMessage(error),
                    tone: 'danger',
                  })
                },
              })
            }}
          >
            삭제
          </Button>
        </>
      }
    />
  )
}
