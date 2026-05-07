"""FaraxShop bot entry point."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is optional
    load_dotenv = None  # type: ignore[assignment]

from .config import Config, load_config
from .cryptobot import CryptoBotClient
from .database import Database
from .handlers import build_router
from .poller import poll_invoices


async def _run(config: Config) -> None:
    db = Database(config.db_path)
    await db.init()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    cryptobot = CryptoBotClient(
        token=config.cryptobot_token, base_url=config.cryptobot_base_url
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp["db"] = db
    dp["config"] = config
    dp["cryptobot"] = cryptobot

    dp.include_router(build_router())

    poll_task: asyncio.Task | None = None
    if config.cryptobot_token:
        poll_task = asyncio.create_task(poll_invoices(bot, config, db, cryptobot))

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        if poll_task is not None:
            poll_task.cancel()
            try:
                await poll_task
            except (asyncio.CancelledError, Exception):
                pass
        await bot.session.close()


def main() -> None:
    if load_dotenv is not None:
        load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    config = load_config()
    asyncio.run(_run(config))


if __name__ == "__main__":
    main()
