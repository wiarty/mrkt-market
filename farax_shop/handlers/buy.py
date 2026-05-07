"""Star purchase flow."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from .. import texts
from ..cryptobot import CryptoBotClient, CryptoBotError
from ..database import Database
from ..keyboards import (
    back_to_menu_kb,
    buy_amount_kb,
    buy_currency_kb,
    cancel_input_kb,
    invoice_kb,
)
from ..states import BuyStates

router = Router(name="buy")
log = logging.getLogger(__name__)


async def _get_prices(db: Database) -> tuple[float, float, int]:
    settings = await db.all_settings()
    rub = float(settings.get("price_rub", "1.5") or "1.5")
    usdt = float(settings.get("price_usdt", "0.015") or "0.015")
    min_stars = int(settings.get("min_stars", "50") or "50")
    return rub, usdt, min_stars


@router.callback_query(F.data == "buy")
async def on_buy(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await state.clear()
    rub, usdt, min_stars = await _get_prices(db)
    await callback.message.edit_text(
        texts.buy_select_amount(rub, usdt, min_stars),
        reply_markup=buy_amount_kb(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy_amount:"))
async def on_amount(callback: CallbackQuery, db: Database) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return
    try:
        stars = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректное количество", show_alert=True)
        return
    rub, usdt, min_stars = await _get_prices(db)
    if stars < min_stars:
        await callback.answer(
            f"Минимум {min_stars} звёзд", show_alert=True
        )
        return
    await callback.message.edit_text(
        texts.buy_select_currency(stars, stars * rub, stars * usdt),
        reply_markup=buy_currency_kb(stars),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "buy_custom")
async def on_buy_custom(
    callback: CallbackQuery, state: FSMContext, db: Database
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    _rub, _usdt, min_stars = await _get_prices(db)
    await state.set_state(BuyStates.waiting_for_amount)
    await callback.message.answer(
        texts.buy_custom_prompt(min_stars),
        reply_markup=cancel_input_kb(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.message(BuyStates.waiting_for_amount, F.text.lower() == "отмена")
async def cancel_custom(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        texts.cancelled(),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.HTML,
    )
    await message.answer(
        "Возвращаемся в меню.", reply_markup=back_to_menu_kb()
    )


@router.message(BuyStates.waiting_for_amount)
async def on_custom_amount(
    message: Message, state: FSMContext, db: Database
) -> None:
    if not message.text:
        await message.answer("Отправь количество звёзд числом.")
        return
    try:
        stars = int(message.text.strip())
    except ValueError:
        await message.answer("Это не число. Попробуй ещё раз.")
        return
    rub, usdt, min_stars = await _get_prices(db)
    if stars < min_stars:
        await message.answer(
            f"Минимум — {min_stars} звёзд."
        )
        return
    if stars > 1_000_000:
        await message.answer("Слишком большое число.")
        return
    await state.clear()
    await message.answer(
        "Готово.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        texts.buy_select_currency(stars, stars * rub, stars * usdt),
        reply_markup=buy_currency_kb(stars),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data.startswith("buy_pay:"))
async def on_buy_pay(
    callback: CallbackQuery,
    db: Database,
    cryptobot: CryptoBotClient,
) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return
    user = callback.from_user
    if user is None:
        await callback.answer()
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Некорректные данные", show_alert=True)
        return
    try:
        stars = int(parts[1])
    except ValueError:
        await callback.answer("Некорректное количество", show_alert=True)
        return
    currency = parts[2].upper()
    if currency not in ("RUB", "USDT"):
        await callback.answer("Неподдерживаемая валюта", show_alert=True)
        return

    rub, usdt, min_stars = await _get_prices(db)
    if stars < min_stars:
        await callback.answer(
            f"Минимум {min_stars} звёзд", show_alert=True
        )
        return

    amount = stars * rub if currency == "RUB" else stars * usdt
    description = f"FaraxShop: {stars} Telegram Stars"

    if not cryptobot.token:
        await callback.answer(
            "Платежи временно недоступны. Свяжись с поддержкой.",
            show_alert=True,
        )
        return

    try:
        if currency == "USDT":
            invoice = await cryptobot.create_invoice(
                amount=amount,
                currency_type="crypto",
                asset="USDT",
                description=description,
                payload=f"user={user.id}|stars={stars}",
            )
        else:
            invoice = await cryptobot.create_invoice(
                amount=amount,
                currency_type="fiat",
                fiat="RUB",
                description=description,
                payload=f"user={user.id}|stars={stars}",
            )
    except CryptoBotError as exc:
        log.exception("CryptoBot create_invoice failed")
        await callback.answer(
            f"Ошибка создания счёта: {exc}", show_alert=True
        )
        return

    order_id = await db.create_order(
        user_id=user.id,
        stars_amount=stars,
        currency=currency,
        price_amount=amount,
        invoice_id=str(invoice.invoice_id),
        invoice_url=invoice.pay_url,
    )

    await callback.message.edit_text(
        texts.invoice_created(stars, currency, amount, order_id),
        reply_markup=invoice_kb(invoice.pay_url, order_id),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()
