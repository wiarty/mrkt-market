"""Premium emoji helpers.

Wrap any emoji with `tg(<id>, fallback)` to render it as a premium custom
emoji in HTML messages. For inline / reply keyboard buttons pass the same
id via ``icon_custom_emoji_id``.
"""

from __future__ import annotations


def tg(emoji_id: str, fallback: str) -> str:
    """Return HTML markup for a premium custom emoji."""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


# --- Premium emoji ID catalogue (provided by the user) -----------------------
SETTINGS = "5870982283724328568"          # ⚙
PROFILE = "5870994129244131212"           # 👤
PEOPLE = "5870772616305839506"            # 👥
PERSON_CHECK = "5891207662678317861"      # 👤✅
PERSON_CROSS = "5893192487324880883"      # 👤❌
FILE = "5870528606328852614"              # 📁
SMILE = "5870764288364252592"             # 🙂
GROWTH = "5870930636742595124"            # 📊 рост
STATS = "5870921681735781843"             # 📊 статистика
HOUSE = "5873147866364514353"             # 🏘
LOCK_CLOSED = "6037249452824072506"       # 🔒
LOCK_OPEN = "6037496202990194718"         # 🔓
MEGAPHONE = "6039422865189638057"         # 📣
CHECK = "5870633910337015697"             # ✅
CROSS = "5870657884844462243"             # ❌
PEN = "5870676941614354370"               # 🖋
TRASH = "5870875489362513438"             # 🗑
DOWN_ARROW = "5893057118545646106"        # 📰 вниз
PAPERCLIP = "6039451237743595514"         # 📎
LINK = "5769289093221454192"              # 🔗
INFO = "6028435952299413210"              # ℹ
BOT = "6030400221232501136"               # 🤖
EYE = "6037397706505195857"               # 👁
EYE_HIDDEN = "6037243349675544634"        # 👁 скрыто
SEND_UP = "5963103826075456248"           # ⬆
DOWNLOAD = "6039802767931871481"          # ⬇
BELL = "6039486778597970865"              # 🔔
GIFT = "6032644646587338669"              # 🎁
CLOCK = "5983150113483134607"             # ⏰
PARTY = "6041731551845159060"             # 🎉
FONT_LINK = "5870801517140775623"         # 🔗 шрифт
WRITE = "5870753782874246579"             # ✍
MEDIA_PHOTO = "6035128606563241721"       # 🖼
PIN = "6042011682497106307"               # 📍
WALLET = "5769126056262898415"            # 👛
BOX = "5884479287171485878"               # 📦
CRYPTO_BOT = "5260752406890711732"        # 👾
CALENDAR = "5890937706803894250"          # 📅
TAG = "5886285355279193209"               # 🏷
CLOCK_PAST = "5775896410780079073"        # 🕓 время прошло
APPS = "5778672437122045013"              # 📦 приложения
BRUSH = "6050679691004612757"             # 🖌
ADD_TEXT = "5771851822897566479"          # 🔡
RESOLUTION = "5778479949572738874"        # ↔
MONEY = "5904462880941545555"             # 🪙
SEND_MONEY = "5890848474563352982"        # 🪙 отправить
RECEIVE_MONEY = "5879814368572478751"     # 🏧
CODE = "5940433880585605708"              # 🔨 код
LOADING = "5345906554510012647"           # 🔄
BACK = "5210956306952758910"              # ◁ (placeholder, see fallback ◁)


# Fallback unicode (used inside tg-emoji tag for clients without premium)
EMOJI_FALLBACK = {
    SETTINGS: "⚙",
    PROFILE: "👤",
    PEOPLE: "👥",
    PERSON_CHECK: "👤",
    PERSON_CROSS: "👤",
    FILE: "📁",
    SMILE: "🙂",
    GROWTH: "📊",
    STATS: "📊",
    HOUSE: "🏘",
    LOCK_CLOSED: "🔒",
    LOCK_OPEN: "🔓",
    MEGAPHONE: "📣",
    CHECK: "✅",
    CROSS: "❌",
    PEN: "🖋",
    TRASH: "🗑",
    DOWN_ARROW: "📰",
    PAPERCLIP: "📎",
    LINK: "🔗",
    INFO: "ℹ",
    BOT: "🤖",
    EYE: "👁",
    EYE_HIDDEN: "👁",
    SEND_UP: "⬆",
    DOWNLOAD: "⬇",
    BELL: "🔔",
    GIFT: "🎁",
    CLOCK: "⏰",
    PARTY: "🎉",
    FONT_LINK: "🔗",
    WRITE: "✍",
    MEDIA_PHOTO: "🖼",
    PIN: "📍",
    WALLET: "👛",
    BOX: "📦",
    CRYPTO_BOT: "👾",
    CALENDAR: "📅",
    TAG: "🏷",
    CLOCK_PAST: "🕓",
    APPS: "📦",
    BRUSH: "🖌",
    ADD_TEXT: "🔡",
    RESOLUTION: "↔",
    MONEY: "🪙",
    SEND_MONEY: "🪙",
    RECEIVE_MONEY: "🏧",
    CODE: "🔨",
    LOADING: "🔄",
    BACK: "◁",
}


def e(emoji_id: str) -> str:
    """Render a premium emoji using the canonical fallback."""
    return tg(emoji_id, EMOJI_FALLBACK.get(emoji_id, "•"))
