import {
  BookOpen,
  Copy,
  Download,
  FileText,
  LayoutGrid,
  Monitor,
  Moon,
  MoreHorizontal,
  Plus,
  Search,
  Settings,
  Sun,
  Trash2,
  Upload,
} from 'lucide-react'
import { motion } from 'motion/react'
import { useState, type ReactNode } from 'react'

import { Button } from '../components/ui/Button.tsx'
import { ChartCard, ChartCardSkeleton, type ChartCardData } from '../components/ui/ChartCard.tsx'
import { Dialog } from '../components/ui/Dialog.tsx'
import { Input, Textarea } from '../components/ui/Field.tsx'
import { IconButton } from '../components/ui/IconButton.tsx'
import { Kbd } from '../components/ui/Kbd.tsx'
import { SidebarItem, SidebarSection } from '../components/ui/SidebarItem.tsx'
import { Skeleton } from '../components/ui/Skeleton.tsx'
import { useToast } from '../components/ui/toast-context.ts'
import { Tooltip } from '../components/ui/Tooltip.tsx'
import { cx } from '../design/cx.ts'
import { appear } from '../design/motion.ts'
import { useTheme, type ThemePreference } from '../design/theme.ts'

const SECTIONS = [
  ['color', '색'],
  ['type', '타이포그래피'],
  ['shape', '형태'],
  ['button', '버튼'],
  ['field', '입력'],
  ['overlay', '오버레이'],
  ['feedback', '피드백'],
  ['sidebar', '사이드바'],
  ['card', '카드'],
] as const

const GRAYS = Array.from({ length: 10 }, (_, i) => i + 1)
const SEMANTIC = [
  'bg',
  'bg-subtle',
  'bg-muted',
  'surface',
  'border',
  'border-strong',
  'text',
  'text-secondary',
  'text-muted',
  'text-faint',
  'accent',
  'accent-hover',
  'accent-subtle',
  'danger',
  'success',
] as const

const SAMPLE_CARD: ChartCardData = {
  title: 'KOSPI 일봉',
  chartType: '캔들스틱',
  period: '2026.05 ~ 2026.10',
  imageUrl: null,
  takeaways: [
    '5월 약 2,650에서 10월 약 3,200까지 상승했습니다.',
    '7월 말부터 8월 중순까지 약 2,800선까지 조정을 거쳤습니다.',
    '9월 이후 양봉 비중이 늘며 상승 기울기가 가팔라졌습니다.',
  ],
  interpretation:
    '기간 전체로는 우상향 흐름이며, 8월 저점 이후 반등 폭이 앞선 상승 구간보다 큽니다. 거래량 정보가 없어 상승의 강도를 판단하기는 어렵습니다.',
  caveats: ['세로축이 2,600에서 시작해 변동 폭이 커 보일 수 있습니다.'],
  note: '9월 FOMC 전후 구간 다시 확인',
}

export default function DesignPage() {
  return (
    <div className="flex min-h-dvh bg-bg">
      <aside className="sticky top-0 hidden h-dvh w-[232px] shrink-0 flex-col border-r border-border bg-bg-subtle px-2.5 py-3 md:flex">
        <div className="flex h-8 items-center px-2 text-[14px] font-semibold tracking-[-0.01em]">
          finchart-notes
        </div>
        <SidebarSection title="Design system">
          {SECTIONS.map(([id, label]) => (
            <SidebarItem key={id} href={`#${id}`}>
              {label}
            </SidebarItem>
          ))}
        </SidebarSection>
      </aside>

      <main className="min-w-0 flex-1">
        <header className="sticky top-0 z-10 flex h-12 items-center justify-between border-b border-border bg-bg px-8">
          <div className="flex items-baseline gap-3">
            <h1 className="text-[15px] font-semibold">Design system</h1>
            <span className="text-[13px] text-text-muted">토큰과 컴포넌트</span>
          </div>
          <ThemeSwitch />
        </header>

        <motion.div {...appear} className="mx-auto flex max-w-[880px] flex-col px-8 pb-24">
          <ColorSection />
          <TypeSection />
          <ShapeSection />
          <ButtonSection />
          <FieldSection />
          <OverlaySection />
          <FeedbackSection />
          <SidebarDemo />
          <CardSection />
        </motion.div>
      </main>
    </div>
  )
}

