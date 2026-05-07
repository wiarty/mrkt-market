"""Admin broadcast flow."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from .. import texts
from ..config import Config
from ..database import Database
from ..keyboards import admin_menu_kb, broadcast_confirm_kb, cancel_input_kb
from ..states import AdminStates

router = Router(name="broadcast")
log = logging.getLogger(__name__)


def _is_admin(user_id: int, config: Config) -> bool:
    return user_id in config.admin_ids


@router.callback_query(F.data == "adm:broadcast")
async def start_broadcast(
    callback: CallbackQuery, state: FSMContext, config: Config
) -> None:
    if callback.from_user is None or not _is_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    if callback.message is None:
        await callback.answer()
        return
    await state.clear()
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    await callback.message.answer(
        texts.broadcast_prompt(),
        reply_markup=cancel_input_kb(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.message(
    AdminStates.waiting_for_broadcast_message,
    F.text.lower() == "отмена",
)
async def cancel_broadcast(message: Message, state: FSMContext) -> None:
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


@router.message(AdminStates.waiting_for_broadcast_message)
async def receive_broadcast_message(
    message: Message, state: FSMContext, db: Database
) -> None:
    await state.update_data(
        broadcast_chat_id=message.chat.id,
        broadcast_message_id=message.message_id,
    )
    await state.set_state(AdminStates.confirm_broadcast)
    total = len(await db.all_user_ids())
    await message.answer(
        texts.broadcast_confirm(total),
        reply_markup=broadcast_confirm_kb(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(
    AdminStates.confirm_broadcast, F.data == "adm:bc_cancel"
)
async def cancel_confirm(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.edit_text(
            texts.cancelled(),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_menu_kb(),
        )
    await callback.answer()


@router.callback_query(
    AdminStates.confirm_broadcast, F.data == "adm:bc_send"
)
async def confirm_and_send(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if callback.from_user is None or not _is_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    data = await state.get_data()
    chat_id = data.get("broadcast_chat_id")
    message_id = data.get("broadcast_message_id")
    if chat_id is None or message_id is None:
        await callback.answer("Сообщение для рассылки потеряно.", show_alert=True)
        await state.clear()
        return

    user_ids = await db.all_user_ids()
    await state.clear()

    if callback.message is not None:
        await callback.message.edit_text(
            f"Отправляю {len(user_ids)} получателям…",
            parse_mode=ParseMode.HTML,
        )

    success = 0
    failed = 0
    for user_id in user_ids:
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=chat_id,
                message_id=message_id,
            )
            success += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 1)
            try:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=chat_id,
                    message_id=message_id,
                )
                success += 1
            except TelegramAPIError:
                failed += 1
        except TelegramAPIError as exc:
            log.debug("broadcast to %s failed: %s", user_id, exc)
            failed += 1
        except Exception as exc:
            log.warning("broadcast to %s unexpected: %s", user_id, exc)
            failed += 1
        await asyncio.sleep(0.05)

    if callback.message is not None:
        await callback.message.answer(
            texts.broadcast_done(success, failed),
            reply_markup=admin_menu_kb(),
            parse_mode=ParseMode.HTML,
        )
    await callback.answer()
