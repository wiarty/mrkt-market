"""Inline / reply keyboard builders.

All buttons use only premium custom emojis via ``icon_custom_emoji_id`` and
plain text labels — no unicode emoji inside button text per project spec.
"""

from __future__ import annotations

from typing import Any, Optional

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from . import emojis as em


def _ikb(
    text: str,
    *,
    callback_data: Optional[str] = None,
    url: Optional[str] = None,
    icon: Optional[str] = None,
) -> InlineKeyboardButton:
    """Construct an InlineKeyboardButton with optional premium icon."""
    extra: dict[str, Any] = {}
    if icon:
        extra["icon_custom_emoji_id"] = icon
    if url:
        return InlineKeyboardButton(text=text, url=url, **extra)
    return InlineKeyboardButton(
        text=text, callback_data=callback_data or "noop", **extra
    )


# ============================================================================
#  USER KEYBOARDS
# ============================================================================
def main_menu_kb(
    *, support_username: str = "", channel_link: str = "", is_admin: bool = False
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [_ikb("Купить звёзды", callback_data="buy", icon=em.MONEY)],
        [
            _ikb("Профиль", callback_data="profile", icon=em.PROFILE),
            _ikb("Мои заказы", callback_data="orders", icon=em.BOX),
        ],
    ]
    extra_row: list[InlineKeyboardButton] = []
    if channel_link:
        extra_row.append(_ikb("Канал", url=channel_link, icon=em.MEGAPHONE))
    if support_username:
        url = f"https://t.me/{support_username.lstrip('@')}"
        extra_row.append(_ikb("Поддержка", url=url, icon=em.SMILE))
    if extra_row:
        rows.append(extra_row)
    if is_admin:
        rows.append([_ikb("Админ-панель", callback_data="admin", icon=em.SETTINGS)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_ikb("Назад в меню", callback_data="menu", icon=em.BACK)],
        ]
    )


def buy_amount_kb() -> InlineKeyboardMarkup:
    presets = [50, 100, 250, 500, 1000, 2500]
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for value in presets:
        row.append(
            _ikb(str(value), callback_data=f"buy_amount:{value}", icon=em.GIFT)
        )
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [_ikb("Своё количество", callback_data="buy_custom", icon=em.PEN)]
    )
    rows.append([_ikb("Назад", callback_data="menu", icon=em.BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def buy_currency_kb(stars: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _ikb(
                    "Рубли (RUB)",
                    callback_data=f"buy_pay:{stars}:RUB",
                    icon=em.MONEY,
                ),
                _ikb(
                    "USDT",
                    callback_data=f"buy_pay:{stars}:USDT",
                    icon=em.CRYPTO_BOT,
                ),
            ],
            [_ikb("Назад", callback_data="buy", icon=em.BACK)],
        ]
    )


def invoice_kb(pay_url: str, order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_ikb("Оплатить", url=pay_url, icon=em.SEND_MONEY)],
            [
                _ikb(
                    "Я оплатил — проверить",
                    callback_data=f"check:{order_id}",
                    icon=em.CHECK,
                )
            ],
            [
                _ikb(
                    "Отменить заказ",
                    callback_data=f"cancel:{order_id}",
                    icon=em.CROSS,
                )
            ],
        ]
    )


# ============================================================================
#  ADMIN KEYBOARDS
# ============================================================================
def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_ikb("Цены", callback_data="adm:prices", icon=em.MONEY)],
            [
                _ikb(
                    "Минимум звёзд",
                    callback_data="adm:min_stars",
                    icon=em.TAG,
                ),
                _ikb(
                    "Поддержка",
                    callback_data="adm:support",
                    icon=em.SMILE,
                ),
            ],
            [_ikb("Канал", callback_data="adm:channel", icon=em.MEGAPHONE)],
            [
                _ikb(
                    "Рассылка",
                    callback_data="adm:broadcast",
                    icon=em.MEGAPHONE,
                )
            ],
            [_ikb("Статистика", callback_data="adm:stats", icon=em.STATS)],
            [_ikb("Заказы", callback_data="adm:orders", icon=em.BOX)],
            [_ikb("В меню", callback_data="menu", icon=em.BACK)],
        ]
    )


def admin_prices_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _ikb(
                    "Цена в RUB",
                    callback_data="adm:price_rub",
                    icon=em.MONEY,
                )
            ],
            [
                _ikb(
                    "Цена в USDT",
                    callback_data="adm:price_usdt",
                    icon=em.CRYPTO_BOT,
                )
            ],
            [_ikb("Назад", callback_data="admin", icon=em.BACK)],
        ]
    )


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_ikb("Назад", callback_data="admin", icon=em.BACK)],
        ]
    )


def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _ikb(
                    "Отправить",
                    callback_data="adm:bc_send",
                    icon=em.SEND_UP,
                ),
                _ikb(
                    "Отменить",
                    callback_data="adm:bc_cancel",
                    icon=em.CROSS,
                ),
            ],
        ]
    )


def admin_order_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _ikb(
                    "Отметить выданным",
                    callback_data=f"adm:complete:{order_id}",
                    icon=em.CHECK,
                )
            ],
            [
                _ikb(
                    "Отменить заказ",
                    callback_data=f"adm:cancel:{order_id}",
                    icon=em.CROSS,
                )
            ],
        ]
    )


def cancel_input_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
