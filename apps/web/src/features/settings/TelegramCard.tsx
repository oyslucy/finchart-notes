import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, ExternalLink, Link2Off, Send } from 'lucide-react'
import QRCode from 'qrcode'
import { useEffect, useRef, useState } from 'react'

import { Button } from '../../components/ui/Button.tsx'
import { Dialog } from '../../components/ui/Dialog.tsx'
import { Skeleton } from '../../components/ui/Skeleton.tsx'
import { useToast } from '../../components/ui/toast-context.ts'
import { api, errorMessage, type TelegramLinkToken } from '../../lib/api.ts'

const statusKey = ['telegram', 'status'] as const
const POLL_MS = 2000

function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const id = setInterval(() => {
      setNow(Date.now())
    }, 1000)
    return () => {
      clearInterval(id)
    }
  }, [active])
  return now
}

function useQrDataUrl(text: string | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!text) return
    let cancelled = false
    void QRCode.toString(text, {
      type: 'svg',
      margin: 1,
      errorCorrectionLevel: 'M',
      color: { dark: '#22201e', light: '#ffffff' },
    }).then((svg) => {
      if (!cancelled) setUrl(`data:image/svg+xml;utf8,${encodeURIComponent(svg)}`)
    })
    return () => {
      cancelled = true
    }
  }, [text])
  return text ? url : null
}

export function TelegramCard() {
  const qc = useQueryClient()
  const toast = useToast()
  const [link, setLink] = useState<TelegramLinkToken | null>(null)
  const [confirmUnlink, setConfirmUnlink] = useState(false)
  const now = useNow(link !== null)
  const expiresIn = link ? new Date(link.expires_at).getTime() - now : 0

  const status = useQuery({
    queryKey: statusKey,
    queryFn: api.telegramStatus,
    // Poll only while a link is open, to notice the moment the bot confirms it.
    refetchInterval: (query) =>
      link && expiresIn > 0 && !query.state.data?.linked ? POLL_MS : false,
  })
  const linked = status.data?.linked ?? false
  const waiting = link !== null && expiresIn > 0 && !linked
  const qr = useQrDataUrl(waiting ? link.url : undefined)

  const announced = useRef<string | null>(null)
  useEffect(() => {
    if (linked && link && announced.current !== link.url) {
      announced.current = link.url
      toast({ title: '텔레그램과 연결되었습니다', tone: 'success' })
    }
  }, [linked, link, toast])

  const create = useMutation({
    mutationFn: api.telegramLinkToken,
    onSuccess: setLink,
    onError: (e) => {
      toast({
        title: '연결 링크를 만들지 못했습니다',
        description: errorMessage(e),
        tone: 'danger',
      })
    },
  })
  const unlink = useMutation({
    mutationFn: api.telegramUnlink,
    onSuccess: () => {
      setConfirmUnlink(false)
      setLink(null)
      void qc.invalidateQueries({ queryKey: statusKey })
      toast({ title: '연결을 해제했습니다' })
    },
  })

  return (
    <section className="rounded-lg border border-border bg-surface">
      <header className="flex items-start gap-3 border-b border-border px-5 py-4">
        <span className="mt-0.5 text-accent">
          <Send size={18} strokeWidth={1.5} aria-hidden="true" />
        </span>
        <div className="flex flex-col gap-0.5">
          <h2 className="text-[16px]">텔레그램 연결</h2>
          <p className="text-[13px] text-text-muted">
            봇에게 차트 스크린샷을 보내면 분석해서 카드로 저장합니다.
          </p>
        </div>
      </header>

      <div className="px-5 py-4">
        {status.isPending && <Skeleton className="h-5 w-1/2" />}

        {status.data && !status.data.enabled && (
          <p className="text-[14px] text-text-muted">서버에 텔레그램 봇이 설정되지 않았습니다.</p>
        )}

        {status.data?.enabled && linked && (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[14px]">
              {status.data.telegram_username ? (
                <>
                  <span className="font-medium">@{status.data.telegram_username}</span> 계정과
                  연결되어 있습니다.
                </>
              ) : (
                '텔레그램 계정과 연결되어 있습니다.'
              )}{' '}
              <a
                href={`https://t.me/${status.data.bot_username ?? ''}`}
                target="_blank"
                rel="noreferrer"
                className="text-accent hover:underline"
              >
                봇 열기
              </a>
            </p>
            <Button
              size="sm"
              variant="danger"
              icon={Link2Off}
              onClick={() => {
                setConfirmUnlink(true)
              }}
            >
              연결 해제
            </Button>
          </div>
        )}

        {status.data?.enabled && !linked && !waiting && (
          <div className="flex flex-col items-start gap-3">
            {link && (
              <p className="text-[13px] text-danger">링크가 만료되었습니다. 다시 만들어 주세요.</p>
            )}
            <ol className="flex list-decimal flex-col gap-1 pl-4 text-[14px] text-text-secondary">
              <li>아래 버튼으로 연결 링크를 만듭니다(10분 동안 유효).</li>
              <li>휴대폰으로 QR을 찍거나 링크를 열고, 텔레그램에서 시작을 누릅니다.</li>
            </ol>
            <Button
              variant="primary"
              icon={Send}
              disabled={create.isPending}
              onClick={() => {
                create.mutate()
              }}
            >
              연결 링크 만들기
            </Button>
          </div>
        )}

        {status.data?.enabled && !linked && waiting && (
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <div className="size-[168px] shrink-0 rounded-md border border-border bg-white p-2">
              {qr ? (
                <img src={qr} alt="텔레그램 연결 QR 코드" className="size-full" />
              ) : (
                <Skeleton className="size-full" />
              )}
            </div>
            <div className="flex min-w-0 flex-col gap-2.5">
              <p className="text-[14px]">
                텔레그램에서 <span className="font-medium">시작</span>을 누르면 자동으로 연결됩니다.
              </p>
              <div className="flex flex-wrap gap-2">
                <a
                  href={link.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex h-8.5 items-center gap-1.5 rounded-md bg-accent px-3.5 text-[14px] font-medium text-accent-fg hover:bg-accent-hover"
                >
                  <ExternalLink size={16} strokeWidth={1.5} aria-hidden="true" />
                  텔레그램에서 열기
                </a>
                <Button
                  icon={Copy}
                  onClick={() => {
                    void navigator.clipboard.writeText(link.url).then(() => {
                      toast({ title: '링크를 복사했습니다' })
                    })
                  }}
                >
                  링크 복사
                </Button>
              </div>
              <p className="text-[12px] text-text-muted tabular" aria-live="polite">
                {Math.floor(expiresIn / 60000)}:
                {String(Math.floor((expiresIn % 60000) / 1000)).padStart(2, '0')} 후 만료 · 연결을
                기다리는 중…
              </p>
            </div>
          </div>
        )}
      </div>

      <Dialog
        open={confirmUnlink}
        onOpenChange={setConfirmUnlink}
        title="텔레그램 연결을 해제할까요?"
        description="해제하면 봇으로 보낸 이미지는 더 이상 분석되지 않습니다. 이미 만든 카드는 그대로 남습니다."
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => {
                setConfirmUnlink(false)
              }}
            >
              취소
            </Button>
            <Button
              variant="danger"
              disabled={unlink.isPending}
              onClick={() => {
                unlink.mutate()
              }}
            >
              연결 해제
            </Button>
          </>
        }
      />
    </section>
  )
}
