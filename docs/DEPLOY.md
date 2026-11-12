# Deploy

운영 환경은 Oracle Cloud Always Free Micro VM 한 대다. `main`에 push하면 GitHub Actions가 검사 → 이미지 빌드(GHCR) → VM 배포까지 진행한다. 구조는 `docs/ARCHITECTURE.md`를 본다.

## 1. 최초 서버 준비 (VM 새로 만들 때만)

1. Compute → Create instance: `VM.Standard.E2.1.Micro`(Always Free), Ubuntu, SSH 키 등록. 공인 IPv4를 할당한다.
2. 기존 VCN을 쓰거나, Security List에서 TCP 80/443을 연다.
3. VM 안에서 아래를 실행한다.
   ```bash
   sudo iptables -I INPUT 1 -p tcp -m multiport --dports 80,443 -m conntrack --ctstate NEW -j ACCEPT
   sudo netfilter-persistent save
   curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker ubuntu   # 다시 로그인
   sudo apt-get install -y docker-compose-v2 || sudo apt-get install -y docker-compose-plugin
   sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile \
     && sudo swapon /swapfile && echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   mkdir -p ~/finchart
   ```
4. DuckDNS의 `finchart-notes` 도메인 IP를 새 VM IP로 바꾼다.
5. GitHub repo Secrets: `VM_HOST`(IP), `VM_SSH_KEY`(개인키 전체)
6. 백업 권한: Dynamic Group `finchart-vm`의 규칙에 새 instance OCID를 넣는다(Policy `finchart-backup-policy`는 그대로 둔다).

## 2. 환경변수 (`~/finchart/.env`, 권한 600)

```bash
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash-lite
ANTHROPIC_API_KEY=...             # 뉴스 PDF 번역 (유료). 비우면 뉴스 업로드가 꺼진다
TELEGRAM_BOT_TOKEN=...            # BotFather
TELEGRAM_BOT_USERNAME=FinchartNoteBot
TELEGRAM_WEBHOOK_SECRET=...       # python3 -c "import secrets;print(secrets.token_urlsafe(32))"
```

- 바꾼 뒤에는 `cd ~/finchart && docker compose up -d`를 실행한다(변경된 컨테이너만 다시 만든다).
- 전체 목록은 `.env.example`과 `docs/ARCHITECTURE.md`에 있다. 실제 값은 절대 커밋하지 않는다.

## 3. 배포

- `main`에 push → Actions `Deploy` 워크플로가 실행된다(약 3~5분).
- 수동으로 다시 돌리려면 Actions 탭에서 `Deploy` → Run workflow를 누른다.
- 확인: `curl https://finchart-notes.duckdns.org/api/health` → `{"status":"ok","last_backup":...}`

## 4. 텔레그램 웹훅 등록

웹훅 URL은 `https://finchart-notes.duckdns.org/api/telegram/webhook`이다. 토큰이나 시크릿을 바꾸면 다시 등록한다.

```bash
# 로컬에서 (VM .env와 같은 토큰/시크릿을 환경변수로 넘긴다)
TELEGRAM_BOT_TOKEN=... TELEGRAM_WEBHOOK_SECRET=... \
PUBLIC_BASE_URL=https://finchart-notes.duckdns.org \
  python3 scripts/set_webhook.py set

# 또는 VM에서 (VM .env의 시크릿을 그대로 사용, Python 3.8 이상)
scp -i <키> scripts/set_webhook.py ubuntu@<VM_IP>:/tmp/ && \
  ssh -i <키> ubuntu@<VM_IP> 'python3 /tmp/set_webhook.py set --env-file ~/finchart/.env'

python3 scripts/set_webhook.py info --env-file apps/api/.env    # 상태와 마지막 오류 확인
python3 scripts/set_webhook.py delete --env-file apps/api/.env  # 해제
```

- `setWebhook`에는 `secret_token`과 `allowed_updates=["message", "callback_query"]`를 넣는다. 서버는 헤더가 다르면 403을 반환한다.
- `info`의 `pending_update_count`와 `last_error_message`로 전달 실패를 확인한다.

### 로컬 개발 (공개 URL 없이)

`apps/api/.env`에 `TELEGRAM_MODE=polling`을 넣고 `uv run finchart-api`를 실행한다. 시작할 때 웹훅을 해제하고 `getUpdates` 롱 폴링으로 메시지를 받는다. 테스트가 끝나면 위의 `set`으로 운영 웹훅을 다시 등록한다. 웹훅이 있으면 폴링이 막히고, 폴링을 시작하면 웹훅이 해제되기 때문이다.

### 재전송과 재시작에 대한 안전성

- 이 VM은 잠들지 않는다(Render 같은 콜드스타트 없음). 다만 배포나 재시작으로 앱이 잠깐 내려가면, Telegram은 응답을 받을 때까지 같은 업데이트를 다시 보낸다.
- 웹훅은 시크릿만 확인하고 바로 `200`을 반환한다. 그다음 백그라운드에서 처리하고, `update_id`를 먼저 기록해 같은 업데이트를 두 번 처리하지 않는다.
- 같은 이미지가 다른 `update_id`로 다시 와도 SHA-256 중복 확인으로 분석을 다시 하지 않는다.
- 알려진 한계: `200`을 반환한 뒤 분석 도중에 앱이 재시작되면, 그 업데이트는 Telegram이 다시 보내지 않는다. 사용자는 "분석 중…" 메시지만 받게 되므로 이미지를 다시 보내면 된다.

## 5. 백업과 복구

매일 04:00 KST에 자동으로 실행된다. 수동 백업과 복구 방법은 `docs/ARCHITECTURE.md`의 "백업과 복구"를 본다.
