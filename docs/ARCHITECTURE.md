# Architecture

금융 차트 스크린샷을 올리면 VLM이 메인 차트 영역(bbox)과 해설을 돌려주고, 서버가 그 영역만 크롭해 카드로 저장한다. 카드는 보드 단위로 쌓이고, 브라우저에서 PDF로 내보낸다.

## 구성도

```
브라우저 (React SPA)
  │  https://finchart-notes.duckdns.org  (세션: httpOnly 쿠키)
  ▼
Oracle Cloud Always Free VM (VM.Standard.E2.1.Micro, RAM 1 GB)
  └ docker compose
     ├ caddy   : 80/443, Let's Encrypt 자동 HTTPS → app:8000
     ├ app     : FastAPI (uvicorn, worker 1)
     │            ├ /api/*  JSON API, 로그인, 이미지 제공
     │            └ /*      web 정적 빌드 (SPA fallback)
     └ backup  : 같은 이미지. 매일 04:00 KST에 /data를 압축해 업로드
                    │
       volume app_data:/data ── finchart.db (SQLite), images/<user_id>/*.webp
                    │
                    ├──▶ Gemini API (VLM, 무료 티어)
                    ├──▶ Claude API (뉴스 PDF 번역, 유료. 키가 없으면 꺼짐)
                    ├──◀ Telegram Bot API (웹훅 수신, 메시지 전송, 파일 다운로드)
                    └──▶ Oracle Object Storage  finchart-backups 버킷 (7일 보관)
```

- 외부 서비스는 Gemini, Claude API(뉴스 번역, 선택), Oracle(VM, Object Storage)이다. 프론트, API, DB, 이미지, 로그인이 모두 VM 하나 안에 있다.
- 프론트와 API는 같은 도메인을 쓴다. CORS가 없고, 세션 쿠키는 `SameSite=Lax`이며, 상태를 바꾸는 요청은 Origin 검사를 거친다.
- PDF는 브라우저에서 인쇄용 CSS로 만든다(`PrintBoard`). A4 한 장마다 보드 제목, 날짜, 쪽 번호와 카드 2장(차트 왼쪽, 해설 오른쪽)을 넣는다. 1 GB VM에서는 서버 렌더러를 쓰지 않는다.

## 요청 흐름: 카드 생성

`POST /api/boards/{board_id}/cards` (multipart `image`)

1. **인증**: `finchart_session` 쿠키로 세션을 찾는다. 세션이 없으면 401. `ALLOWED_USERNAMES`가 설정돼 있고 아이디가 목록에 없으면 403.
2. **제한**: 사용자별 분당 업로드 수(메모리 기반)와 하루 분석 장수(`analysis_log` 기준, 카드를 지워도 줄지 않음)를 확인한다. 중복 이미지는 분석하지 않으므로 하루 한도에 포함되지 않는다. 파일은 10 MB 이하, `image/png|jpeg|webp`만 받는다(헤더와 실제 바이트를 모두 검사).
3. **해시 확인**: 원본 바이트의 SHA-256으로 `(owner_id, image_sha256)`를 찾는다. 이미 있으면 **분석을 생략**하고 기존 카드를 `duplicate: true`로 반환한다.
4. **VLM 분석**: `VisionProvider.analyze(image_bytes)` → `ChartAnalysis`(bbox, title, chart_type, period, takeaways, interpretation, caveats). Gemini가 429나 5xx를 반환하면 지수 백오프로 최대 3회 재시도하고, 그래도 실패하면 폴백 모델을 쓴다.
5. **크롭**: 0~1000으로 정규화된 bbox를 픽셀로 바꾸고, 축 라벨이 잘리지 않도록 0.8% 여백을 둔다. 크롭 영역이 너무 작거나 원본의 90% 이상이면 원본 전체를 쓴다. EXIF를 제거하고 WebP로 저장하며, 썸네일(긴 변 480px)도 만든다. 카드 한 장은 보통 30~50 KB다.
6. **저장**: `/data/images/{owner_id}/{sha256}.webp`와 `_thumb.webp`에 저장하고, `cards`에 행을 추가한다.
7. **응답**: 카드 JSON을 반환한다. 이미지 URL은 `/api/images/...`이고, 소유자만 받을 수 있다.

## 요청 흐름: 뉴스 PDF 번역

`POST /api/articles` (multipart `pdf`)

