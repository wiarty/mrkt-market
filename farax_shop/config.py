"""Bot configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _parse_admin_ids(raw: str) -> list[int]:
    if not raw:
        return []
    out: list[int] = []
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            out.append(int(chunk))
        except ValueError:
            continue
    return out


@dataclass
class Config:
    bot_token: str
    admin_ids: list[int] = field(default_factory=list)
    cryptobot_token: str = ""
    cryptobot_testnet: bool = False
    db_path: Path = Path("farax_shop.db")
    shop_name: str = "FaraxShop"
    invoice_poll_interval: int = 15

    @property
    def cryptobot_base_url(self) -> str:
        if self.cryptobot_testnet:
            return "https://testnet-pay.crypt.bot/api"
        return "https://pay.crypt.bot/api"


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError(
            "BOT_TOKEN is not set. Define it in environment or in a .env file."
        )

    return Config(
        bot_token=bot_token,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
        cryptobot_token=os.getenv("CRYPTOBOT_TOKEN", "").strip(),
        cryptobot_testnet=os.getenv("CRYPTOBOT_TESTNET", "0").lower() in {"1", "true", "yes"},
        db_path=Path(os.getenv("DB_PATH", "farax_shop.db")),
        shop_name=os.getenv("SHOP_NAME", "FaraxShop"),
        invoice_poll_interval=int(os.getenv("INVOICE_POLL_INTERVAL", "15")),
    )
