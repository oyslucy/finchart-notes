# Architecture

금융 차트 스크린샷을 올리면 VLM이 메인 차트 영역(bbox)과 해설을 돌려주고, 서버가 그 영역만 크롭해 카드로 저장한다. 카드는 보드 단위로 쌓이고 브라우저에서 PDF로 내보낸다.

## 구성도

```
브라우저 (React SPA)
  │  Supabase Auth (Google / 이메일 매직링크) → access token(JWT)
  │
  │  https://finchart-notes.duckdns.org
  ▼
Oracle Cloud Always Free VM (VM.Standard.E2.1.Micro, RAM 1 GB)
  └ docker compose
     ├ caddy   : 80/443, Let's Encrypt 자동 HTTPS → app:8000
     └ app     : FastAPI (uvicorn, worker 1)
                  ├ /api/*  JSON API
                  └ /*      web 정적 빌드 (SPA fallback)
                     │
                     ├──▶ Gemini API (VLM, 무료 티어)
                     └──▶ Supabase (사용자 JWT를 그대로 전달 → RLS 적용)
                            ├ Postgres : boards, cards
                            └ Storage  : charts 버킷 (비공개)
```

- 프론트와 API는 같은 도메인을 쓴다(CORS 없음). 별도 프론트 호스팅(Cloudflare Pages)은 쓰지 않는다.
- HF Spaces Docker는 2026-11 기준 유료 플랜이 필요해서 쓰지 않는다(`docs/FREE_TIER.md`).
- API는 Supabase를 **사용자 JWT로** 호출한다. service role 키를 쓰지 않으므로 RLS가 항상 마지막 방어선이 된다.
- PDF는 브라우저에서 인쇄용 CSS로 만든다. 서버 렌더러(WeasyPrint 등)는 1 GB VM에서 쓰지 않는다.

## 요청 흐름: 카드 생성

`POST /api/boards/{board_id}/cards` (multipart `image`)

1. **인증**: `Authorization: Bearer <jwt>`를 Supabase JWKS로 검증한다. 이메일이 `ALLOWED_EMAILS`에 없으면 403.
2. **제한**: 사용자별 분당 호출 수(메모리 기반)를 확인한다. 파일은 10 MB 이하, `image/png|jpeg|webp`만 받는다.
3. **해시 확인**: 원본 바이트의 SHA-256을 계산하고 `(owner_id, image_sha256)`로 기존 카드를 찾는다. 있으면 **분석을 생략**하고 기존 카드를 `duplicate: true`로 반환한다.
4. **VLM 분석**: `VisionProvider.analyze(image_bytes)` → `ChartAnalysis`(bbox, title, chart_type, period, takeaways, interpretation, caveats). Gemini가 429나 5xx를 반환하면 지수 백오프로 최대 3회 재시도하고, 그래도 실패하면 폴백 모델을 쓴다.
5. **크롭**: 0~1000으로 정규화된 bbox를 픽셀로 바꿔 크롭한다. 너무 작거나 원본의 90% 이상이면 크롭을 거절하고 원본 전체를 쓴다. EXIF는 제거하고 WebP로 인코딩하며, 썸네일(긴 변 480px)도 만든다.
6. **저장**: Storage `charts/{owner_id}/{sha256}.webp`와 `..._thumb.webp`에 올리고, `cards`에 행을 추가한다(position은 보드의 마지막 다음 번호).
7. **응답**: 카드 JSON과 이미지 서명 URL(1시간 유효)을 반환한다.

```
upload ─▶ auth ─▶ limits ─▶ sha256 ─┬─ hit ─▶ 기존 카드 반환
                                     └─ miss ─▶ VLM ─▶ crop ─▶ storage ─▶ insert ─▶ 카드 반환
```

## 코드 구조

```
apps/api/src/finchart_api/
  config.py          설정 (pydantic-settings)
  main.py            create_app(): 의존성 조립, 라우터 등록, SPA 마운트
  domain/            프레임워크 무관한 순수 로직
    analysis.py      ChartAnalysis 스키마
    pipeline.py      카드 생성 유스케이스 (해시 → 분석 → 크롭 → 저장)
    ports.py         저장소/스토리지 프로토콜
  imaging.py         해시, bbox 변환, 크롭 검증, 썸네일, EXIF 제거
  llm/
    base.py          VisionProvider 프로토콜
    prompt.py        프롬프트와 규칙
    gemini.py        google-genai provider (재시도와 폴백)
    claude_cli.py    로컬 개발 전용 provider (LLM_PROVIDER=claude_cli일 때만 import)
    factory.py       설정에 따라 provider 선택
  infra/supabase.py  PostgREST와 Storage를 httpx로 호출하는 어댑터
  http/              FastAPI 라우터, 인증 의존성, 레이트 리밋, SPA
apps/web/            React + Vite + TS + Tailwind v4 + Motion + TanStack Query + React Router
supabase/migrations/ SQL 마이그레이션 (테이블, 인덱스, RLS, Storage 정책)
deploy/              compose.yml, Caddyfile (VM의 ~/finchart로 복사됨)
```

## 데이터 모델