1. **검사**: 20 MB 이하, `%PDF-`로 시작하고 암호가 없어야 하며, 30쪽 이하여야 한다. 쪽수는 `pypdf`로 페이지 트리만 읽어 센다(렌더링하지 않는다).
2. **제한**: 사용자별 분당 업로드 수(카드와 공유)와 하루 번역 횟수(`translation_log`, 기본 10회)를 확인한다. 번역은 토큰 단위로 과금되므로 차트 분석과 별도로 센다. 실패한 시도와 다시 시도도 1회로 센다.
3. **저장**: PDF의 SHA-256이 이미 있으면 기존 기사를 `duplicate: true`로 돌려준다. 없으면 `/data/images/{owner_id}/articles/{sha256}.pdf`에 저장하고, `articles`에 `pending` 행을 만든 뒤 `202`를 반환한다.
4. **번역(백그라운드)**: `Translator.translate(pdf)`가 PDF를 Claude API에 문서 블록으로 보낸다. 응답은 JSON 스키마(structured output)로 받는다: 언어, 원제, 한국어 제목, 매체, 발행일, 요약 3줄, 문단 목록(`kind`, `original`, `translated`). 출력이 길어 스트리밍으로 받는다. SDK가 429, 과부하, 5xx를 재시도한다.
5. **결과**: 성공하면 `done`, 실패하면 `failed`와 사유(`too_long`, `unreadable`, `failed`)를 기록한다. 서버가 번역 도중 재시작되면 시작 시 `pending`을 `failed`(`interrupted`)로 바꾼다. 웹은 `pending`인 기사가 있는 동안 목록을 폴링한다.

## 코드 구조

```
apps/api/src/finchart_api/
  config.py            설정 (pydantic-settings)
  main.py              create_app(): DB 마이그레이션, 라우터 등록, SPA 마운트
  domain/              프레임워크와 무관한 순수 로직
    analysis.py        ChartAnalysis 스키마
    pipeline.py        스크린샷 분석 (해시 → VLM → 크롭)
    cards.py           카드 생성/삭제, 보드 삭제 유스케이스
    articles.py        뉴스 PDF 제출/번역/재시도 유스케이스, 번역 스키마, Translator 프로토콜
    ports.py           저장소/스토리지 프로토콜
  imaging.py           해시, bbox 변환, 크롭 검증, 썸네일, EXIF 제거
  pdf.py               PDF 쪽수 확인 (pypdf, 렌더링 없음)
  llm/                 VisionProvider (gemini, 로컬 전용 claude_cli), 프롬프트, claude_api.py (번역)
  infra/
    sqlite.py          스키마, 사용자별로 범위가 정해진 보드/카드 저장소, 파일 스토리지
    accounts.py        계정(argon2 비밀번호 해시)과 세션
  backup.py            백업/복구 (Object Storage, instance principal)
  telegram/            텔레그램 봇 (업데이트 처리, 로컬용 폴링). 카드 생성은 domain/cards.py를 그대로 호출
  infra/telegram_*.py  Bot API 클라이언트, 연결/토큰/업데이트 저장소
  http/                라우터(auth, boards, cards, images, health), 의존성, 레이트 리밋, Origin 검사
apps/web/              React + Vite + TS + Tailwind v4 + Motion + TanStack Query + React Router
deploy/                compose.yml, Caddyfile, restore.sh (VM의 ~/finchart로 복사됨)
```

## 데이터 모델 (SQLite)

```sql
users        (id, username unique, password_hash, created_at)
sessions (token_hash pk, user_id → users, created_at, expires_at)   -- 토큰 원문은 저장하지 않는다
boards   (id, owner_id → users, title, created_at)
cards    (id, board_id → boards, owner_id → users, position, image_path, thumb_path,
          image_sha256, title, chart_type, period, takeaways json, interpretation,
          caveats json, user_note, model, raw_response json, created_at, pinned_at,
          unique (owner_id, image_sha256))
analysis_log (owner_id → users, created_at)   -- 하루 분석 한도 계산용, 카드를 지워도 남는다
telegram_links       (user_id pk → users, telegram_user_id unique, chat_id, telegram_username,
                      default_board_id → boards, created_at)
telegram_link_tokens (token_hash pk, user_id → users, created_at, expires_at, used_at)  -- 해시만 저장
telegram_updates     (update_id pk, received_at)   -- 웹훅 재전송 멱등성, 7일 보관
```

