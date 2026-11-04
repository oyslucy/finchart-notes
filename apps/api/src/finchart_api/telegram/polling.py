"""Long-polling loop for local development, where Telegram cannot reach a webhook."""

import asyncio
import logging

from finchart_api.infra.telegram_api import HttpTelegramClient, TelegramApiError
from finchart_api.telegram.bot import TelegramBot

log = logging.getLogger("finchart.telegram")
POLL_TIMEOUT_S = 25


async def run_polling(bot: TelegramBot, client: HttpTelegramClient) -> None:
    # A registered webhook blocks getUpdates, so polling mode removes it first.
    await client.call("deleteWebhook", drop_pending_updates=False)
    offset: int | None = None
    log.info("telegram polling started")
    while True:
        try:
            updates = await client.get_updates(offset, POLL_TIMEOUT_S)
        except TelegramApiError as exc:
            log.warning("getUpdates failed: %s", exc)
            await asyncio.sleep(5)
            continue
        for update in updates:
            offset = int(update["update_id"]) + 1
            await bot.process_update(update)
