"""Manual payment-status checks and order cancellation by user."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery

from .. import texts
from ..config import Config
from ..cryptobot import CryptoBotClient, CryptoBotError
from ..database import Database
from ..keyboards import admin_order_kb, back_to_menu_kb

router = Router(name="payment")
log = logging.getLogger(__name__)


async def notify_admins_paid(
    bot: Bot,
    config: Config,
    db: Database,
    order_id: int,
) -> None:
    order = await db.get_order(order_id)
    if order is None:
        return
    user_row = await db.get_user(order.user_id)
    text = texts.admin_new_order_alert(
        order_id=order.id,
        user_id=order.user_id,
        username=user_row.username if user_row else None,
        stars=order.stars_amount,
        currency=order.currency,
        amount=order.price_amount,
    )
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                text,
                reply_markup=admin_order_kb(order.id),
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            log.warning("Cannot notify admin %s: %s", admin_id, exc)


async def confirm_paid(
    bot: Bot,
    config: Config,
    db: Database,
    order_id: int,
) -> bool:
    """Mark order as paid (idempotent). Returns True on first transition."""
    order = await db.get_order(order_id)
    if order is None or order.status != "pending":
        return False
    await db.update_order_status(order_id, "paid", paid=True)
    await db.add_purchase_stats(
        order.user_id, order.stars_amount, order.currency, order.price_amount
    )
    try:
        await bot.send_message(
            order.user_id,
            texts.order_paid(order.stars_amount, order.id),
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        log.warning("Cannot notify user %s: %s", order.user_id, exc)
    await notify_admins_paid(bot, config, db, order_id)
    return True


@router.callback_query(F.data.startswith("check:"))
async def on_check_payment(
    callback: CallbackQuery,
    bot: Bot,
    config: Config,
    db: Database,
    cryptobot: CryptoBotClient,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    try:
        order_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный заказ", show_alert=True)
        return

    order = await db.get_order(order_id)
    if order is None:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    if callback.from_user is None or order.user_id != callback.from_user.id:
        await callback.answer("Это не твой заказ", show_alert=True)
        return

    if order.status == "paid" or order.status == "completed":
        await callback.message.edit_text(
            texts.order_paid(order.stars_amount, order.id),
            reply_markup=back_to_menu_kb(),
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return
    if order.status == "cancelled":
        await callback.message.edit_text(
            texts.order_cancelled(order.id),
            reply_markup=back_to_menu_kb(),
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    if not order.invoice_id:
        await callback.answer("Счёт не найден", show_alert=True)
        return

    try:
        invoice = await cryptobot.get_invoice(int(order.invoice_id))
    except CryptoBotError as exc:
        log.warning("CryptoBot get_invoice failed: %s", exc)
        await callback.answer(
            "Не удалось проверить оплату, попробуй позже.", show_alert=True
        )
        return

    if invoice and invoice.status == "paid":
        if await confirm_paid(bot, config, db, order_id):
            await callback.message.edit_text(
                texts.order_paid(order.stars_amount, order.id),
                reply_markup=back_to_menu_kb(),
                parse_mode=ParseMode.HTML,
            )
        await callback.answer("Оплата получена!")
        return

    await callback.answer("Оплата ещё не поступила.", show_alert=True)


@router.callback_query(F.data.startswith("cancel:"))
async def on_cancel(
    callback: CallbackQuery,
    db: Database,
    cryptobot: CryptoBotClient,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    try:
        order_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer()
        return
    order = await db.get_order(order_id)
    if order is None or callback.from_user is None:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    if order.user_id != callback.from_user.id:
        await callback.answer("Это не твой заказ", show_alert=True)
        return
    if order.status != "pending":
        await callback.answer("Заказ уже не активен", show_alert=True)
        return

    await db.update_order_status(order_id, "cancelled")
    if order.invoice_id:
        try:
            await cryptobot.delete_invoice(int(order.invoice_id))
        except CryptoBotError:
            pass
    await callback.message.edit_text(
        texts.order_cancelled(order_id),
        reply_markup=back_to_menu_kb(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()