- 모든 보드와 카드 쿼리는 저장소 계층에서 `owner_id = 로그인 사용자`로 범위가 정해진다(`SqliteBoards`, `SqliteCards`). 다른 사람의 리소스는 존재하지 않는 것처럼 404로 응답한다.
- 이미지 경로는 `<owner_id>/`로 시작해야 하고, 경로 조작(`..`)은 거부한다.
- 정렬: 보드에서는 고정 카드(최근에 고정한 순) → `position` 순, 홈에서는 고정 카드 → 최신순으로 정렬한다. 새 카드는 `position` 0으로 들어가고 나머지는 하나씩 밀린다.
- 스키마 변경은 `infra/sqlite.py`의 `_MIGRATIONS`에 한 줄씩 추가한다. 앱이 시작할 때 `pragma user_version`을 보고 필요한 것만 적용한다.
- 외래 키 cascade로 보드를 지우면 카드 행도 함께 지워진다. 이미지 파일은 유스케이스에서 함께 지운다.

## 인증

- 아이디(영문 소문자, 숫자, `_`, 3~20자)와 비밀번호(8~128자)로 가입하고 로그인한다.
- 비밀번호는 argon2id로 해시한다. 없는 아이디로 로그인해도 같은 시간이 걸리도록 더미 해시로 검증한다.
- 세션은 무작위 토큰이고, DB에는 SHA-256 해시만 저장한다. 30일 동안 유효하다. 쿠키는 `HttpOnly`, `SameSite=Lax`, 운영 환경에서는 `Secure`다.
- 기본은 **누구나 가입할 수 있다.** `ALLOWED_USERNAMES`를 설정하면 그 목록에 있는 아이디만 가입하고 로그인할 수 있고, 목록에서 빠지면 기존 세션도 403을 받는다.
- 공개 가입이므로 남용을 막는 장치가 있다: 같은 IP에서 시간당 가입 5회, 계정별 하루 분석 30장(Gemini 무료 한도를 여러 사용자가 나눠 쓰기 때문).
- 로그인 시도는 IP와 아이디 조합별로 분당 10회로 제한한다.
- 비밀번호 재설정 메일은 없다. 잊어버리면 VM에서 계정을 지우고 다시 가입한다.

## API

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/health` | 상태와 마지막 백업 시각 (인증 없음) |
| POST | `/api/auth/signup` | 가입과 동시에 로그인 |
| POST | `/api/auth/login` | 로그인 |
| POST | `/api/auth/logout` | 로그아웃 (세션 삭제) |
| GET | `/api/auth/me` | 현재 사용자 |
| POST / GET | `/api/boards` | 보드 생성 / 내 보드 목록 |
| PATCH / DELETE | `/api/boards/{id}` | 이름 수정 / 삭제 (카드와 이미지 포함) |
| GET | `/api/cards?q=` | 최근 카드 (모든 보드). `q`를 주면 제목, 해설, 핵심 관찰, 주의, 기간, 메모, 보드 이름에서 키워드 검색 |
| POST / GET | `/api/boards/{id}/cards` | 이미지 업로드 → 카드 생성 (맨 앞에 추가) / 카드 목록 (고정 카드 먼저) |
| PUT | `/api/boards/{id}/order` | 카드 순서 변경 (`card_ids` 배열) |
| PATCH / DELETE | `/api/cards/{id}` | 텍스트, 메모, 고정(`pinned`) 수정 / 삭제 |
| POST | `/api/cards/{id}/reanalyze` | 저장된 크롭 이미지로 해설만 다시 받는다. 메모와 이미지는 그대로 두고, 하루 분석 횟수에 포함된다 |
| POST / GET | `/api/articles` | 뉴스 PDF 업로드 → `202` 후 백그라운드 번역 / 기사 목록 (`q`로 검색, 본문 제외) |
| GET / PATCH / DELETE | `/api/articles/{id}` | 기사 (문단별 원문과 번역) / 고정(`pinned`) / 삭제 (PDF 포함). 목록은 고정한 기사가 먼저 |
| POST | `/api/articles/{id}/retry` | 실패한 번역을 다시 시도 (하루 번역 횟수에 포함) |
| GET | `/api/articles/{id}/pdf` | 원본 PDF (소유자만, inline) |
| GET | `/api/articles/quota` | 오늘 번역 횟수 (`/api/quota`와 같은 형태) |
| GET | `/api/quota` | 오늘 분석 횟수 (`limit`, `used`, `remaining`, `resets_at`, 매일 00:00 UTC 초기화) |
| GET | `/api/images/{path}` | 카드 이미지 (소유자만) |
| POST | `/api/telegram/link-token` | 1회용 연결 링크 `https://t.me/<봇>?start=<토큰>` 발급 (10분) |
| GET | `/api/telegram/status` | 연결 여부, 연결된 텔레그램 아이디 |
| DELETE | `/api/telegram/link` | 연결 해제 |
| POST | `/api/telegram/webhook` | Telegram 웹훅. `X-Telegram-Bot-Api-Secret-Token`이 일치해야 한다 |

