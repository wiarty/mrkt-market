"""Static message templates for FaraxShop."""

from __future__ import annotations

from . import emojis as em


def welcome(shop_name: str, user_first_name: str) -> str:
    return (
        f"<b>{em.e(em.PARTY)} Добро пожаловать в {shop_name}, {user_first_name}!</b>\n\n"
        f"{em.e(em.MONEY)} Здесь ты можешь купить Telegram Stars быстро и выгодно.\n"
        f"{em.e(em.CRYPTO_BOT)} Принимаем оплату в <b>RUB</b> и <b>USDT</b> через CryptoBot.\n\n"
        f"{em.e(em.INFO)} Выбери действие в меню ниже."
    )


def profile(
    user_id: int,
    username: str | None,
    total_stars: int,
    total_rub: float,
    total_usdt: float,
) -> str:
    uname = f"@{username}" if username else "—"
    return (
        f"<b>{em.e(em.PROFILE)} Твой профиль</b>\n\n"
        f"{em.e(em.TAG)} <b>ID:</b> <code>{user_id}</code>\n"
        f"{em.e(em.PEN)} <b>Username:</b> {uname}\n"
        f"{em.e(em.GIFT)} <b>Куплено звёзд:</b> {total_stars}\n"
        f"{em.e(em.MONEY)} <b>Потрачено RUB:</b> {total_rub:.2f}\n"
        f"{em.e(em.CRYPTO_BOT)} <b>Потрачено USDT:</b> {total_usdt:.2f}"
    )


def buy_select_amount(price_rub: float, price_usdt: float, min_stars: int) -> str:
    return (
        f"<b>{em.e(em.GIFT)} Покупка звёзд</b>\n\n"
        f"{em.e(em.MONEY)} <b>Цена за 1 звезду:</b> "
        f"{price_rub:.2f} RUB / {price_usdt:.4f} USDT\n"
        f"{em.e(em.TAG)} <b>Минимум:</b> {min_stars} звёзд\n\n"
        f"{em.e(em.INFO)} Выбери количество или укажи своё."
    )


def buy_custom_prompt(min_stars: int) -> str:
    return (
        f"<b>{em.e(em.PEN)} Своё количество</b>\n\n"
        f"{em.e(em.INFO)} Отправь количество звёзд числом "
        f"(минимум {min_stars}).\n"
        f"{em.e(em.CROSS)} Чтобы отменить — нажми «Отмена»."
    )


def buy_select_currency(stars: int, rub: float, usdt: float) -> str:
    return (
        f"<b>{em.e(em.GIFT)} {stars} звёзд</b>\n\n"
        f"{em.e(em.MONEY)} <b>RUB:</b> {rub:.2f} ₽\n"
        f"{em.e(em.CRYPTO_BOT)} <b>USDT:</b> {usdt:.4f}\n\n"
        f"{em.e(em.INFO)} Выбери способ оплаты."
    )


def invoice_created(
    stars: int, currency: str, amount: float, order_id: int
) -> str:
    asset_str = "₽" if currency == "RUB" else "USDT"
    return (
        f"<b>{em.e(em.SEND_MONEY)} Счёт создан</b>\n\n"
        f"{em.e(em.GIFT)} <b>Количество:</b> {stars} звёзд\n"
        f"{em.e(em.MONEY)} <b>Сумма:</b> {amount:.4f} {asset_str}\n"
        f"{em.e(em.TAG)} <b>Заказ #{order_id}</b>\n\n"
        f"{em.e(em.INFO)} Нажми «Оплатить», затем вернись и нажми "
        f"«Я оплатил — проверить»."
    )


def order_paid(stars: int, order_id: int) -> str:
    return (
        f"<b>{em.e(em.PARTY)} Оплата получена!</b>\n\n"
        f"{em.e(em.GIFT)} <b>Куплено:</b> {stars} звёзд\n"
        f"{em.e(em.TAG)} <b>Заказ #{order_id}</b>\n\n"
        f"{em.e(em.CLOCK)} Звёзды будут зачислены в ближайшее время.\n"
        f"{em.e(em.INFO)} Спасибо за покупку!"
    )


def order_completed(stars: int, order_id: int) -> str:
    return (
        f"<b>{em.e(em.CHECK)} Заказ выполнен</b>\n\n"
        f"{em.e(em.GIFT)} <b>Звёзды зачислены:</b> {stars}\n"
        f"{em.e(em.TAG)} <b>Заказ #{order_id}</b>\n\n"
        f"{em.e(em.PARTY)} Спасибо, что выбрал нас!"
    )


def order_cancelled(order_id: int) -> str:
    return (
        f"<b>{em.e(em.CROSS)} Заказ отменён</b>\n\n"
        f"{em.e(em.TAG)} <b>Заказ #{order_id}</b>"
    )


def order_pending(order_id: int) -> str:
    return (
        f"<b>{em.e(em.CLOCK)} Оплата ещё не поступила</b>\n\n"
        f"{em.e(em.TAG)} <b>Заказ #{order_id}</b>\n"
        f"{em.e(em.INFO)} Попробуй ещё раз через минуту."
    )


def admin_menu() -> str:
    return (
        f"<b>{em.e(em.SETTINGS)} Админ-панель</b>\n\n"
        f"{em.e(em.INFO)} Выбери раздел."
    )


