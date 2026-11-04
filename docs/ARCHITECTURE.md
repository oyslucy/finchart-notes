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
                    └──▶ Oracle Object Storage  finchart-backups 버킷 (7일 보관)
```

- 외부 서비스는 Gemini와 Oracle(VM, Object Storage) 두 곳뿐이다. 프론트, API, DB, 이미지, 로그인이 모두 VM 하나 안에 있다.
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

## 코드 구조

```
apps/api/src/finchart_api/
  config.py            설정 (pydantic-settings)
  main.py              create_app(): DB 마이그레이션, 라우터 등록, SPA 마운트
  domain/              프레임워크와 무관한 순수 로직
    analysis.py        ChartAnalysis 스키마
    pipeline.py        스크린샷 분석 (해시 → VLM → 크롭)
    cards.py           카드 생성/삭제, 보드 삭제 유스케이스
    ports.py           저장소/스토리지 프로토콜
  imaging.py           해시, bbox 변환, 크롭 검증, 썸네일, EXIF 제거
  llm/                 VisionProvider (gemini, 로컬 전용 claude_cli), 프롬프트
  infra/
    sqlite.py          스키마, 사용자별로 범위가 정해진 보드/카드 저장소, 파일 스토리지
    accounts.py        계정(argon2 비밀번호 해시)과 세션
  backup.py            백업/복구 (Object Storage, instance principal)
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
| GET | `/api/images/{path}` | 카드 이미지 (소유자만) |

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

웹 빌드에는 환경변수가 필요 없다.

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
