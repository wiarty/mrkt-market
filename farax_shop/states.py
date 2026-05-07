"""FSM states used across the bot."""

from aiogram.fsm.state import State, StatesGroup


class BuyStates(StatesGroup):
    waiting_for_amount = State()


class AdminStates(StatesGroup):
    waiting_for_rub_price = State()
    waiting_for_usdt_price = State()
    waiting_for_min_stars = State()
    waiting_for_support_username = State()
    waiting_for_channel_link = State()
    waiting_for_broadcast_message = State()
    confirm_broadcast = State()
