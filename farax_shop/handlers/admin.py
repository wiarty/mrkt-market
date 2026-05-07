"""Admin panel: prices, support, channel, stats, orders, broadcast entry."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from .. import texts
from ..config import Config
from ..database import Database
from ..keyboards import (
    admin_back_kb,
    admin_menu_kb,
    admin_order_kb,
    admin_prices_kb,
    cancel_input_kb,
)
from ..states import AdminStates

router = Router(name="admin")
log = logging.getLogger(__name__)


def _is_admin(user_id: int, config: Config) -> bool:
    return user_id in config.admin_ids


@router.message(Command("admin"))
async def open_admin_cmd(
    message: Message, state: FSMContext, config: Config
) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id, config):
        await message.answer(texts.access_denied(), parse_mode=ParseMode.HTML)
        return
    await state.clear()
    await message.answer(
        texts.admin_menu(),
        reply_markup=admin_menu_kb(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == "admin")
async def open_admin_cb(
    callback: CallbackQuery, state: FSMContext, config: Config
) -> None:
    if callback.from_user is None or not _is_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    if callback.message is None:
        await callback.answer()
        return
    await state.clear()
    await callback.message.edit_text(
        texts.admin_menu(),
        reply_markup=admin_menu_kb(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "adm:prices")
async def show_prices(
    callback: CallbackQuery, db: Database, config: Config
) -> None:
    if callback.from_user is None or not _is_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    if callback.message is None:
        await callback.answer()
        return
    settings = await db.all_settings()
    rub = float(settings.get("price_rub", "1.5") or "1.5")
    usdt = float(settings.get("price_usdt", "0.015") or "0.015")
    await callback.message.edit_text(
        texts.admin_prices(rub, usdt),
        reply_markup=admin_prices_kb(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "adm:price_rub")
async def ask_price_rub(
    callback: CallbackQuery, state: FSMContext, config: Config
) -> None:
    if callback.from_user is None or not _is_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_for_rub_price)
    if callback.message is not None:
        await callback.message.answer(
            "Отправь новую цену за 1 звезду в RUB (например 1.5):",
            reply_markup=cancel_input_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "adm:price_usdt")
async def ask_price_usdt(
    callback: CallbackQuery, state: FSMContext, config: Config
) -> None:
    if callback.from_user is None or not _is_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_for_usdt_price)
    if callback.message is not None:
        await callback.message.answer(
            "Отправь новую цену за 1 звезду в USDT (например 0.015):",
            reply_markup=cancel_input_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "adm:min_stars")
async def ask_min_stars(
    callback: CallbackQuery, state: FSMContext, config: Config
) -> None:
    if callback.from_user is None or not _is_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_for_min_stars)
    if callback.message is not None:
        await callback.message.answer(
            "Отправь минимальное количество звёзд для покупки (число):",
            reply_markup=cancel_input_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "adm:support")
async def ask_support(
    callback: CallbackQuery, state: FSMContext, config: Config
) -> None:
    if callback.from_user is None or not _is_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_for_support_username)
    if callback.message is not None:
        await callback.message.answer(
            "Отправь username поддержки без @ (например support):",
            reply_markup=cancel_input_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "adm:channel")
async def ask_channel(
    callback: CallbackQuery, state: FSMContext, config: Config
) -> None:
    if callback.from_user is None or not _is_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_for_channel_link)
    if callback.message is not None:
        await callback.message.answer(
            "Отправь ссылку на канал (https://t.me/...) "
            "или пустое сообщение чтобы убрать:",
            reply_markup=cancel_input_kb(),
        )
    await callback.answer()


# ---------------- value handlers ----------------
async def _cancel_input(message: Message, state: FSMContext) -> bool:
    if message.text and message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer(
            texts.cancelled(),
            reply_markup=ReplyKeyboardRemove(),
            parse_mode=ParseMode.HTML,
        )
        await message.answer(
            texts.admin_menu(),
            reply_markup=admin_menu_kb(),
            parse_mode=ParseMode.HTML,
        )
        return True
    return False


@router.message(AdminStates.waiting_for_rub_price)
async def set_price_rub(message: Message, state: FSMContext, db: Database) -> None:
    if await _cancel_input(message, state):
        return
    if not message.text:
        return
    try:
        value = float(message.text.replace(",", ".").strip())
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Это не похоже на положительное число.")
        return
    await db.set_setting("price_rub", f"{value}")
    await state.clear()
    await message.answer(
        f"Новая цена в RUB: {value}",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        texts.admin_menu(),
        reply_markup=admin_menu_kb(),
        parse_mode=ParseMode.HTML,
    )


@router.message(AdminStates.waiting_for_usdt_price)
async def set_price_usdt(message: Message, state: FSMContext, db: Database) -> None:
    if await _cancel_input(message, state):
        return
    if not message.text:
        return
    try:
        value = float(message.text.replace(",", ".").strip())
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Это не похоже на положительное число.")
        return
    await db.set_setting("price_usdt", f"{value}")
    await state.clear()
    await message.answer(
        f"Новая цена в USDT: {value}",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        texts.admin_menu(),
        reply_markup=admin_menu_kb(),
        parse_mode=ParseMode.HTML,
    )


@router.message(AdminStates.waiting_for_min_stars)
async def set_min_stars(message: Message, state: FSMContext, db: Database) -> None:
    if await _cancel_input(message, state):
        return
    if not message.text:
        return
    try:
        value = int(message.text.strip())
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введи целое положительное число.")
        return
    await db.set_setting("min_stars", str(value))
    await state.clear()
    await message.answer(
        f"Новый минимум: {value} звёзд",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        texts.admin_menu(),
        reply_markup=admin_menu_kb(),
        parse_mode=ParseMode.HTML,
    )


@router.message(AdminStates.waiting_for_support_username)
async def set_support(message: Message, state: FSMContext, db: Database) -> None:
    if await _cancel_input(message, state):
        return
    raw = (message.text or "").strip().lstrip("@")
    await db.set_setting("support_username", raw)
    await state.clear()
    await message.answer(
        f"Поддержка обновлена: @{raw}" if raw else "Поддержка очищена.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        texts.admin_menu(),
        reply_markup=admin_menu_kb(),
        parse_mode=ParseMode.HTML,
    )


@router.message(AdminStates.waiting_for_channel_link)
async def set_channel(message: Message, state: FSMContext, db: Database) -> None:
    if await _cancel_input(message, state):
        return
    raw = (message.text or "").strip()
    if raw and not raw.startswith(("https://t.me/", "http://t.me/", "tg://")):
        await message.answer("Ссылка должна начинаться с https://t.me/")
        return
    await db.set_setting("channel_link", raw)
    await state.clear()
    await message.answer(
        f"Канал обновлён: {raw}" if raw else "Канал очищен.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        texts.admin_menu(),
        reply_markup=admin_menu_kb(),
        parse_mode=ParseMode.HTML,
    )


# ---------------- stats / orders ----------------
@router.callback_query(F.data == "adm:stats")
async def show_stats(
    callback: CallbackQuery, db: Database, config: Config
) -> None:
    if callback.from_user is None or not _is_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    if callback.message is None:
        await callback.answer()
        return
    stats = await db.shop_stats()
    total_users = await db.total_users()
    settings = await db.all_settings()
    text = (
        texts.admin_stats(stats, total_users)
        + "\n\n"
        + texts.admin_settings_overview(settings)
    )
    await callback.message.edit_text(
        text, reply_markup=admin_back_kb(), parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(F.data == "adm:orders")
async def show_orders(
    callback: CallbackQuery, db: Database, config: Config
) -> None:
    if callback.from_user is None or not _is_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    if callback.message is None:
        await callback.answer()
        return
    orders = await db.list_pending_orders()
    if not orders:
        await callback.message.edit_text(
            "Активных pending-заказов нет.",
            reply_markup=admin_back_kb(),
        )
        await callback.answer()
        return
    lines = ["<b>Pending заказы:</b>\n"]
    for o in orders[:30]:
        asset = "₽" if o.currency == "RUB" else "USDT"
        lines.append(
            f"#{o.id} — user <code>{o.user_id}</code> — "
            f"{o.stars_amount}★ — {o.price_amount:.2f} {asset}"
        )
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=admin_back_kb(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:complete:"))
async def complete_order(
    callback: CallbackQuery, bot: Bot, db: Database, config: Config
) -> None:
    if callback.from_user is None or not _is_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    if callback.data is None:
        await callback.answer()
        return
    try:
        order_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("Некорректные данные", show_alert=True)
        return
    order = await db.get_order(order_id)
    if order is None:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    if order.status not in ("paid", "pending"):
        await callback.answer(
            f"Заказ уже {order.status}", show_alert=True
        )
        return
    await db.update_order_status(order_id, "completed", completed=True)
    try:
        await bot.send_message(
            order.user_id,
            texts.order_completed(order.stars_amount, order.id),
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        log.warning("Cannot notify user %s about completion: %s", order.user_id, exc)
    if callback.message is not None:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"Заказ #{order_id} помечен как выданный.",
            reply_markup=admin_back_kb(),
        )
    await callback.answer("Готово")


@router.callback_query(F.data.startswith("adm:cancel:"))
async def admin_cancel_order(
    callback: CallbackQuery, bot: Bot, db: Database, config: Config
) -> None:
    if callback.from_user is None or not _is_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    if callback.data is None:
        await callback.answer()
        return
    try:
        order_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("Некорректные данные", show_alert=True)
        return
    order = await db.get_order(order_id)
    if order is None:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    await db.update_order_status(order_id, "cancelled")
    try:
        await bot.send_message(
            order.user_id,
            texts.order_cancelled(order.id),
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        log.warning("Cannot notify user %s about cancel: %s", order.user_id, exc)
    if callback.message is not None:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"Заказ #{order_id} отменён.",
            reply_markup=admin_back_kb(),
        )
    await callback.answer()


# Keep order with admin_order_kb in scope (re-export use)
__all__ = ["router", "admin_order_kb"]
