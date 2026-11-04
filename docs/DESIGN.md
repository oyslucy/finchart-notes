# Design system

목표 톤은 세 가지를 섞는 것이다. Notion 문서의 조용함, AlphaSense의 데이터 밀도, Apple의 여백과 타이포그래피. 흰 바탕에 장식을 빼서 차트와 글이 주인공이 되게 한다. 포인트 컬러는 연한 보라 단색 하나만 쓴다. 템플릿 같은 AI 앱의 인상(보라나 인디고 그라데이션, 네온, 유리 효과, 이모지 아이콘, 겹겹이 쌓인 카드)은 만들지 않는다.

모든 토큰과 컴포넌트는 `/design` 라우트에서 한 화면으로 볼 수 있다. `npm run shots`를 실행하면 라이트/다크 스크린샷이 `apps/web/screenshots/`에 저장된다.

## 파일

```
apps/web/src/
  index.css              Tailwind v4, Pretendard, @theme 매핑, base 스타일
  styles/tokens.css      CSS 변수 (원시 스케일 + 의미 토큰, 라이트/다크)
  design/motion.ts       모션 프리셋 (appear, fade, durations)
  design/theme.ts        테마 선호도 (light / dark / system)
  design/cx.ts           className 결합
  components/ui/         Button, IconButton, Input, Textarea, Tooltip, Dialog, Toast,
                         Skeleton, Kbd, SidebarItem, ChartCard, Icon
  pages/DesignPage.tsx   /design 쇼케이스
apps/web/e2e/design.spec.ts   Playwright 스크린샷과 기본 상호작용 검사
```

## 원칙

1. **의미 토큰만 쓴다.** 컴포넌트는 `bg-surface`, `text-text-muted`, `border-border`처럼 의미 토큰을 참조한다. `gray-5`나 hex 값을 직접 쓰지 않는다. 다크 모드는 의미 토큰을 다시 연결하는 것만으로 끝난다.
2. **상자를 겹치지 않는다.** 영역은 1px 헤어라인과 여백으로 나눈다. 카드 안에 또 카드를 넣지 않는다.
3. **그림자는 거의 보이지 않게 한다.** 떠 있는 레이어(다이얼로그, 토스트, 툴팁)에만 `shadow-pop`을 쓴다.
4. **색은 정보에만 쓴다.** 포인트 컬러는 주요 행동 하나와 포커스에만 쓴다. 빨강과 초록은 위험과 성공 상태 표시에만 쓴다.

## 타이포그래피

- 서체: **Pretendard Variable**을 self-host한다. npm `pretendard`의 dynamic subset(woff2 92개, `unicode-range`)을 Vite가 번들에 포함하므로 외부 CDN에 요청하지 않는다. 화면에 쓰인 글자가 속한 조각만 내려받고, `font-display: swap`을 쓴다.
- 폴백: `-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`
- 한글 줄바꿈: `word-break: keep-all`. 단어 중간에서 줄이 바뀌지 않게 한다.
- 숫자: 가격, 기간, 개수 같은 숫자는 `tabular` 유틸리티(`font-variant-numeric: tabular-nums`)로 자릿수를 맞춘다.

| 용도 | 크기 / 굵기 | 행간 | 비고 |
|---|---|---|---|
| Display | 34 / 600 | 1.2 | 자간 -0.01em |
| H1 | 26 / 600 | 1.3 | 자간 -0.01em |
| H2 (섹션) | 20 / 600 | 1.4 | 자간 -0.01em |
| H3 (카드 제목) | 17 / 600 | 1.5 | 자간 -0.01em |
| 본문 | **15 / 400** | **1.6** | 기본 |
| UI 텍스트 (버튼, 입력) | 14 / 500 | | |
| 보조 텍스트 | 13 | 1.55 | `text-text-muted` |
| 캡션, 라벨 | 12 | 1.5 | `text-text-faint` |

## 색

### 원시 스케일

