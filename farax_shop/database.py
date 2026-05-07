"""Async SQLite storage for users, orders and shop settings."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import aiosqlite

DEFAULT_SETTINGS: dict[str, str] = {
    # price per 1 star
    "price_rub": "1.5",
    "price_usdt": "0.015",
    # minimum amount of stars per order
    "min_stars": "50",
    # support username (without @)
    "support_username": "",
    # channel link (https://t.me/...)
    "channel_link": "",
}


@dataclass
class Order:
    id: int
    user_id: int
    stars_amount: int
    currency: str          # "RUB" | "USDT"
    price_amount: float
    invoice_id: Optional[str]
    invoice_url: Optional[str]
    status: str            # "pending" | "paid" | "completed" | "cancelled"
    created_at: int
    paid_at: Optional[int]
    completed_at: Optional[int]


@dataclass
class UserRow:
    user_id: int
    username: Optional[str]
    full_name: Optional[str]
    created_at: int
    total_stars: int
    total_rub: float
    total_usdt: float
    is_banned: int


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    created_at INTEGER NOT NULL,
                    total_stars INTEGER NOT NULL DEFAULT 0,
                    total_rub REAL NOT NULL DEFAULT 0,
                    total_usdt REAL NOT NULL DEFAULT 0,
                    is_banned INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    stars_amount INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    price_amount REAL NOT NULL,
                    invoice_id TEXT,
                    invoice_url TEXT,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    paid_at INTEGER,
                    completed_at INTEGER
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            for key, value in DEFAULT_SETTINGS.items():
                await db.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (key, value),
                )
            await db.commit()

    # ---------- settings ----------
    async def get_setting(self, key: str, default: str = "") -> str:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ) as cur:
                row = await cur.fetchone()
        return row[0] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            await db.commit()

    async def all_settings(self) -> dict[str, str]:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT key, value FROM settings") as cur:
                rows = await cur.fetchall()
        return {row[0]: row[1] for row in rows}

    # ---------- users ----------
    async def upsert_user(
        self,
        user_id: int,
        username: Optional[str],
        full_name: Optional[str],
    ) -> None:
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO users (user_id, username, full_name, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name
                """,
                (user_id, username, full_name, now),
            )
            await db.commit()

    async def get_user(self, user_id: int) -> Optional[UserRow]:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT user_id, username, full_name, created_at, total_stars, "
                "total_rub, total_usdt, is_banned FROM users WHERE user_id = ?",
                (user_id,),
            ) as cur:
                row = await cur.fetchone()
        if not row:
            return None
        return UserRow(*row)

    async def all_user_ids(self) -> list[int]:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT user_id FROM users WHERE is_banned = 0"
            ) as cur:
                rows = await cur.fetchall()
        return [row[0] for row in rows]

    async def total_users(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cur:
                row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def set_banned(self, user_id: int, banned: bool) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE users SET is_banned = ? WHERE user_id = ?",
                (1 if banned else 0, user_id),
            )
            await db.commit()

    # ---------- orders ----------
    async def create_order(
        self,
        user_id: int,
        stars_amount: int,
        currency: str,
        price_amount: float,
        invoice_id: Optional[str],
        invoice_url: Optional[str],
    ) -> int:
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                INSERT INTO orders
                    (user_id, stars_amount, currency, price_amount,
                     invoice_id, invoice_url, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    user_id,
                    stars_amount,
                    currency,
                    price_amount,
                    invoice_id,
                    invoice_url,
                    now,
                ),
            )
            await db.commit()
            return cur.lastrowid or 0

    async def get_order(self, order_id: int) -> Optional[Order]:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT id, user_id, stars_amount, currency, price_amount, "
                "invoice_id, invoice_url, status, created_at, paid_at, "
                "completed_at FROM orders WHERE id = ?",
                (order_id,),
            ) as cur:
                row = await cur.fetchone()
        if not row:
            return None
        return Order(*row)

    async def list_pending_orders(self) -> list[Order]:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT id, user_id, stars_amount, currency, price_amount, "
                "invoice_id, invoice_url, status, created_at, paid_at, "
                "completed_at FROM orders WHERE status = 'pending' "
                "ORDER BY created_at ASC"
            ) as cur:
                rows = await cur.fetchall()
        return [Order(*row) for row in rows]

    async def list_user_orders(self, user_id: int, limit: int = 10) -> list[Order]:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT id, user_id, stars_amount, currency, price_amount, "
                "invoice_id, invoice_url, status, created_at, paid_at, "
                "completed_at FROM orders WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ) as cur:
                rows = await cur.fetchall()
        return [Order(*row) for row in rows]

    async def update_order_status(
        self,
        order_id: int,
        status: str,
        paid: bool = False,
        completed: bool = False,
    ) -> None:
        now = int(time.time())
        fields: list[str] = ["status = ?"]
        values: list[Any] = [status]
        if paid:
            fields.append("paid_at = ?")
            values.append(now)
        if completed:
            fields.append("completed_at = ?")
            values.append(now)
        values.append(order_id)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                f"UPDATE orders SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            await db.commit()

    async def add_purchase_stats(
        self,
        user_id: int,
        stars: int,
        currency: str,
        amount: float,
    ) -> None:
        currency_field = "total_rub" if currency.upper() == "RUB" else "total_usdt"
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                f"UPDATE users SET total_stars = total_stars + ?, "
                f"{currency_field} = {currency_field} + ? WHERE user_id = ?",
                (stars, amount, user_id),
            )
            await db.commit()

    async def shop_stats(self) -> dict[str, float]:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                """
                SELECT
                    COUNT(*) AS total_orders,
                    SUM(CASE WHEN status IN ('paid','completed') THEN 1 ELSE 0 END)
                        AS paid_orders,
                    COALESCE(SUM(CASE WHEN currency='RUB'
                        AND status IN ('paid','completed')
                        THEN price_amount ELSE 0 END), 0) AS revenue_rub,
                    COALESCE(SUM(CASE WHEN currency='USDT'
                        AND status IN ('paid','completed')
                        THEN price_amount ELSE 0 END), 0) AS revenue_usdt,
                    COALESCE(SUM(CASE WHEN status IN ('paid','completed')
                        THEN stars_amount ELSE 0 END), 0) AS stars_sold
                FROM orders
                """
            ) as cur:
                row = await cur.fetchone()
        if not row:
            return {
                "total_orders": 0,
                "paid_orders": 0,
                "revenue_rub": 0.0,
                "revenue_usdt": 0.0,
                "stars_sold": 0,
            }
        return {
            "total_orders": int(row[0] or 0),
            "paid_orders": int(row[1] or 0),
            "revenue_rub": float(row[2] or 0),
            "revenue_usdt": float(row[3] or 0),
            "stars_sold": int(row[4] or 0),
        }