function Section({
  id,
  title,
  lead,
  children,
}: {
  id: string
  title: string
  lead?: string
  children: ReactNode
}) {
  return (
    <section id={id} className="scroll-mt-14 border-b border-border py-10 last:border-b-0">
      <div className="mb-6 flex flex-col gap-1">
        <h2 className="text-[20px]">{title}</h2>
        {lead && <p className="max-w-[60ch] text-[14px] text-text-muted">{lead}</p>}
      </div>
      {children}
    </section>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] items-center gap-6 py-3">
      <div className="text-[12px] text-text-faint">{label}</div>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  )
}

function ThemeSwitch() {
  const [theme, setTheme] = useTheme()
  const options: [ThemePreference, typeof Sun, string][] = [
    ['light', Sun, '라이트'],
    ['dark', Moon, '다크'],
    ['system', Monitor, '시스템'],
  ]
  return (
    <div
      role="radiogroup"
      aria-label="테마"
      className="flex rounded-md border border-border bg-surface p-0.5"
    >
      {options.map(([value, icon, label]) => (
        <IconButton
          key={value}
          role="radio"
          aria-checked={theme === value}
          icon={icon}
          label={label}
          size="sm"
          className={cx('size-6.5', theme === value && 'bg-bg-muted text-text')}
          onClick={() => {
            setTheme(value)
          }}
        />
      ))}
    </div>
  )
}

