import { FileText, FileUp, LoaderCircle, Pin, PinOff, RotateCw, Search, X } from 'lucide-react'
import { useCallback, useState } from 'react'
import { Link } from 'react-router'

import { Icon } from '../components/ui/Icon.tsx'
import { IconButton } from '../components/ui/IconButton.tsx'
import { Skeleton } from '../components/ui/Skeleton.tsx'
import { useToast } from '../components/ui/toast-context.ts'
import { cx } from '../design/cx.ts'
import { TranslationQuotaNote } from '../features/cards/QuotaNote.tsx'
import { UploadZone } from '../features/cards/UploadZone.tsx'
import {
  FAILURE_MESSAGE,
  useArticles,
  useRetryArticle,
  useToggleArticlePin,
  useUploadArticle,
} from '../features/news/queries.ts'
import { errorMessage, isRetryable } from '../lib/api.ts'
import type { ArticleSummary } from '../lib/types.ts'
import { useDebounced } from '../lib/useDebounced.ts'

const PDF = ['application/pdf']
const dateFormat = new Intl.DateTimeFormat('ko-KR', { month: 'numeric', day: 'numeric' })

/** Sends PDFs one after another; each returns at once and translates on the server. */
function useNewsUploads() {
  const upload = useUploadArticle()
  const toast = useToast()
  const [pending, setPending] = useState(0)

  const onFiles = useCallback(
    // Named so a failed file's retry goes through the same queue
    function run(files: File[]) {
      setPending((n) => n + files.length)
      void files.reduce(async (previous, file) => {
        await previous
        try {
          const { duplicate } = await upload.mutateAsync(file)
          if (duplicate) toast({ title: '이미 올린 PDF라 기존 번역을 불러왔습니다' })
        } catch (error) {
          toast({
            title: `${file.name} 업로드 실패`,
            description: errorMessage(error),
            tone: 'danger',
            ...(isRetryable(error) && {
              action: {
                label: '다시 시도',
                onClick: () => {
                  run([file])
                },
              },
            }),
          })
        } finally {
          setPending((n) => n - 1)
        }
      }, Promise.resolve())
    },
    [upload, toast],
  )

  return { onFiles, pending }
}

export default function NewsPage() {
  const [input, setInput] = useState('')
  const query = useDebounced(input.trim(), 250)
  const articles = useArticles(query)
  const { onFiles, pending } = useNewsUploads()
  const list = articles.data ?? []

  return (
    <div className="mx-auto flex max-w-[960px] flex-col gap-5 px-4 pt-6 pb-24 md:px-10 md:pt-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-[26px]">뉴스</h1>
        <p className="text-[14px] text-text-muted">
          뉴스 PDF를 올리면 원문과 한국어 번역을 문단별로 나란히 보여 드립니다.
        </p>
      </header>

      <UploadZone
        onFiles={onFiles}
        busy={pending > 0}
        accept={PDF}
        noun="뉴스 PDF를"
        icon={FileUp}
        hint="번역은 1~2분 걸립니다"
        aside={<TranslationQuotaNote />}
      />

      <div className="flex items-center justify-between gap-3 pt-2">
        <h2 className="text-[15px] font-semibold">
          기사 <span className="pl-1 text-[13px] font-normal text-text-faint">{list.length}건</span>
        </h2>
        <NewsSearch value={input} onChange={setInput} />
      </div>

      {articles.isPending ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-[76px] rounded-lg" />
          ))}
        </div>
      ) : list.length === 0 ? (
        <p className="py-16 text-center text-[14px] text-text-muted">
          {query ? '검색 결과가 없습니다.' : '아직 기사가 없습니다. 뉴스 PDF를 올려 보세요.'}
        </p>
      ) : (
        <ul className="flex flex-col divide-y divide-border overflow-hidden rounded-lg border border-border bg-surface">
          {list.map((article) => (
            <ArticleRow key={article.id} article={article} />
          ))}
        </ul>
      )}
    </div>
  )
}

function ArticleRow({ article }: { article: ArticleSummary }) {
  const meta = [
    article.source,
    article.published ?? dateFormat.format(new Date(article.created_at)),
    `${String(article.page_count)}쪽`,
  ].filter(Boolean)

  return (
    <li className="group relative flex items-start gap-3 px-4 py-3.5 hover:bg-bg-subtle">
      <span className={cx('mt-0.5', article.pinned ? 'text-accent' : 'text-text-faint')}>
        <Icon icon={article.pinned ? Pin : FileText} size={18} />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <Link
          to={`/news/${article.id}`}
          className="truncate text-[15px] font-medium text-text after:absolute after:inset-0"
        >
          {article.title_ko ?? article.filename}
        </Link>
        {article.status === 'done' && article.summary[0] && (
          <p className="truncate text-[13px] text-text-muted">{article.summary[0]}</p>
        )}
        {article.status === 'failed' && (
          <p className="text-[13px] text-danger">{FAILURE_MESSAGE[article.error ?? 'failed']}</p>
        )}
        <p className="text-[12px] text-text-faint tabular">{meta.join(' · ')}</p>
      </div>
      <ArticleStatus article={article} />
      <PinButton article={article} />
    </li>
  )
}

function PinButton({ article }: { article: ArticleSummary }) {
  const { toggle, pending } = useToggleArticlePin(article)
  return (
    <IconButton
      icon={article.pinned ? PinOff : Pin}
      label={article.pinned ? '고정 해제' : '맨 위에 고정'}
      size="sm"
      disabled={pending}
      onClick={toggle}
      // Above the row's stretched link; on desktop it shows on hover, phones always show it
      className="relative z-10 -my-1 md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100"
    />
  )
}

function ArticleStatus({ article }: { article: ArticleSummary }) {
  const retry = useRetryArticle()
  const toast = useToast()

  if (article.status === 'pending')
    return (
      <span className="inline-flex shrink-0 items-center gap-1.5 text-[12px] text-text-muted">
        <LoaderCircle size={14} className="animate-spin" aria-hidden="true" />
        번역 중
      </span>
    )
  if (article.status === 'failed')
    return (
      <button
        type="button"
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
        // Above the row's stretched link
        className="relative z-10 inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-[13px] font-medium text-accent hover:bg-accent-subtle disabled:opacity-45"
      >
        <RotateCw size={14} aria-hidden="true" />
        다시 시도
      </button>
    )
  return null
}

function NewsSearch({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="relative w-full max-w-[260px]">
      <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-text-faint">
        <Icon icon={Search} size={16} />
      </span>
      <input
        type="search"
        aria-label="기사 검색"
        value={value}
        placeholder="제목, 매체, 본문 검색"
        onChange={(e) => {
          onChange(e.target.value)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onChange('')
        }}
        className="h-9 w-full rounded-md border border-border bg-surface pr-9 pl-9 text-[14px] placeholder:text-text-faint hover:border-border-strong focus:border-accent focus:shadow-[0_0_0_3px_var(--focus-ring)] focus:outline-none [&::-webkit-search-cancel-button]:hidden"
      />
      {value && (
        <button
          type="button"
          aria-label="검색어 지우기"
          onClick={() => {
            onChange('')
          }}
          className="absolute top-1/2 right-2 inline-flex size-6 -translate-y-1/2 items-center justify-center rounded-sm text-text-faint hover:bg-bg-muted hover:text-text"
        >
          <Icon icon={X} size={14} />
        </button>
      )}
    </div>
  )
}
