"""Background task that polls CryptoBot for paid invoices."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from .config import Config
from .cryptobot import CryptoBotClient, CryptoBotError
from .database import Database
from .handlers.payment import confirm_paid

log = logging.getLogger(__name__)


async def poll_invoices(
    bot: Bot, config: Config, db: Database, cryptobot: CryptoBotClient
) -> None:
    """Periodically check pending orders and mark paid ones."""
    while True:
        try:
            pending = await db.list_pending_orders()
            for order in pending:
                if not order.invoice_id:
                    continue
                try:
                    invoice = await cryptobot.get_invoice(int(order.invoice_id))
                except CryptoBotError as exc:
                    log.debug("Invoice check failed for %s: %s", order.id, exc)
                    continue
                except Exception as exc:
                    log.warning("Invoice check error for %s: %s", order.id, exc)
                    continue
                if invoice and invoice.status == "paid":
                    try:
                        await confirm_paid(bot, config, db, order.id)
                    except Exception as exc:
                        log.exception("confirm_paid failed for %s: %s", order.id, exc)
        except Exception as exc:
            log.exception("Invoice poller crashed: %s", exc)
        await asyncio.sleep(max(5, config.invoice_poll_interval))