function ColorSection() {
  return (
    <Section
      id="color"
      title="색"
      lead="따뜻한 중립 회색 10단계와 채도를 낮춘 딥블루 하나. 컴포넌트는 의미 토큰만 참조하고, 다크 모드에서는 의미 토큰이 다른 단계로 다시 연결됩니다."
    >
      <div className="grid grid-cols-10 overflow-hidden rounded-md border border-border">
        {GRAYS.map((n) => (
          <div key={n} className="flex flex-col">
            <div className="h-14" style={{ background: `var(--gray-${String(n)})` }} />
            <div className="border-t border-border bg-surface px-2 py-1.5 text-[11px] text-text-muted tabular">
              gray-{n}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-6 grid grid-cols-3 gap-x-6 gap-y-1">
        {SEMANTIC.map((name) => (
          <div key={name} className="flex items-center gap-2.5 py-1.5">
            <span
              className="size-5 shrink-0 rounded-sm border border-border"
              style={{ background: `var(--${name})` }}
            />
            <code className="font-mono text-[12px] text-text-secondary">--{name}</code>
          </div>
        ))}
      </div>
    </Section>
  )
}

function TypeSection() {
  return (
    <Section
      id="type"
      title="타이포그래피"
      lead="Pretendard Variable. 본문 15px/1.6, 제목 자간 -0.01em, 숫자는 tabular-nums."
    >
      <div className="flex flex-col divide-y divide-border">
        <TypeRow spec="34 / 600">
          <span className="text-[34px] leading-[1.2] font-semibold tracking-[-0.01em]">
            차트 노트
          </span>
        </TypeRow>
        <TypeRow spec="26 / 600">
          <span className="text-[26px] leading-[1.3] font-semibold tracking-[-0.01em]">
            2026년 4분기 시장 메모
          </span>
        </TypeRow>
        <TypeRow spec="20 / 600">
          <span className="text-[20px] font-semibold tracking-[-0.01em]">KOSPI와 원/달러 환율</span>
        </TypeRow>
        <TypeRow spec="17 / 600">
          <span className="text-[17px] font-semibold tracking-[-0.01em]">
            미국 10년물 국채 금리
          </span>
        </TypeRow>
        <TypeRow spec="15 / 400 · 1.6">
          <p className="max-w-[56ch]">
            기간 전체로는 우상향 흐름이며, 8월 저점 이후 반등 폭이 앞선 상승 구간보다 큽니다. 거래량
            정보가 없어 상승의 강도를 판단하기는 어렵습니다.
          </p>
        </TypeRow>
        <TypeRow spec="13 / muted">
          <span className="text-[13px] text-text-muted">
            캔들스틱 · 2026.05 ~ 2026.10 · gemini-3.5-flash-lite
          </span>
        </TypeRow>
        <TypeRow spec="tabular-nums">
          <div className="flex flex-col text-right text-[14px] tabular">
            <span>3,118.42</span>
            <span>2,904.07</span>
            <span>1,111.11</span>
          </div>
        </TypeRow>
      </div>
    </Section>
  )
}

function TypeRow({ spec, children }: { spec: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] items-baseline gap-6 py-4">
      <span className="text-[12px] text-text-faint tabular">{spec}</span>
      <div>{children}</div>
    </div>
  )
}

function ShapeSection() {
  return (
    <Section
      id="shape"
      title="형태"
      lead="모서리 6/8/10px, 1px 헤어라인, 거의 보이지 않는 그림자. 상자를 겹치지 않고 선과 여백으로 나눕니다."
    >
      <div className="grid grid-cols-3 gap-4">
        {(
          [
            ['radius-sm · 6', 'rounded-sm', ''],
            ['radius-md · 8', 'rounded-md', 'shadow-xs'],
            ['radius-lg · 10', 'rounded-lg', 'shadow-sm'],
          ] as const
        ).map(([label, radius, shadow]) => (
          <div
            key={label}
            className={cx(
              'flex h-24 items-end border border-border bg-surface p-3',
              radius,
              shadow,
            )}
          >
            <span className="text-[12px] text-text-muted tabular">
              {label}
              {shadow && ` · ${shadow}`}
            </span>
          </div>
        ))}
      </div>
    </Section>
  )
}

function ButtonSection() {
  return (
    <Section id="button" title="버튼">
      <Row label="variant">
        <Button variant="primary" icon={Upload}>
          스크린샷 올리기
        </Button>
        <Button>보드 만들기</Button>
        <Button variant="ghost">취소</Button>
        <Button variant="danger" icon={Trash2}>
          삭제
        </Button>
      </Row>
      <Row label="size sm">
        <Button size="sm" variant="primary">
          저장
        </Button>
        <Button size="sm" icon={Plus}>
          카드
        </Button>
        <Button size="sm" variant="ghost">
          더 보기
        </Button>
      </Row>
      <Row label="disabled">
        <Button variant="primary" disabled>
          분석 중
        </Button>
        <Button disabled>보드 만들기</Button>
      </Row>
      <Row label="icon">
        <IconButton icon={Search} label="검색" shortcut="⌘K" />
        <IconButton icon={Copy} label="복사" />
        <IconButton icon={Download} label="PDF로 내보내기" />
        <IconButton icon={MoreHorizontal} label="더 보기" />
        <IconButton icon={Settings} label="설정" size="sm" />
      </Row>
    </Section>
  )
}

function FieldSection() {
  return (
    <Section id="field" title="입력">
      <div className="grid max-w-[560px] gap-5">
        <Input label="보드 이름" placeholder="예: 2026 4분기 매크로" hint="최대 200자" />
        <Input
          label="보드 이름"
          defaultValue=""
          placeholder="비어 있음"
          error="이름을 입력해 주세요."
        />
        <Input label="모델" defaultValue="gemini-3.5-flash-lite" disabled />
        <Textarea label="메모" placeholder="이 차트에서 다시 볼 점을 적어 두세요." />
      </div>
    </Section>
  )
}

function OverlaySection() {
  const [open, setOpen] = useState(false)
  return (
    <Section
      id="overlay"
      title="오버레이"
      lead="툴팁은 300ms 지연 후 표시됩니다. 다이얼로그는 포커스를 가두고 Esc로 닫힙니다."
    >
      <Row label="tooltip">
        <Tooltip content="카드 삭제" shortcut="⌫">
          <Button size="sm" variant="ghost" icon={Trash2}>
            마우스를 올려 보세요
          </Button>
        </Tooltip>
      </Row>
      <Row label="dialog">
        <Button
          onClick={() => {
            setOpen(true)
          }}
        >
          보드 삭제
        </Button>
        <Dialog
          open={open}
          onOpenChange={setOpen}
          title="보드를 삭제할까요?"
          description="카드 12장과 원본 이미지가 함께 삭제되며 되돌릴 수 없습니다."
          footer={
            <>
              <Button
                variant="ghost"
                onClick={() => {
                  setOpen(false)
                }}
              >
                취소
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  setOpen(false)
                }}
              >
                삭제
              </Button>
            </>
          }
        />
      </Row>
    </Section>
  )
}

