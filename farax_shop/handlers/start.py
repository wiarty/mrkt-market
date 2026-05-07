"""/start, main menu, profile and user orders."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import texts
from ..config import Config
from ..database import Database
from ..keyboards import back_to_menu_kb, main_menu_kb

router = Router(name="start")


async def _show_menu(
    target: Message | CallbackQuery,
    db: Database,
    config: Config,
    *,
    edit: bool = False,
) -> None:
    user = target.from_user
    if user is None:
        return
    settings = await db.all_settings()
    text = texts.welcome(config.shop_name, user.first_name or "друг")
    kb = main_menu_kb(
        support_username=settings.get("support_username", ""),
        channel_link=settings.get("channel_link", ""),
        is_admin=user.id in config.admin_ids,
    )
    if isinstance(target, CallbackQuery) and edit and target.message is not None:
        await target.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        message = target if isinstance(target, Message) else target.message
        if message is None:
            return
        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.message(CommandStart())
async def on_start(
    message: Message, state: FSMContext, db: Database, config: Config
) -> None:
    await state.clear()
    user = message.from_user
    if user is None:
        return
    await db.upsert_user(user.id, user.username, user.full_name)
    await _show_menu(message, db, config)


@router.message(Command("menu"))
async def on_menu(
    message: Message, state: FSMContext, db: Database, config: Config
) -> None:
    await state.clear()
    await _show_menu(message, db, config)


@router.callback_query(F.data == "menu")
async def on_menu_cb(
    callback: CallbackQuery, state: FSMContext, db: Database, config: Config
) -> None:
    await state.clear()
    await _show_menu(callback, db, config, edit=True)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def on_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "profile")
async def on_profile(
    callback: CallbackQuery, db: Database, config: Config
) -> None:
    user = callback.from_user
    if user is None or callback.message is None:
        await callback.answer()
        return
    await db.upsert_user(user.id, user.username, user.full_name)
    row = await db.get_user(user.id)
    text = texts.profile(
        user_id=user.id,
        username=user.username,
        total_stars=row.total_stars if row else 0,
        total_rub=row.total_rub if row else 0.0,
        total_usdt=row.total_usdt if row else 0.0,
    )
    await callback.message.edit_text(
        text, reply_markup=back_to_menu_kb(), parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(F.data == "orders")
async def on_orders(callback: CallbackQuery, db: Database) -> None:
    user = callback.from_user
    if user is None or callback.message is None:
        await callback.answer()
        return
    orders = await db.list_user_orders(user.id, limit=10)
    if not orders:
        text = texts.order_list_empty()
    else:
        text = texts.format_user_orders(orders)
    await callback.message.edit_text(
        text, reply_markup=back_to_menu_kb(), parse_mode=ParseMode.HTML
    )
    await callback.answer()