def admin_prices(price_rub: float, price_usdt: float) -> str:
    return (
        f"<b>{em.e(em.MONEY)} Цены за 1 звезду</b>\n\n"
        f"{em.e(em.MONEY)} <b>RUB:</b> {price_rub:.4f}\n"
        f"{em.e(em.CRYPTO_BOT)} <b>USDT:</b> {price_usdt:.6f}"
    )


def admin_settings_overview(settings: dict[str, str]) -> str:
    rub = float(settings.get("price_rub", "0"))
    usdt = float(settings.get("price_usdt", "0"))
    min_stars = int(settings.get("min_stars", "0"))
    support = settings.get("support_username") or "—"
    channel = settings.get("channel_link") or "—"
    return (
        f"<b>{em.e(em.SETTINGS)} Настройки магазина</b>\n\n"
        f"{em.e(em.MONEY)} <b>Цена RUB:</b> {rub}\n"
        f"{em.e(em.CRYPTO_BOT)} <b>Цена USDT:</b> {usdt}\n"
        f"{em.e(em.TAG)} <b>Минимум звёзд:</b> {min_stars}\n"
        f"{em.e(em.SMILE)} <b>Поддержка:</b> {support}\n"
        f"{em.e(em.MEGAPHONE)} <b>Канал:</b> {channel}"
    )


def admin_stats(stats: dict[str, float], total_users: int) -> str:
    return (
        f"<b>{em.e(em.STATS)} Статистика</b>\n\n"
        f"{em.e(em.PEOPLE)} <b>Пользователей:</b> {total_users}\n"
        f"{em.e(em.BOX)} <b>Заказов всего:</b> {int(stats['total_orders'])}\n"
        f"{em.e(em.CHECK)} <b>Оплачено:</b> {int(stats['paid_orders'])}\n"
        f"{em.e(em.GIFT)} <b>Звёзд продано:</b> {int(stats['stars_sold'])}\n"
        f"{em.e(em.MONEY)} <b>Выручка RUB:</b> {stats['revenue_rub']:.2f}\n"
        f"{em.e(em.CRYPTO_BOT)} <b>Выручка USDT:</b> {stats['revenue_usdt']:.4f}"
    )


def broadcast_prompt() -> str:
    return (
        f"<b>{em.e(em.MEGAPHONE)} Рассылка</b>\n\n"
        f"{em.e(em.WRITE)} Отправь сообщение для рассылки "
        f"(текст / фото / видео — любое).\n"
        f"{em.e(em.CROSS)} Для отмены отправь «Отмена»."
    )


def broadcast_confirm(total: int) -> str:
    return (
        f"<b>{em.e(em.MEGAPHONE)} Подтверждение рассылки</b>\n\n"
        f"{em.e(em.PEOPLE)} <b>Получателей:</b> {total}\n\n"
        f"{em.e(em.INFO)} Сообщение выше будет отправлено всем "
        f"пользователям. Подтвердить?"
    )


def broadcast_done(success: int, failed: int) -> str:
    return (
        f"<b>{em.e(em.CHECK)} Рассылка завершена</b>\n\n"
        f"{em.e(em.CHECK)} <b>Успешно:</b> {success}\n"
        f"{em.e(em.CROSS)} <b>Ошибок:</b> {failed}"
    )


def admin_new_order_alert(
    order_id: int,
    user_id: int,
    username: str | None,
    stars: int,
    currency: str,
    amount: float,
) -> str:
    uname = f"@{username}" if username else "—"
    asset_str = "₽" if currency == "RUB" else "USDT"
    return (
        f"<b>{em.e(em.BELL)} Новый оплаченный заказ</b>\n\n"
        f"{em.e(em.TAG)} <b>Заказ #{order_id}</b>\n"
        f"{em.e(em.PROFILE)} <b>Пользователь:</b> {uname} "
        f"(<code>{user_id}</code>)\n"
        f"{em.e(em.GIFT)} <b>Звёзд:</b> {stars}\n"
        f"{em.e(em.MONEY)} <b>Сумма:</b> {amount:.4f} {asset_str}\n\n"
        f"{em.e(em.INFO)} Зачисли звёзды и отметь заказ как выданный."
    )


def access_denied() -> str:
    return f"<b>{em.e(em.CROSS)} Нет доступа.</b>"


def cancelled() -> str:
    return f"<b>{em.e(em.CROSS)} Действие отменено.</b>"


def support_unset() -> str:
    return (
        f"<b>{em.e(em.INFO)} Поддержка пока не настроена.</b>\n"
        f"Администратор скоро добавит контакт."
    )


def order_list_empty() -> str:
    return f"<b>{em.e(em.BOX)} У тебя пока нет заказов.</b>"


def format_user_orders(orders: list, max_lines: int = 10) -> str:
    lines = [f"<b>{em.e(em.BOX)} Твои заказы</b>\n"]
    for o in orders[:max_lines]:
        status_map = {
            "pending": "ожидает оплаты",
            "paid": "оплачен",
            "completed": "выдан",
            "cancelled": "отменён",
        }
        status = status_map.get(o.status, o.status)
        asset = "₽" if o.currency == "RUB" else "USDT"
        lines.append(
            f"{em.e(em.TAG)} #{o.id} — {o.stars_amount}★ "
            f"({o.price_amount:.2f} {asset}) — {status}"
        )
    return "\n".join(lines)