function FeedbackSection() {
  const toast = useToast()
  return (
    <Section id="feedback" title="피드백">
      <Row label="toast">
        <Button
          size="sm"
          onClick={() => {
            toast({
              title: '카드를 추가했습니다',
              description: 'KOSPI 일봉 · 캔들스틱',
              tone: 'success',
            })
          }}
        >
          성공
        </Button>
        <Button
          size="sm"
          onClick={() => {
            toast({
              title: '분석에 실패했습니다',
              description: '잠시 후 다시 시도해 주세요.',
              tone: 'danger',
            })
          }}
        >
          실패
        </Button>
        <Button
          size="sm"
          onClick={() => {
            toast({ title: '이미 올린 이미지라 기존 분석을 불러왔습니다' })
          }}
        >
          중립
        </Button>
      </Row>
      <Row label="skeleton">
        <div className="flex w-full max-w-[360px] flex-col gap-2">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-5/6" />
        </div>
      </Row>
      <Row label="kbd">
        <span className="flex items-center gap-1 text-[13px] text-text-muted">
          <Kbd>⌘</Kbd>
          <Kbd>K</Kbd>
          <span className="ml-1">검색</span>
        </span>
        <span className="flex items-center gap-1 text-[13px] text-text-muted">
          <Kbd>⌘</Kbd>
          <Kbd>V</Kbd>
          <span className="ml-1">붙여넣어 올리기</span>
        </span>
      </Row>
    </Section>
  )
}

function SidebarDemo() {
  return (
    <Section id="sidebar" title="사이드바">
      <div className="w-[232px] rounded-md border border-border bg-bg-subtle px-2.5 pb-3">
        <SidebarSection title="보드">
          <SidebarItem href="#sidebar" icon={LayoutGrid} active count={12}>
            2026 4분기 매크로
          </SidebarItem>
          <SidebarItem href="#sidebar" icon={LayoutGrid} count={7}>
            반도체 업황
          </SidebarItem>
          <SidebarItem href="#sidebar" icon={LayoutGrid} count={3}>
            환율 메모
          </SidebarItem>
        </SidebarSection>
        <SidebarSection title="도구">
          <SidebarItem href="#sidebar" icon={FileText}>
            PDF 내보내기
          </SidebarItem>
          <SidebarItem href="#sidebar" icon={BookOpen}>
            가이드
          </SidebarItem>
        </SidebarSection>
      </div>
    </Section>
  )
}

function CardSection() {
  return (
    <Section
      id="card"
      title="카드"
      lead="스크린샷 한 장 = 카드 한 장. 내부는 상자 대신 구분선으로 나눕니다."
    >
      <div className="grid grid-cols-2 items-start gap-5">
        <ChartCard
          card={SAMPLE_CARD}
          actions={
            <>
              <IconButton icon={Copy} label="복사" size="sm" />
              <IconButton icon={MoreHorizontal} label="더 보기" size="sm" />
            </>
          }
        />
        <ChartCardSkeleton />
      </div>
    </Section>
  )
}
