#!/usr/bin/env python3
"""Registers, inspects or removes the Telegram webhook. Standard library only.

Usage (reads TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, PUBLIC_BASE_URL from the
environment or from an .env file given with --env-file):

    python3 scripts/set_webhook.py set   [--env-file apps/api/.env]
    python3 scripts/set_webhook.py info  [--env-file ...]
    python3 scripts/set_webhook.py delete [--env-file ...]
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

WEBHOOK_PATH = "/api/telegram/webhook"
DEFAULT_BASE_URL = "https://finchart-notes.duckdns.org"


def load_env_file(path: Path) -> None:
    for line in path.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip())


def call(token: str, method: str, params: dict[str, object]) -> dict[str, object]:
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(params).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body: dict[str, object] = json.load(response)
    except urllib.error.HTTPError as exc:
        # The URL contains the token, so print only Telegram's description.
        body = json.load(exc)
    return body


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("action", choices=["set", "info", "delete"])
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    if args.env_file:
        load_env_file(args.env_file)

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        sys.exit("TELEGRAM_BOT_TOKEN is not set")

    if args.action == "set":
        secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
        if len(secret) < 16:
            sys.exit("TELEGRAM_WEBHOOK_SECRET must be at least 16 characters")
        base = os.environ.get("PUBLIC_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        result = call(
            token,
            "setWebhook",
            {
                "url": base + WEBHOOK_PATH,
                "secret_token": secret,
                "allowed_updates": ["message", "callback_query"],
                "max_connections": 5,
            },
        )
    elif args.action == "info":
        result = call(token, "getWebhookInfo", {})
    else:
        result = call(token, "deleteWebhook", {"drop_pending_updates": False})

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