```sql
boards (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid not null default auth.uid() references auth.users on delete cascade,
  title       text not null,
  created_at  timestamptz not null default now()
)

cards (
  id              uuid primary key default gen_random_uuid(),
  board_id        uuid not null references boards on delete cascade,
  owner_id        uuid not null default auth.uid() references auth.users on delete cascade,
  position        integer not null,
  image_path      text not null,
  thumb_path      text not null,
  image_sha256    text not null,
  title           text not null,
  chart_type      text not null,
  period          text,
  takeaways       jsonb not null default '[]',
  interpretation  text not null,
  caveats         jsonb not null default '[]',
  user_note       text,
  model           text not null,
  raw_response    jsonb,
  created_at      timestamptz not null default now(),
  unique (owner_id, image_sha256)
)
```

- `cards.owner_id`는 원래 명세에는 없지만 추가했다. `(owner_id, image_sha256)` 유니크 제약은 cards 테이블 안의 컬럼으로만 걸 수 있기 때문이다. 이 값이 보드 소유자와 같아야 한다는 조건은 RLS가 강제한다.
- 인덱스: `cards (board_id, position)`, `boards (owner_id, created_at desc)`

## RLS 정책 (본인 데이터만)

| 테이블 | 동작 | 조건 |
|---|---|---|
| boards | select/insert/update/delete | `owner_id = auth.uid()` |
| cards | select/update/delete | `owner_id = auth.uid()` |
| cards | insert | `owner_id = auth.uid()` 이고, `board_id`가 본인 보드 |
| cards | update | 다른 사람 보드로 옮길 수 없음(with check에서 보드 소유 확인) |
| storage.objects (charts) | select/insert/update/delete | `bucket_id = 'charts'` 이고, 경로의 첫 폴더가 `auth.uid()::text` |

- 모든 정책은 `to authenticated`로만 연다. anon은 아무것도 할 수 없다.
- `charts` 버킷은 비공개다. 이미지는 API가 사용자 JWT로 발급한 서명 URL로만 내려준다.

## API

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/health` | 상태 확인 (인증 없음) |
| POST | `/api/boards` | 보드 생성 |
| GET | `/api/boards` | 내 보드 목록 |
| PATCH | `/api/boards/{id}` | 제목 수정 |
| DELETE | `/api/boards/{id}` | 보드 삭제 (카드 포함) |
| POST | `/api/boards/{id}/cards` | 이미지 업로드 → 카드 생성 |
| GET | `/api/boards/{id}/cards` | 카드 목록 (position 순, 서명 URL 포함) |
| PUT | `/api/boards/{id}/order` | 카드 순서 변경 (`card_ids` 배열) |
| PATCH | `/api/cards/{id}` | 텍스트와 메모 수정 |
| DELETE | `/api/cards/{id}` | 카드 삭제 (스토리지 파일 포함) |

## 환경변수

### API (VM `~/finchart/.env`, 로컬 `apps/api/.env`)

| 이름 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `APP_ENV` | | `development` | `production`이면 로컬 전용 provider를 막는다 |
| `LLM_PROVIDER` | | `gemini` | `gemini` 또는 `claude_cli`(로컬 전용) |
| `GEMINI_API_KEY` | O | | AI Studio에서 발급 |
| `GEMINI_MODEL` | | `gemini-3.5-flash-lite` | 기본 모델 |
| `GEMINI_FALLBACK_MODEL` | | `gemini-3.1-flash-lite` | 재시도 후 폴백 |
| `SUPABASE_URL` | O | | `https://<ref>.supabase.co` |
| `SUPABASE_ANON_KEY` | O | | PostgREST/Storage 호출 시 `apikey` 헤더 (공개 키) |
| `ALLOWED_EMAILS` | O | | 쉼표로 구분한 허용 이메일 |
| `RATE_LIMIT_PER_MINUTE` | | `10` | 사용자별 분당 카드 생성 수 |
| `MAX_UPLOAD_BYTES` | | `10485760` | 10 MB |
| `WEB_DIST_DIR` | | | 웹 빌드 경로 (Docker 이미지에서는 `/app/web`) |

### Web (빌드 시점, Vite)

| 이름 | 설명 |
|---|---|
| `VITE_SUPABASE_URL` | Supabase 프로젝트 URL |
| `VITE_SUPABASE_ANON_KEY` | anon 키 (공개 키라 번들에 들어가도 된다. 접근 제어는 RLS가 한다) |

배포 빌드에서는 GitHub repo **Variables**(Secrets가 아님)로 넣는다.

## 배포

- `main`에 push → `ci.yml`(api: ruff/mypy/pytest, web: eslint/prettier/build) → 이미지를 빌드해 GHCR에 push → compose 파일을 VM으로 복사 → SSH로 `docker compose pull && up -d`
- VM에서는 빌드하지 않는다(RAM 1 GB).
- Supabase 마이그레이션은 Supabase CLI(`supabase db push`)나 SQL Editor로 적용한다.

| 대상 | 역할 | 무료 조건 |
|---|---|---|
| Oracle Cloud Always Free (Micro) | app + caddy | 1/8 OCPU, 1 GB, 트래픽 월 10 TB |
| DuckDNS | 도메인 | 무료 |
| Supabase Free | Postgres, Storage, Auth | DB 500 MB, Storage 1 GB, 7일 비활성 시 정지 |
| Gemini API Free | VLM | 모델별 RPD 제한 (AI Studio에서 확인) |
| GitHub Actions / GHCR | CI, 이미지 저장소 | 공개 repo 무료 |
