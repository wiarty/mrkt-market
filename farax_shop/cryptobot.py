"""Minimal async client for the @CryptoBot Pay API.

Docs: https://help.crypt.bot/crypto-pay-api
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp

log = logging.getLogger(__name__)


class CryptoBotError(RuntimeError):
    pass


@dataclass
class Invoice:
    invoice_id: int
    status: str
    pay_url: str
    amount: str
    currency_type: str
    asset: Optional[str]
    fiat: Optional[str]
    raw: dict[str, Any]


class CryptoBotClient:
    def __init__(self, token: str, base_url: str):
        self.token = token
        self.base_url = base_url.rstrip("/")

    async def _request(self, method: str, **params: Any) -> Any:
        if not self.token:
            raise CryptoBotError("CryptoBot token is not configured")
        url = f"{self.base_url}/{method}"
        headers = {"Crypto-Pay-API-Token": self.token}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=params) as resp:
                data = await resp.json(content_type=None)
        if not data.get("ok"):
            err = data.get("error") or data
            raise CryptoBotError(f"CryptoBot API error: {err}")
        return data["result"]

    async def create_invoice(
        self,
        *,
        amount: float,
        currency_type: str,
        asset: Optional[str] = None,
        fiat: Optional[str] = None,
        description: str = "",
        payload: str = "",
        expires_in: int = 3600,
    ) -> Invoice:
        """Create a new invoice.

        ``currency_type`` is ``"crypto"`` or ``"fiat"``. For crypto pass
        ``asset`` (USDT, TON, BTC, ...). For fiat pass ``fiat`` (RUB, USD, EUR).
        """
        params: dict[str, Any] = {
            "currency_type": currency_type,
            "amount": f"{amount:.2f}" if currency_type == "fiat" else f"{amount:.6f}",
            "description": description[:1024],
            "payload": payload[:4096],
            "expires_in": expires_in,
            "allow_anonymous": False,
        }
        if currency_type == "crypto":
            if not asset:
                raise CryptoBotError("`asset` is required for crypto invoice")
            params["asset"] = asset
        else:
            if not fiat:
                raise CryptoBotError("`fiat` is required for fiat invoice")
            params["fiat"] = fiat
            params["accepted_assets"] = "USDT,TON,BTC,ETH,LTC,BNB,TRX"
        result = await self._request("createInvoice", **params)
        return _parse_invoice(result)

    async def get_invoice(self, invoice_id: int) -> Optional[Invoice]:
        result = await self._request("getInvoices", invoice_ids=str(invoice_id))
        items = result.get("items") if isinstance(result, dict) else None
        if not items:
            return None
        return _parse_invoice(items[0])

    async def delete_invoice(self, invoice_id: int) -> bool:
        try:
            await self._request("deleteInvoice", invoice_id=invoice_id)
            return True
        except CryptoBotError as exc:
            log.warning("CryptoBot deleteInvoice failed: %s", exc)
            return False


def _parse_invoice(data: dict[str, Any]) -> Invoice:
    return Invoice(
        invoice_id=int(data["invoice_id"]),
        status=str(data.get("status", "")),
        pay_url=str(data.get("bot_invoice_url") or data.get("pay_url") or ""),
        amount=str(data.get("amount", "")),
        currency_type=str(data.get("currency_type", "")),
        asset=data.get("asset"),
        fiat=data.get("fiat"),
        raw=data,
    )