## 환경변수 (VM `~/finchart/.env`, 로컬 `apps/api/.env`)

| 이름 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `GEMINI_API_KEY` | O | | AI Studio에서 발급 |
| `ALLOWED_USERNAMES` | | (비어 있음 = 누구나) | 설정하면 이 아이디만 가입하고 로그인할 수 있다 (쉼표로 구분) |
| `GEMINI_MODEL` | | `gemini-3.5-flash-lite` | 기본 모델 |
| `GEMINI_FALLBACK_MODEL` | | `gemini-3.1-flash-lite` | 재시도 후 쓰는 폴백 |
| `LLM_PROVIDER` | | `gemini` | `claude_cli`는 로컬 전용 |
| `APP_ENV` | | `development` | compose가 `production`으로 설정한다 (Secure 쿠키, 로컬 provider 차단) |
| `DATA_DIR` | | `data` | compose가 `/data`로 설정한다 |
| `BACKUP_BUCKET` | | `finchart-backups` | Object Storage 버킷 이름 |
| `RATE_LIMIT_PER_MINUTE` | | `10` | 사용자별 분당 업로드 수 |
| `DAILY_ANALYSES_PER_USER` | | `30` | 사용자별 하루 분석 장수 (UTC 자정 기준) |
| `SIGNUPS_PER_IP_PER_HOUR` | | `5` | IP별 시간당 가입 수 |
| `LOGIN_ATTEMPTS_PER_MINUTE` | | `10` | IP와 아이디별 분당 로그인 시도 수 |
| `MAX_UPLOAD_BYTES` | | `10485760` | 10 MB |
| `ANTHROPIC_API_KEY` | | | 뉴스 번역용. 비어 있으면 뉴스 업로드가 503을 반환한다 (유료, 토큰 단위 과금) |
| `TRANSLATE_MODEL` | | `claude-haiku-4-5-20251001` | 번역 모델 |
| `DAILY_TRANSLATIONS_PER_USER` | | `10` | 사용자별 하루 번역 횟수 (UTC 자정 기준) |
| `MAX_PDF_BYTES` | | `20971520` | 20 MB (텔레그램 다운로드 한도와 같다) |
| `MAX_PDF_PAGES` | | `30` | 쪽수 상한 |

| `PUBLIC_BASE_URL` | | `https://finchart-notes.duckdns.org` | 봇이 보내는 카드 링크의 주소 |
| `TELEGRAM_BOT_TOKEN` | | | BotFather 토큰. 비어 있으면 봇 기능이 꺼진다 |
| `TELEGRAM_BOT_USERNAME` | | | 예: `FinchartNoteBot` (연결 링크에 사용) |
| `TELEGRAM_WEBHOOK_SECRET` | | | 웹훅 검증용 무작위 문자열 (16자 이상) |
| `TELEGRAM_MODE` | | `webhook` | `webhook` / `polling`(로컬) / `off` |

웹 빌드에는 환경변수가 필요 없다. 봇 토큰은 서버 설정(SecretStr)으로만 읽고, 웹 번들, API 응답, 로그 어디에도 나오지 않는다. Bot API 오류 메시지에서도 URL(토큰 포함)은 빼고 기록한다.

## 텔레그램 봇

```
웹 설정 → POST /telegram/link-token → t.me/<봇>?start=<토큰> (QR / 링크)
텔레그램 /start <토큰> → 웹훅 → 토큰 검증(해시, 10분, 1회용) → telegram_links 저장
웹 설정은 2초 간격으로 /telegram/status를 폴링해 연결 완료를 감지한다
```

- **웹훅 처리**: 시크릿 헤더를 검증하고 즉시 `200`을 반환한다. 실제 처리는 백그라운드 태스크로 넘긴다.
  1. 개인 채팅만 처리한다.
  2. `update_id`를 `telegram_updates`에 먼저 기록한다. 이미 있으면 Telegram의 재전송이므로 무시한다.
  3. 연결되지 않은 사용자에게는 "웹 설정에서 먼저 연결해주세요"만 보낸다.
  4. 이미지(사진은 가장 큰 크기, 또는 이미지 MIME의 문서)는 "분석 중…"을 먼저 보낸다. 그다음 `getFile`로 내려받아 웹과 같은 `validate_image_upload` → `create_card`(해시 중복 확인 → 분석 → 크롭 → 저장)를 실행하고, 결과(제목, 핵심 3줄, 웹 카드 링크)로 그 메시지를 수정한다.
