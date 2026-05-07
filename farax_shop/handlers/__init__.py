"""Handlers package."""

from aiogram import Router

from . import admin, broadcast, buy, payment, start


def build_router() -> Router:
    router = Router(name="farax_shop")
    router.include_router(start.router)
    router.include_router(buy.router)
    router.include_router(payment.router)
    router.include_router(broadcast.router)
    router.include_router(admin.router)
    return router


__all__ = ["build_router"]