따뜻한 중립 회색 10단계(`--gray-1` ~ `--gray-10`)는 테두리, 사이드바, 보조 텍스트에 쓴다. 페이지 배경(`--bg`)은 라이트 모드에서 **순백(#ffffff)**이다. 포인트는 **연한 보라 하나**(`--violet-*`)뿐이다. `violet-6`(#7266d6)은 흰 글자와 4.58:1 대비를 확보한 값이고, 연한 느낌은 `violet-1/2` 틴트(선택된 칩, 강조 배경)로 낸다.

| 토큰 | 라이트 | 다크 |
|---|---|---|
| gray-1 | `#fbfaf8` | `#151413` |
| gray-2 | `#f5f4f1` | `#1b1a19` |
| gray-3 | `#eeece8` | `#232120` |
| gray-4 | `#e4e1dc` | `#2d2b29` |
| gray-5 | `#d6d2cc` | `#3a3734` |
| gray-6 | `#b9b4ac` | `#524e4a` |
| gray-7 | `#958f87` | `#77726c` |
| gray-8 | `#6f6a63` | `#9c968f` |
| gray-9 | `#47433f` | `#c9c4bd` |
| gray-10 | `#22201e` | `#edeae6` |
| violet-1 (accent-subtle) | `#f4f2fe` | `#211e33` |
| violet-6 (accent) | `#7266d6` | `#b9b0f7` |
| bg | `#ffffff` | `#151413` |

### 의미 토큰

| 토큰 | 용도 |
|---|---|
| `--bg` / `--bg-subtle` / `--bg-muted` | 페이지 배경 / 사이드바 / hover와 선택 배경 |
| `--surface` | 카드, 입력, 다이얼로그 면 |
| `--border` / `--border-strong` | 헤어라인 / hover 시 테두리 |
| `--text` / `--text-secondary` / `--text-muted` / `--text-faint` | 본문 / 긴 해설 / 메타 정보 / 라벨 |
| `--accent` / `--accent-hover` / `--accent-subtle` / `--accent-fg` | 주요 행동 / hover / 옅은 강조 배경 / accent 위 글자 |
| `--danger` / `--danger-subtle` / `--success` | 상태 표시 |
| `--focus-ring` | 포커스 링 (accent 45%) |

테마는 `<html data-theme="light|dark">`로 바뀐다. 첫 페인트 전에 `index.html`의 인라인 스크립트가 저장된 선호도나 `prefers-color-scheme`을 보고 값을 정한다. 그래서 다크 모드에서 흰 화면이 번쩍이지 않는다.

## 형태

- 모서리: `rounded-sm` 6px(툴팁, Kbd, 작은 요소), `rounded-md` 8px(버튼, 입력), `rounded-lg` 10px(카드, 다이얼로그, 토스트)
- 테두리: 항상 1px `--border`. 강조가 필요하면 `--border-strong`을 쓰고, 테두리를 두껍게 하지 않는다.
- 그림자: `shadow-xs`(필요한 경우만), `shadow-pop`(떠 있는 레이어). 투명도는 4~8%다.

## 아이콘

- **Lucide**만 쓴다. `<Icon>` 래퍼가 `strokeWidth={1.5}`와 `nonScalingStroke`를 강제하므로 크기와 상관없이 선이 1.5px로 유지된다.
- 크기는 14, 16(기본), 18, 20 중 하나를 쓴다.
- 아이콘만 있는 버튼은 반드시 `IconButton`을 쓴다. `label`이 aria-label과 툴팁을 겸한다.

## 모션

Motion(`motion/react`)을 쓴다. 프리셋은 `design/motion.ts`에 있다.

| 종류 | 값 |
|---|---|
| 등장 (`appear`) | opacity 0→1, translateY 8px→0, 220ms, `cubic-bezier(0.2, 0, 0, 1)` |
| 페이드 (`fade`) | opacity만, 220ms |
| 상호작용 (hover, active) | CSS transition 150ms 이내, `ease-out` |
| 스프링 (`gentleSpring`) | stiffness 520, damping 40. 튀지 않는 값 |

- 앱 루트에 `<MotionConfig reducedMotion="user">`를 둔다. 사용자가 `prefers-reduced-motion`을 켜면 Motion이 transform을 끄고 opacity 페이드만 남긴다.
- CSS 애니메이션과 transition도 `prefers-reduced-motion`에서 0.01ms로 줄인다(`index.css`).

## 컴포넌트

| 컴포넌트 | 요점 | 접근성 |
|---|---|---|
| `Button` | variant: primary / secondary / ghost / danger. size: sm(28px) / md(34px). `icon` prop | 기본 `type="button"`, disabled 시 포인터 차단 |
| `IconButton` | 28/32px 정사각형, ghost 스타일 | `label` 필수 → `aria-label`과 툴팁. `shortcut`이 있으면 툴팁에 Kbd 표시 |
| `Input`, `Textarea` | label, hint, error 슬롯 | `useId`로 label 연결, `aria-describedby`, error 시 `aria-invalid` |
| `Tooltip` | Radix. 300ms 지연, 반전 색(text 위 bg) | 포커스로도 열림, Esc로 닫힘 |
| `Dialog` | Radix + Motion. 440px, 헤어라인 footer | 포커스 트랩, Esc와 바깥 클릭으로 닫힘, Title/Description 연결 |
| `Toast` | Radix. 우하단, 최대 3개, 4초 | `useToast()`로 호출. 라이브 영역 공지, 스와이프로 닫기 |
| `Skeleton` | `bg-muted` 위에 부드러운 opacity 펄스 | `aria-hidden` |
| `Kbd` | 20px 높이 키캡 | 의미 있는 `<kbd>` |
| `SidebarItem` | 30px 행, 아이콘, 개수(tabular) | 활성 항목에 `aria-current="page"` |
| `ChartCard` | 헤더(제목과 메타) → 이미지 → 핵심 관찰 / 해설 / 주의 / 메모를 구분선으로 나눈다 | 이미지 `alt`는 카드 제목, 로딩 뼈대는 `aria-busy` |

Radix primitive는 동작만 가져다 쓰고, 스타일은 위 토큰으로 직접 입힌다. shadcn 기본 테마는 쓰지 않는다.

## 하지 말 것

- 그라데이션 배경(보라, 인디고 포함), 네온 글로우, 글래스모피즘(`backdrop-blur`로 반투명 패널 만들기). 보라는 단색 포인트로만 쓴다.
- 이모지를 아이콘으로 쓰기
- 카드 안에 카드, 그림자로 깊이 만들기
- 굵기 700 이상 남용, 대문자 남용(작은 섹션 라벨에만 허용)
- 의미 토큰을 거치지 않는 hex나 Tailwind 기본 팔레트(`bg-blue-500` 등)

## 홈 레이아웃

- 첫 화면은 검색 엔진처럼 동작한다. "어떤 차트를 정리할까요?" 아래 업로드 바와 보드 칩을 화면 중앙보다 살짝 위에 둔다.
- 최근 카드는 첫 화면 아래쪽에서 시작하고, 마스크 그라데이션으로 아래로 갈수록 흐려진다.
- 스크롤하면(약 280px까지) 업로드 바가 상단에 붙는 헤더가 되고(아래 헤어라인과 그림자가 점점 진해짐), 목록의 흐림이 사라진다.
- 스크롤에 연동되는 값은 Motion의 `useScroll`/`useTransform`으로 계산한다. `prefers-reduced-motion`이면 목록을 흐리게 하지 않는다.