- **저장 보드**: 캡션의 `#보드이름`(밑줄은 공백으로 바꿈, 없으면 새로 만든다) → 기본 보드 → `Inbox`(없으면 만들고 기본 보드로 지정) 순서로 정한다.
- **명령**: `/board`(목록), `/board 이름`(기본 보드 변경), `/unlink`(연결 해제)
- **제한**: 웹과 같은 `RateLimiter` 인스턴스(사용자별 분당), 하루 분석 한도, 10 MB를 적용한다.
- **멱등성**: `update_id`로 같은 업데이트를 두 번 처리하지 않는다. 같은 이미지를 다시 보내면 SHA-256 중복 확인으로 분석 없이 기존 카드를 돌려준다.

## 백업과 복구

- `backup` 컨테이너가 매일 19:00 UTC(04:00 KST)에 `python -m finchart_api.backup schedule`을 실행한다. 순서는 다음과 같다.
  1. SQLite 온라인 백업 API로 일관된 사본을 만든다(앱을 멈추지 않는다).
  2. 사본과 `images/`를 하나로 압축한다: `finchart-YYYYMMDD-HHMMSS.tar.gz`
  3. Object Storage `finchart-backups`에 업로드하고, 최신 7개만 남긴다.
  4. `/data/.last_backup`에 성공 시각을 기록한다. `/api/health`의 `last_backup`에서 볼 수 있다.
  - 실패하면 1시간 뒤 한 번 더 시도하고, 그래도 실패하면 다음 날 다시 시도한다.
- 인증에는 instance principal을 쓴다. VM에 키를 두지 않는다. 필요한 OCI 설정은 Dynamic Group `finchart-vm`과 Policy `finchart-backup-policy`(버킷 한정 권한)다.
- 수동 명령 (VM의 `~/finchart`에서):
  ```bash
  docker compose run --rm backup python -m finchart_api.backup run    # 지금 백업
  docker compose run --rm backup python -m finchart_api.backup list   # 목록
  ./restore.sh                                                        # 최신 백업으로 복구 (확인 후 진행)
  ./restore.sh finchart-20261104-190000.tar.gz                        # 특정 백업으로 복구
  ```
  복구할 때는 앱을 멈추고, 현재 데이터를 `/data/.pre-restore-<시각>/`으로 옮긴 다음 백업을 풀고 앱을 다시 시작한다.
- **VM이 회수됐을 때**: 새 Micro VM을 만들고 → 서버 준비(Docker, 방화벽, swap) → DuckDNS IP 갱신 → `VM_HOST` Secret 갱신 → 배포 → Dynamic Group 규칙의 instance OCID 갱신 → `./restore.sh` 순서로 진행한다. 잃는 데이터는 최대 하루치다.

## 로컬 실행

```bash
cp .env.example apps/api/.env      # GEMINI_API_KEY 채우기

# API (http://127.0.0.1:8000, 문서: /api/docs). 데이터는 apps/api/data/
cd apps/api && uv sync && uv run finchart-api

# Web (http://localhost:5173, /api는 8000으로 프록시)
cd apps/web && npm install && npm run dev
```

- Gemini 없이 개발하려면 `apps/api/.env`에 `LLM_PROVIDER=claude_cli`를 넣는다. 로컬 CLI의 `-p` 모드로 분석하며, `APP_ENV=production`에서는 거부된다.
- 검사 (CI와 동일):
  ```bash
  cd apps/api && uv run ruff format --check . && uv run ruff check . && uv run mypy src tests && uv run pytest -q
  cd apps/web && npm run lint && npm run build
  ```
- 실제 Gemini 호출 테스트: `cd apps/api && GEMINI_API_KEY=... uv run pytest -m live`
- 디자인 시스템 스크린샷: `cd apps/web && npm run shots` (`docs/DESIGN.md`)

## 배포

- `main`에 push하면 `ci.yml`(api: ruff/mypy/pytest, web: eslint/prettier/build)이 돌고, 이미지를 빌드해 GHCR에 push한다. 그다음 `deploy/`를 VM으로 복사하고 SSH로 `docker compose pull && up -d`를 실행한다.
- VM에서는 빌드하지 않는다(RAM 1 GB).

| 대상 | 역할 | 무료 조건 |
|---|---|---|
| Oracle Cloud Always Free (Micro VM) | app, caddy, backup, SQLite, 이미지 | 1/8 OCPU, 1 GB, 블록 스토리지 200 GB, 트래픽 월 10 TB |
| Oracle Object Storage | 백업 7일치 | 20 GB, 요청 월 5만 회 |
| DuckDNS | 도메인 | 무료 |
| Gemini API Free | VLM | 모델별 RPD 제한 (AI Studio에서 확인) |
| GitHub Actions / GHCR | CI, 이미지 저장소 | 공개 repo 무료 |
