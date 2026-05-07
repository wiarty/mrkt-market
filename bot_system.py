import asyncio
import random
import json
import os
import shutil
from pathlib import Path
import telegram
from datetime import datetime
from telegram.error import TimedOut, NetworkError
from telethon import TelegramClient, events
from telethon.errors import (
    FloodWaitError, 
    UserPrivacyRestrictedError,
    ChatWriteForbiddenError,
    UserIsBlockedError,
    RPCError
)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler,
    ContextTypes,
    filters
)

# ==================== НАСТРОЙКИ ====================
# Конфигурация читается из (по приоритету):
#   1) переменных окружения ADMIN_BOT_TOKEN / MAIN_ADMIN_ID;
#   2) .env рядом со скриптом (формат KEY=VALUE по строкам);
#   3) secrets.json рядом со скриптом
#      (формат: {"ADMIN_BOT_TOKEN": "...", "MAIN_ADMIN_ID": 123456}).
# .env / secrets.json должны быть в .gitignore — не коммитьте токен.
def _load_dotenv():
    """Простой парсер .env (без внешних зависимостей).
    Читает файл .env рядом со скриптом и вкладывает пары
    KEY=VALUE в os.environ (не перезаписывая уже заданные переменные).
    """
    path = Path(__file__).resolve().parent / '.env'
    if not path.exists():
        return
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                # Поддерживаем синтаксис "export KEY=VALUE"
                if line.startswith('export '):
                    line = line[len('export '):].lstrip()
                if '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip()
                # Снимаем обрамляющие кавычки
                if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
                    v = v[1:-1]
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception as e:
        print(f"⚠️ Не удалось прочитать {path}: {e}")


def _load_local_secrets():
    path = Path(__file__).resolve().parent / 'secrets.json'
    if not path.exists():
        return {}
    try:
        raw = path.read_bytes()
    except Exception as e:
        print(f"⚠️ Не удалось открыть {path}: {e}")
        return {}
    if not raw.strip():
        print(f"⚠️ {path} пустой. Впишите в него JSON и сохраните (Ctrl+S).")
        return {}
    text = None
    last_err = None
    for enc in ('utf-8-sig', 'utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'cp1251'):
        try:
            text = raw.decode(enc)
            break
        except Exception as e:
            last_err = e
            continue
    if text is None:
        print(f"⚠️ {path}: не удалось распознать кодировку: {last_err}")
        return {}
    text = text.lstrip('﻿').strip()
    if not text:
        print(f"⚠️ {path} пустой после разбора. Сохраните файл с валидным JSON.")
        return {}
    try:
        data = json.loads(text)
    except Exception as e:
        head = repr(raw[:60])
        print(f"⚠️ {path}: невалидный JSON ({e}). Первые байты: {head}")
        return {}
    return data if isinstance(data, dict) else {}


_load_dotenv()
_LOCAL_SECRETS = _load_local_secrets()
ADMIN_BOT_TOKEN = (
    os.getenv("ADMIN_BOT_TOKEN")
    or _LOCAL_SECRETS.get("ADMIN_BOT_TOKEN")
    or ""
)
try:
    MAIN_ADMIN_ID = int(
        os.getenv("MAIN_ADMIN_ID")
        or _LOCAL_SECRETS.get("MAIN_ADMIN_ID")
        or 0
    )
except (TypeError, ValueError):
    MAIN_ADMIN_ID = 0

# ==================== ФАЙЛЫ ====================
USERS_FILE = 'users.json'
DATA_DIR = Path('data')

# Имена файлов внутри директории каждого пользователя
ACCOUNTS_FILENAME = 'accounts.json'
SCENARIOS_FILENAME = 'scenarios.json'
CONFIG_FILENAME = 'config.json'
SESSIONS_DIRNAME = 'sessions'

# Старые пути (для одноразовой миграции)
LEGACY_ACCOUNTS_FILE = 'accounts.json'
LEGACY_SCENARIOS_FILE = 'scenarios.json'
LEGACY_CONFIG_FILE = 'config.json'

# ==================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ====================
active_sessions = {}
user_states = {}
mailing_paused = {}
global_mailing_stop = False
admin_bot_app = None
reply_cache = {}
allowed_users = []
GREETINGS = ["привет", "приветик", "приветствую", "ку", "здарова"]

# ==================== PREMIUM EMOJI ====================
# Маппинг обычных эмодзи -> premium custom emoji ID.
# Применяется автоматически ко всем сообщениям бота через
# install_premium_emoji_filter() (см. main()).
PREMIUM_EMOJI_MAP = {
    '⚙️': '5870982283724328568',
    '⚙': '5870982283724328568',
    '👤': '5870994129244131212',
    '👥': '5870772616305839506',
    '📁': '5870528606328852614',
    '🙂': '5870764288364252592',
    '📊': '5870921681735781843',
    '📈': '5870930636742595124',
    '🏘': '5873147866364514353',
    '🏘️': '5873147866364514353',
    '🔒': '6037249452824072506',
    '🔐': '6037249452824072506',
    '🔓': '6037496202990194718',
    '📣': '6039422865189638057',
    '📢': '6039422865189638057',
    '✅': '5870633910337015697',
    '❌': '5870657884844462243',
    '🖋': '5870676941614354370',
    '🖋️': '5870676941614354370',
    '🗑': '5870875489362513438',
    '🗑️': '5870875489362513438',
    '📰': '5893057118545646106',
    '📎': '6039451237743595514',
    '🔗': '5769289093221454192',
    'ℹ': '6028435952299413210',
    'ℹ️': '6028435952299413210',
    '🤖': '6030400221232501136',
    '👁': '6037397706505195857',
    '👁️': '6037397706505195857',
    '⬆': '5963103826075456248',
    '⬆️': '5963103826075456248',
    '⬇': '6039802767931871481',
    '⬇️': '6039802767931871481',
    '🔔': '6039486778597970865',
    '🎁': '6032644646587338669',
    '⏰': '5983150113483134607',
    '⏱': '5983150113483134607',
    '⏱️': '5983150113483134607',
    '🎉': '6041731551845159060',
    '✍': '5870753782874246579',
    '✍️': '5870753782874246579',
    '🖼': '6035128606563241721',
    '🖼️': '6035128606563241721',
    '📍': '6042011682497106307',
    '👛': '5769126056262898415',
    '📦': '5884479287171485878',
    '👾': '5260752406890711732',
    '📅': '5890937706803894250',
    '🏷': '5886285355279193209',
    '🏷️': '5886285355279193209',
    '🕓': '5775896410780079073',
    '🖌': '6050679691004612757',
    '🖌️': '6050679691004612757',
    '🔡': '5771851822897566479',
    '↔': '5778479949572738874',
    '↔️': '5778479949572738874',
    '🪙': '5904462880941545555',
    '🏧': '5879814368572478751',
    '🔨': '5940433880585605708',
    '🔄': '5345906554510012647',
    # Дополнительные психологически близкие эмодзи к набору
    '🟢': '5870633910337015697',
    '🔴': '5870657884844462243',
    '🚀': '5963103826075456248',
    '⏳': '5983150113483134607',
}

# Эмодзи, отсортированные по длине (для корректной обработки vs селекторов VS16)
_PREMIUM_EMOJI_SORTED = sorted(PREMIUM_EMOJI_MAP.keys(), key=len, reverse=True)


def with_premium(text):
    """Заменяет известные эмодзи в строке на premium custom emoji HTML-теги.

    Для отображения требуется parse_mode='HTML'. Если эмодзи не из набора —
    остаётся без изменений.
    """
    if not text:
        return text
    result = []
    i = 0
    n = len(text)
    while i < n:
        # Не обрабатываем содержимое уже существующих <tg-emoji ...>...</tg-emoji>
        if text.startswith('<tg-emoji ', i):
            end = text.find('</tg-emoji>', i)
            if end != -1:
                end += len('</tg-emoji>')
                result.append(text[i:end])
                i = end
                continue
        matched = False
        for emoji in _PREMIUM_EMOJI_SORTED:
            if text.startswith(emoji, i):
                eid = PREMIUM_EMOJI_MAP[emoji]
                result.append(f'<tg-emoji emoji-id="{eid}">{emoji}</tg-emoji>')
                i += len(emoji)
                matched = True
                break
        if not matched:
            result.append(text[i])
            i += 1
    return ''.join(result)


def install_premium_emoji_filter(application):
    """Авто-замена обычных эмодзи на premium в сообщениях бота.

    Перехватывает bot.send_message и bot.edit_message_text — оборачивает
    text через with_premium() и принудительно ставит parse_mode='HTML'.
    """
    bot = application.bot

    original_send_message = bot.send_message
    original_edit_message_text = bot.edit_message_text

    async def send_message_patched(*args, **kwargs):
        if 'text' in kwargs and kwargs['text']:
            kwargs['text'] = with_premium(kwargs['text'])
            kwargs.setdefault('parse_mode', 'HTML')
        elif len(args) >= 2 and args[1]:
            args = list(args)
            args[1] = with_premium(args[1])
            kwargs.setdefault('parse_mode', 'HTML')
            args = tuple(args)
        return await original_send_message(*args, **kwargs)

    async def edit_message_text_patched(*args, **kwargs):
        if 'text' in kwargs and kwargs['text']:
            kwargs['text'] = with_premium(kwargs['text'])
            kwargs.setdefault('parse_mode', 'HTML')
        elif args and args[0]:
            args = list(args)
            args[0] = with_premium(args[0])
            kwargs.setdefault('parse_mode', 'HTML')
            args = tuple(args)
        return await original_edit_message_text(*args, **kwargs)

    bot.send_message = send_message_patched
    bot.edit_message_text = edit_message_text_patched


# ==================== PER-USER ХРАНИЛИЩЕ ====================

def user_data_dir(user_id):
    """Возвращает директорию данных пользователя (создаёт при необходимости)."""
    p = DATA_DIR / str(user_id)
    p.mkdir(parents=True, exist_ok=True)
    (p / SESSIONS_DIRNAME).mkdir(exist_ok=True)
    return p


def user_accounts_path(user_id):
    return user_data_dir(user_id) / ACCOUNTS_FILENAME


def user_scenarios_path(user_id):
    return user_data_dir(user_id) / SCENARIOS_FILENAME


def user_config_path(user_id):
    return user_data_dir(user_id) / CONFIG_FILENAME


def user_session_path(user_id, session_name):
    """Полный путь к файлу telethon-сессии для пользователя."""
    return str(user_data_dir(user_id) / SESSIONS_DIRNAME / session_name)


def make_session_name(user_id, phone):
    """Генерирует уникальное имя сессии (включая user_id для изоляции)."""
    safe_phone = phone.replace('+', '').replace(' ', '')
    return f"u{user_id}_session_{safe_phone}"


def find_account_owner(session_name):
    """Ищет владельца сессии среди активных. None если нет."""
    session = active_sessions.get(session_name)
    if session is not None:
        return getattr(session, 'owner_id', None)
    return None


def migrate_legacy_data():
    """Одноразовая миграция: переносит legacy-файлы в каталог MAIN_ADMIN_ID."""
    user_dir = user_data_dir(MAIN_ADMIN_ID)

    legacy_pairs = [
        (LEGACY_ACCOUNTS_FILE, user_dir / ACCOUNTS_FILENAME),
        (LEGACY_SCENARIOS_FILE, user_dir / SCENARIOS_FILENAME),
        (LEGACY_CONFIG_FILE, user_dir / CONFIG_FILENAME),
    ]

    for src, dst in legacy_pairs:
        try:
            if os.path.exists(src) and not dst.exists():
                shutil.move(src, str(dst))
                print(f"📦 Перенесено: {src} -> {dst}")
        except Exception as e:
            print(f"⚠️ Не удалось перенести {src}: {e}")

    # Старые telethon-сессии в корне (session_<phone>.session*) — переносим
    sessions_dst = user_dir / SESSIONS_DIRNAME
    sessions_dst.mkdir(exist_ok=True)
    try:
        for f in Path('.').glob('session_*.session*'):
            target = sessions_dst / f.name
            if not target.exists():
                shutil.move(str(f), str(target))
                print(f"📦 Перенесена сессия: {f.name}")
    except Exception as e:
        print(f"⚠️ Ошибка переноса telethon-сессий: {e}")

    # Если в legacy-accounts были аккаунты со старым session_name — оставляем
    # session_name как есть (файл уже лежит в sessions_dst и достижим по пути).


# ==================== ФУНКЦИИ ПОЛЬЗОВАТЕЛЕЙ ====================

def load_users():
    """Загружает список разрешенных пользователей"""
    global allowed_users
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            allowed_users = data.get('users', [MAIN_ADMIN_ID])
    else:
        allowed_users = [MAIN_ADMIN_ID]
        save_users()
    return allowed_users

def save_users():
    """Сохраняет список пользователей"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump({'users': allowed_users}, f, ensure_ascii=False, indent=2)

def is_allowed(user_id):
    """Проверяет, разрешен ли доступ пользователю"""
    return user_id in allowed_users

# ==================== АВТОПРОВЕРКА СЕССИЙ ====================

async def check_sessions_task():
    """Фоновая задача проверки сессий каждый час (для каждого пользователя отдельно)."""
    while True:
        await asyncio.sleep(3600)  # 1 час

        print(f"\n🔍 [{datetime.now().strftime('%H:%M:%S')}] Автопроверка сессий...")

        for owner_id in list(allowed_users):
            accounts = load_accounts(owner_id)
            inactive_accounts = []

            for acc in accounts:
                session_name = acc['session_name']

                # Проверяем, активна ли сессия
                if session_name not in active_sessions:
                    inactive_accounts.append(acc['phone'])
                    continue

                # Проверяем подключение
                session = active_sessions[session_name]
                try:
                    if not session.client.is_connected():
                        inactive_accounts.append(acc['phone'])
                        print(f"⚠️ [u{owner_id}] Сессия {acc['phone']} не подключена")
                except Exception as e:
                    inactive_accounts.append(acc['phone'])
                    print(f"⚠️ [u{owner_id}] Ошибка проверки {acc['phone']}: {e}")

            # Отправляем уведомление владельцу
            if inactive_accounts:
                notification = (
                    f"⚠️ <b>НЕАКТИВНЫЕ СЕССИИ ОБНАРУЖЕНЫ!</b>\n\n"
                    f"Время проверки: {datetime.now().strftime('%H:%M:%S')}\n"
                    f"Неактивных: {len(inactive_accounts)}\n\n"
                    f"📱 Аккаунты:\n" +
                    "\n".join([f"• {phone}" for phone in inactive_accounts])
                )
                await send_admin_notification(notification, owner_id=owner_id)
                print(f"📨 [u{owner_id}] Уведомление о {len(inactive_accounts)} неактивных сессиях")
            elif accounts:
                print(f"✅ [u{owner_id}] Все сессии активны ({len(accounts)} шт)")

# ==================== USERBOT КЛАСС ====================

class UserbotSession:
    def __init__(self, api_id, api_hash, phone, session_name, owner_id):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_name = session_name
        self.owner_id = owner_id
        # Файл telethon-сессии хранится в каталоге владельца
        session_path = user_session_path(owner_id, session_name)
        self.client = TelegramClient(session_path, api_id, api_hash)
        self.active_dialogs = 0
        self.completed_dialogs = 0
        self.failed_dialogs = 0
        self.is_mailing = False
    
    async def setup_message_handler(self):
        """Настройка обработчика входящих сообщений"""
        @self.client.on(events.NewMessage(incoming=True))
        async def handler(event):
            if event.is_channel:
                return
            
            try:
                sender = await event.get_sender()
                
                if sender.id == (await self.client.get_me()).id:
                    return
                
                sender_id = sender.id
                username = f"@{sender.username}" if sender.username else sender.first_name
                message_text = event.text[:200] if event.text else "[медиа/стикер]"
                
                reply_id = f"{self.session_name}_{sender_id}"
                
                reply_cache[reply_id] = {
                    'session_name': self.session_name,
                    'sender_id': sender_id,
                    'username': username,
                    'owner_id': self.owner_id,
                }
                
                keyboard = [
                    [InlineKeyboardButton("💬 Ответить", callback_data=f"reply_{reply_id}")]
                ]
                
                notification = (
                    f"💬 <b>Новое сообщение!</b>\n\n"
                    f"📱 Аккаунт: <code>{self.phone}</code>\n"
                    f"👤 От: {username}\n"
                    f"💭 Сообщение:\n{message_text}"
                )
                
                # Уведомление получает только владелец аккаунта
                await send_admin_notification(
                    notification,
                    InlineKeyboardMarkup(keyboard),
                    owner_id=self.owner_id,
                )
                
                print(f"📨 [{self.phone}] Получено сообщение от {username}")
                
            except Exception as e:
                print(f"Ошибка обработки входящего сообщения: {e}")
    
    async def send_reply(self, user_id, message):
        """Отправляет ответ пользователю"""
        try:
            await self.client.send_message(user_id, message)
            return True
        except Exception as e:
            print(f"Ошибка отправки ответа: {e}")
            return False
    
    async def check_spam_status(self):
        """Проверяет статус спам-бана в @SpamBot"""
        try:
            print(f"\n🔍 [{self.session_name}] Проверка спам-бана...")
            spam_bot = await self.client.get_entity('@SpamBot')
            
            await self.client.send_message(spam_bot, '/start')
            await asyncio.sleep(3)
            
            messages = await self.client.get_messages(spam_bot, limit=1)
            
            if messages:
                response = messages[0].text.lower()
                
                spam_keywords = ['limited', 'restricted', 'banned', 'ограничен', 'забанен']
                
                for keyword in spam_keywords:
                    if keyword in response:
                        notification = (
                            f"⚠️ <b>СПАМБЛОК ОБНАРУЖЕН!</b>\n\n"
                            f"Аккаунт: {self.phone}\n"
                            f"Статус: Ограничен\n\n"
                            f"/start отправлен в @SpamBot"
                        )
                        await send_admin_notification(notification)
                        print(f"⚠️ Обнаружен спамблок на {self.phone}")
                        return True
            
            print(f"✅ /start отправлен в @SpamBot")
            return True
            
        except Exception as e:
            print(f"⚠️ Ошибка проверки @SpamBot: {str(e)}")
            return True
        
    async def execute_scenario_step(self, user, step):
        """Выполняет один шаг сценария"""
        step_type = step['type']
        
        try:
            if step_type == 'greeting':
                greeting = random.choice(GREETINGS)
                await self.client.send_message(user, greeting)
                print(f"  ✓ Приветствие: {greeting}")
                
            elif step_type == 'text':
                await self.client.send_message(user, step['content'])
                print(f"  ✓ Текст отправлен: {step['content'][:50]}...")
                
            elif step_type == 'sticker':
                await self.client.send_file(user, step['file_id'])
                print(f"  ✓ Стикер отправлен")
                
            elif step_type == 'forward_from_bot':
                bot_username = step['bot_username']
                command = step.get('command', '')
                
                bot = await self.client.get_entity(bot_username)
                await self.client.send_message(bot, command)
                print(f"  ✓ Отправлена команда в {bot_username}: {command}")
                
                await asyncio.sleep(3)
                
                messages = await self.client.get_messages(bot, limit=1)
                if messages:
                    await self.client.forward_messages(user, messages[0])
                    print(f"  ✓ Переслано сообщение от {bot_username}")
            
            elif step_type == 'forward_from_channel':
                post_link = step['post_link']
                
                try:
                    if '/c/' in post_link:
                        parts = post_link.split('/')
                        channel_id = int('-100' + parts[-2])
                        message_id = int(parts[-1])
                    else:
                        parts = post_link.split('/')
                        channel_username = parts[-2]
                        message_id = int(parts[-1])
                        channel = await self.client.get_entity(channel_username)
                        channel_id = channel.id
                    
                    await self.client.forward_messages(user, message_id, channel_id)
                    print(f"  ✓ Переслан пост из канала")
                    
                except Exception as e:
                    print(f"  ❌ Ошибка пересылки поста: {e}")
                    return False
                    
            elif step_type == 'inline':
                bot_username = step['bot_username']
                query = step.get('query', '')
                result_index = step.get('result_index', 0)
                
                inline_results = await self.client.inline_query(bot_username, query)
                
                if len(inline_results) > result_index:
                    await inline_results[result_index].click(user)
                    print(f"  ✓ Инлайн отправлен от {bot_username} (результат #{result_index})")
                else:
                    print(f"  ⚠️ Недостаточно инлайн-результатов")
                    
            elif step_type == 'delay':
                delay = step.get('seconds', 2)
                await asyncio.sleep(delay)
                print(f"  ⏳ Пауза {delay} сек")
                
            return True
        
        except FloodWaitError as e:
            print(f"  ❌ FloodWait на шаге {step_type}: {e.seconds} сек")
            
            notification = (
                f"⚠️ <b>FloodWait!</b>\n\n"
                f"Аккаунт: {self.phone}\n"
                f"Ожидание: {e.seconds} сек"
            )
            await send_admin_notification(notification)
            return False
            
        except Exception as e:
            print(f"  ❌ Ошибка на шаге {step_type}: {str(e)}")
            return False
    
    async def send_to_user(self, username, scenario):
        """Отправляет сообщения одному пользователю по сценарию"""
        global global_mailing_stop
        
        if global_mailing_stop:
            print(f"⛔ Глобальная остановка рассылки")
            return False
        
        if mailing_paused.get(self.session_name, False):
            print(f"⏸️ Рассылка приостановлена для {self.phone}")
            return False
        
        try:
            clean_username = username.lstrip('@')
            print(f"\n{'='*50}")
            print(f"[{self.session_name}] Начинаю: @{clean_username}")
            print(f"{'='*50}")
            
            self.active_dialogs += 1
            
            user = await self.client.get_entity(clean_username)
            
            for i, step in enumerate(scenario, 1):
                if global_mailing_stop or mailing_paused.get(self.session_name, False):
                    print(f"⛔ Рассылка остановлена")
                    self.active_dialogs -= 1
                    return False
                
                print(f"\n  Шаг {i}/{len(scenario)}: {step['type']}")
                
                step_result = await self.execute_scenario_step(user, step)
                
                if not step_result:
                    print(f"\n⚠️ Остановка сценария из-за ошибки на шаге {i}")
                    self.active_dialogs -= 1
                    self.failed_dialogs += 1
                    return False
            
            self.active_dialogs -= 1
            self.completed_dialogs += 1
            
            print(f"\n✅ Успешно завершено для @{clean_username}")
            return True
            
        except (UserPrivacyRestrictedError, ChatWriteForbiddenError, UserIsBlockedError) as e:
            self.active_dialogs -= 1
            self.failed_dialogs += 1
            print(f"⏭️ ПРОПУЩЕН: {type(e).__name__}")
            return False
            
        except FloodWaitError as e:
            self.active_dialogs -= 1
            self.failed_dialogs += 1
            print(f"⚠️ FloodWait: {e.seconds} сек - ПРОПУЩЕН")
            return False
            
        except RPCError as e:
            self.active_dialogs -= 1
            self.failed_dialogs += 1
            error_str = str(e)
            
            if 'PAYMENT_REQUIRED' in error_str or 'PREMIUM_ACCOUNT_REQUIRED' in error_str:
                print(f"⏭️ ПРОПУЩЕН: требуется оплата ⭐ (платный аккаунт)")
                return False
            else:
                print(f"❌ RPC: {error_str}")
                return False
            
        except Exception as e:
            self.active_dialogs -= 1
            self.failed_dialogs += 1
            print(f"❌ Ошибка: {str(e)}")
            return False

    async def start(self):
        await self.client.start(phone=self.phone)
        me = await self.client.get_me()
        
        await self.setup_message_handler()
        
        print(f"✅ [{self.session_name}] Авторизован: {me.first_name}")
        return me

    async def disconnect(self):
        await self.client.disconnect()
        
    def get_stats(self):
        return {
            'active': self.active_dialogs,
            'completed': self.completed_dialogs,
            'failed': self.failed_dialogs,
            'phone': self.phone
        }

# ==================== ФУНКЦИИ ДАННЫХ ====================

def load_accounts(user_id):
    """Загружает аккаунты пользователя."""
    path = user_accounts_path(user_id)
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_accounts(user_id, accounts):
    """Сохраняет аккаунты пользователя."""
    with open(user_accounts_path(user_id), 'w', encoding='utf-8') as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)

def load_scenarios(user_id):
    """Загружает сценарии пользователя."""
    path = user_scenarios_path(user_id)
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_scenarios(user_id, scenarios):
    """Сохраняет сценарии пользователя."""
    with open(user_scenarios_path(user_id), 'w', encoding='utf-8') as f:
        json.dump(scenarios, f, ensure_ascii=False, indent=2)

def load_config(user_id):
    """Загружает настройки пользователя."""
    path = user_config_path(user_id)
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'delay': 30}

def save_config(user_id, config):
    """Сохраняет настройки пользователя."""
    with open(user_config_path(user_id), 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

async def send_admin_notification(text, reply_markup=None, owner_id=None):
    """Отправляет уведомление.

    Если задан owner_id — только владельцу. Иначе главному админу.
    Это важно: уведомления о входящих сообщениях аккаунта должны
    приходить только владельцу аккаунта.
    """
    global admin_bot_app
    if not admin_bot_app:
        return

    target_user_id = owner_id if owner_id is not None else MAIN_ADMIN_ID
    try:
        await admin_bot_app.bot.send_message(
            chat_id=target_user_id,
            text=text,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Ошибка отправки уведомления: {e}")

async def load_session(session_data, owner_id):
    session = UserbotSession(
        session_data['api_id'],
        session_data['api_hash'],
        session_data['phone'],
        session_data['session_name'],
        owner_id,
    )
    await session.start()
    active_sessions[session_data['session_name']] = session
    return session

async def send_bulk(session, usernames, scenario, delay=None):
    """Массовая рассылка с проверкой спам-бана"""
    global global_mailing_stop
    
    session.is_mailing = True
    
    await session.check_spam_status()
    
    if delay is None:
        config = load_config(session.owner_id)
        delay = config.get('delay', 30)
    
    success = 0
    skipped = 0
    
    for i, username in enumerate(usernames, 1):
        if global_mailing_stop:
            print(f"\n⛔ Глобальная остановка рассылки активирована")
            break
        
        if mailing_paused.get(session.session_name, False):
            print(f"\n⏸️ Рассылка приостановлена для {session.phone}")
            break
        
        print(f"\n[{i}/{len(usernames)}] Обрабатываю @{username}")
        
        result = await session.send_to_user(username, scenario)
        
        if result:
            success += 1
            if i < len(usernames):
                print(f"\n⏳ Пауза {delay} секунд...")
                
                for _ in range(delay):
                    if global_mailing_stop or mailing_paused.get(session.session_name, False):
                        print(f"⛔ Остановка во время задержки")
                        break
                    await asyncio.sleep(1)
        else:
            skipped += 1
            print(f"⏩ Сразу переходим к следующему пользователю")
    
    session.is_mailing = False
    
    return {'success': success, 'skipped': skipped, 'total': len(usernames)}

async def send_bulk_all_accounts(sessions, usernames, scenario, delay=None):
    """Рассылка со всех аккаунтов одновременно"""
    global global_mailing_stop
    
    if delay is None:
        # Все сессии в этом списке принадлежат одному пользователю
        owner_id = sessions[0].owner_id if sessions else MAIN_ADMIN_ID
        config = load_config(owner_id)
        delay = config.get('delay', 30)
    
    users_per_account = len(usernames) // len(sessions)
    remainder = len(usernames) % len(sessions)
    
    tasks = []
    start_idx = 0
    
    for i, session in enumerate(sessions):
        count = users_per_account + (1 if i < remainder else 0)
        end_idx = start_idx + count
        
        users_subset = usernames[start_idx:end_idx]
        
        if users_subset:
            print(f"📱 {session.phone}: назначено {len(users_subset)} пользователей")
            task = asyncio.create_task(send_bulk(session, users_subset, scenario, delay))
            tasks.append(task)
        
        start_idx = end_idx
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    total_success = 0
    total_skipped = 0
    total_total = 0
    
    for result in results:
        if isinstance(result, dict):
            total_success += result['success']
            total_skipped += result['skipped']
            total_total += result['total']
    
    return {
        'success': total_success,
        'skipped': total_skipped,
        'total': total_total,
        'accounts_used': len(sessions)
    }

# ==================== КЛАВИАТУРЫ ====================

def main_menu_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("📱 Аккаунты", callback_data="menu_accounts"),
         InlineKeyboardButton("📋 Сценарии", callback_data="menu_scenarios")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings"),
         InlineKeyboardButton("📊 Статистика", callback_data="menu_stats")],
        [InlineKeyboardButton("🚀 Рассылка", callback_data="menu_mailing")]
    ]
    
    # Только главный админ видит управление пользователями
    if user_id == MAIN_ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👥 Пользователи", callback_data="menu_users")])
    
    return InlineKeyboardMarkup(keyboard)

def users_keyboard():
    """Клавиатура управления пользователями"""
    keyboard = []
    
    for user_id in allowed_users:
        if user_id == MAIN_ADMIN_ID:
            keyboard.append([InlineKeyboardButton(
                f"👑 {user_id} (Главный админ)", 
                callback_data=f"user_info_{user_id}"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                f"👤 {user_id}", 
                callback_data=f"user_{user_id}"
            )])
    
    keyboard.append([InlineKeyboardButton("➕ Добавить пользователя", callback_data="add_user")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main")])
    return InlineKeyboardMarkup(keyboard)

def user_detail_keyboard(user_id):
    """Клавиатура для конкретного пользователя"""
    keyboard = [
        [InlineKeyboardButton("🗑️ Удалить доступ", callback_data=f"delete_user_{user_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_users")]
    ]
    return InlineKeyboardMarkup(keyboard)

def accounts_keyboard(accounts):
    keyboard = []
    for i, acc in enumerate(accounts):
        status = "🟢" if acc['session_name'] in active_sessions else "🔴"
        keyboard.append([InlineKeyboardButton(
            f"{status} {acc['phone']}", 
            callback_data=f"acc_{i}"
        )])
    keyboard.append([InlineKeyboardButton("➕ Добавить аккаунт", callback_data="add_account")])
    keyboard.append([InlineKeyboardButton("⛔ ОСТАНОВИТЬ ВСЕ", callback_data="stop_all_mailing")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main")])
    return InlineKeyboardMarkup(keyboard)

def account_detail_keyboard(acc_id, session_name):
    is_paused = mailing_paused.get(session_name, False)
    pause_text = "▶️ Продолжить" if is_paused else "⏸️ Приостановить"
    
    keyboard = [
        [InlineKeyboardButton(pause_text, callback_data=f"pause_acc_{acc_id}")],
        [InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_acc_{acc_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_accounts")]
    ]
    return InlineKeyboardMarkup(keyboard)

def scenarios_keyboard(scenarios):
    keyboard = []
    for i, scenario in enumerate(scenarios):
        keyboard.append([InlineKeyboardButton(
            f"📋 {scenario['name']} ({len(scenario['steps'])} шагов)", 
            callback_data=f"scenario_{i}"
        )])
    keyboard.append([InlineKeyboardButton("➕ Создать сценарий", callback_data="create_scenario")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main")])
    return InlineKeyboardMarkup(keyboard)

def scenario_detail_keyboard(scenario_id):
    keyboard = [
        [InlineKeyboardButton("➕ Добавить шаг", callback_data=f"add_step_{scenario_id}")],
        [InlineKeyboardButton("👁️ Просмотреть", callback_data=f"view_scenario_{scenario_id}")],
        [InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_scenario_{scenario_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_scenarios")]
    ]
    return InlineKeyboardMarkup(keyboard)

def step_type_keyboard(scenario_id):
    keyboard = [
        [InlineKeyboardButton("👋 Приветствие", callback_data=f"step_greeting_{scenario_id}"),
         InlineKeyboardButton("💬 Текст", callback_data=f"step_text_{scenario_id}")],
        [InlineKeyboardButton("🎨 Стикер", callback_data=f"step_sticker_{scenario_id}"),
         InlineKeyboardButton("🔄 Пересылка с /pyid", callback_data=f"step_forward_{scenario_id}")],
        [InlineKeyboardButton("📢 Пост из канала", callback_data=f"step_channel_{scenario_id}"),
         InlineKeyboardButton("🤖 Инлайн", callback_data=f"step_inline_{scenario_id}")],
        [InlineKeyboardButton("⏱️ Пауза", callback_data=f"step_delay_{scenario_id}")],
        [InlineKeyboardButton("◀️ Отмена", callback_data=f"scenario_{scenario_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def mailing_account_selection_keyboard(accounts, for_all=False):
    """Клавиатура выбора аккаунта с опцией 'Все аккаунты'"""
    keyboard = []
    
    active_count = len([a for a in accounts if a['session_name'] in active_sessions])
    if active_count > 1:
        keyboard.append([InlineKeyboardButton(
            f"🚀 Все аккаунты сразу ({active_count} шт)", 
            callback_data="mailing_account_all"
        )])
    
    for i, acc in enumerate(accounts):
        if acc['session_name'] in active_sessions:
            keyboard.append([InlineKeyboardButton(
                f"📱 {acc['phone']}", 
                callback_data=f"mailing_account_{i}"
            )])
    
    keyboard.append([InlineKeyboardButton("◀️ Отмена", callback_data="main")])
    return InlineKeyboardMarkup(keyboard)

# ==================== ОБРАБОТЧИКИ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_allowed(user_id):
        await update.message.reply_text(
            "❌ <b>Доступ запрещен</b>\n\n"
            "У вас нет доступа к этому боту.",
            parse_mode='HTML'
        )
        return
    
    role = "Главный админ" if user_id == MAIN_ADMIN_ID else "Пользователь"
    
    await update.message.reply_text(
        f"🎛️ <b>Панель управления рассылкой</b>\n\n"
        f"Ваша роль: {role}\n"
        f"Выберите раздел:",
        reply_markup=main_menu_keyboard(user_id),
        parse_mode='HTML'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_mailing_stop
    
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not is_allowed(user_id):
        await query.edit_message_text("❌ Доступ запрещен")
        return
    
    data = query.data
    
    # ==================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ====================
    
    if data == "menu_users":
        if user_id != MAIN_ADMIN_ID:
            await query.answer("❌ Только для главного админа", show_alert=True)
            return
        
        await query.edit_message_text(
            f"👥 <b>Управление пользователями</b>\n\n"
            f"Всего пользователей: {len(allowed_users)}",
            reply_markup=users_keyboard(),
            parse_mode='HTML'
        )
    
    elif data == "add_user":
        if user_id != MAIN_ADMIN_ID:
            await query.answer("❌ Только для главного админа", show_alert=True)
            return
        
        user_states[user_id] = {'action': 'add_user'}
        await query.edit_message_text(
            "➕ <b>Добавление пользователя</b>\n\n"
            "Отправьте User ID нового пользователя:\n\n"
            "Чтобы узнать ID, используйте @userinfobot",
            parse_mode='HTML'
        )
    
    elif data.startswith("user_") and not data.startswith("user_info_"):
        if user_id != MAIN_ADMIN_ID:
            await query.answer("❌ Только для главного админа", show_alert=True)
            return
        
        target_user_id = int(data.split("_")[1])
        
        await query.edit_message_text(
            f"👤 <b>Пользователь</b>\n\n"
            f"User ID: <code>{target_user_id}</code>",
            reply_markup=user_detail_keyboard(target_user_id),
            parse_mode='HTML'
        )
    
    elif data.startswith("delete_user_"):
        if user_id != MAIN_ADMIN_ID:
            await query.answer("❌ Только для главного админа", show_alert=True)
            return
        
        target_user_id = int(data.split("_")[2])
        
        if target_user_id == MAIN_ADMIN_ID:
            await query.answer("❌ Нельзя удалить главного админа", show_alert=True)
            return
        
        allowed_users.remove(target_user_id)
        save_users()
        
        await query.edit_message_text(
            f"✅ Пользователь {target_user_id} удален",
            reply_markup=users_keyboard()
        )
    
    # ==================== ОСНОВНОЕ МЕНЮ ====================
    
    elif data.startswith("reply_"):
        reply_id = data.replace("reply_", "")
        
        if reply_id not in reply_cache:
            await query.edit_message_text(
                "❌ Сессия устарела. Попросите пользователя написать снова.",
                reply_markup=main_menu_keyboard(user_id)
            )
            return

        # Отвечать может только владелец аккаунта
        if reply_cache[reply_id].get('owner_id') != user_id:
            await query.answer("❌ Чужой аккаунт", show_alert=True)
            return

        user_states[user_id] = {
            'action': 'send_reply',
            'reply_id': reply_id
        }
        
        reply_info = reply_cache[reply_id]
        
        await query.edit_message_text(
            f"💬 <b>Ответ пользователю</b>\n\n"
            f"📱 Аккаунт: <code>{active_sessions[reply_info['session_name']].phone}</code>\n"
            f"👤 Кому: {reply_info['username']}\n\n"
            f"✍️ Напишите сообщение:",
            parse_mode='HTML'
        )
        return
    
    if data == "main":
        await query.edit_message_text(
            "🎛️ <b>Панель управления</b>\n\nВыберите раздел:",
            reply_markup=main_menu_keyboard(user_id),
            parse_mode='HTML'
        )
    
    elif data == "menu_accounts":
        accounts = load_accounts(user_id)
        active_count = len([a for a in accounts if a['session_name'] in active_sessions])
        
        await query.edit_message_text(
            f"📱 <b>Управление аккаунтами</b>\n\n"
            f"Всего: {len(accounts)}\n"
            f"Активных: {active_count}",
            reply_markup=accounts_keyboard(accounts),
            parse_mode='HTML'
        )
    
    elif data == "stop_all_mailing":
        global_mailing_stop = True

        # Останавливаем только свои сессии
        own_accounts = load_accounts(user_id)
        for acc in own_accounts:
            if acc['session_name'] in active_sessions:
                mailing_paused[acc['session_name']] = True

        await query.edit_message_text(
            "⛔ <b>ВСЕ РАССЫЛКИ ОСТАНОВЛЕНЫ!</b>\n\n"
            "Чтобы возобновить, снимите паузу с нужных аккаунтов.",
            reply_markup=accounts_keyboard(own_accounts),
            parse_mode='HTML'
        )
    
    elif data == "add_account":
        user_states[user_id] = {'action': 'add_account', 'step': 'api_id'}
        await query.edit_message_text(
            "➕ <b>Добавление аккаунта</b>\n\n"
            "Шаг 1/3: Отправьте API_ID:",
            parse_mode='HTML'
        )
    
    elif data.startswith("acc_"):
        acc_id = int(data.split("_")[1])
        accounts = load_accounts(user_id)
        acc = accounts[acc_id]
        
        is_active = acc['session_name'] in active_sessions
        status_text = "🟢 Активен" if is_active else "🔴 Неактивен"
        
        is_paused = mailing_paused.get(acc['session_name'], False)
        pause_status = "⏸️ Приостановлена" if is_paused else "▶️ Работает"
        
        await query.edit_message_text(
            f"📱 <b>Аккаунт</b>\n\n"
            f"Телефон: {acc['phone']}\n"
            f"Статус: {status_text}\n"
            f"Рассылка: {pause_status}",
            reply_markup=account_detail_keyboard(acc_id, acc['session_name']),
            parse_mode='HTML'
        )
    
    elif data.startswith("pause_acc_"):
        acc_id = int(data.split("_")[2])
        accounts = load_accounts(user_id)
        acc = accounts[acc_id]
        session_name = acc['session_name']
        
        current_state = mailing_paused.get(session_name, False)
        mailing_paused[session_name] = not current_state
        
        if not mailing_paused[session_name]:
            global_mailing_stop = False
        
        new_status = "⏸️ Приостановлена" if mailing_paused[session_name] else "▶️ Продолжена"
        
        await query.edit_message_text(
            f"✅ Рассылка {new_status}\n\n"
            f"Аккаунт: {acc['phone']}",
            reply_markup=account_detail_keyboard(acc_id, session_name)
        )
    
    elif data.startswith("delete_acc_"):
        acc_id = int(data.split("_")[2])
        accounts = load_accounts(user_id)
        deleted = accounts.pop(acc_id)
        save_accounts(user_id, accounts)
        
        if deleted['session_name'] in active_sessions:
            await active_sessions[deleted['session_name']].disconnect()
            del active_sessions[deleted['session_name']]
        
        await query.edit_message_text(
            f"✅ Аккаунт {deleted['phone']} удален",
            reply_markup=accounts_keyboard(accounts)
        )
    
    elif data == "menu_scenarios":
        scenarios = load_scenarios(user_id)
        await query.edit_message_text(
            f"📋 <b>Сценарии рассылки</b>\n\n"
            f"Всего сценариев: {len(scenarios)}",
            reply_markup=scenarios_keyboard(scenarios),
            parse_mode='HTML'
        )
    
    elif data == "create_scenario":
        user_states[user_id] = {'action': 'create_scenario'}
        await query.edit_message_text(
            "➕ <b>Создание сценария</b>\n\n"
            "Отправьте название сценария:",
            parse_mode='HTML'
        )
    
    elif data.startswith("scenario_") and "view_scenario" not in data and "delete_scenario" not in data:
        scenario_id = int(data.split("_")[1])
        scenarios = load_scenarios(user_id)
        scenario = scenarios[scenario_id]
        
        steps_text = "\n".join([
            f"{i+1}. {step['type']}" + 
            (f" - {step.get('content', '')[:30]}..." if 'content' in step else "")
            for i, step in enumerate(scenario['steps'])
        ]) or "Нет шагов"
        
        await query.edit_message_text(
            f"📋 <b>{scenario['name']}</b>\n\n"
            f"Шагов: {len(scenario['steps'])}\n\n"
            f"<b>Список шагов:</b>\n{steps_text}",
            reply_markup=scenario_detail_keyboard(scenario_id),
            parse_mode='HTML'
        )
    
    elif data.startswith("add_step_"):
        scenario_id = int(data.split("_")[2])
        await query.edit_message_text(
            "➕ <b>Добавление шага</b>\n\n"
            "Выберите тип шага:",
            reply_markup=step_type_keyboard(scenario_id),
            parse_mode='HTML'
        )
    
    elif data.startswith("step_greeting_"):
        scenario_id = int(data.split("_")[2])
        scenarios = load_scenarios(user_id)
        scenarios[scenario_id]['steps'].append({'type': 'greeting'})
        save_scenarios(user_id, scenarios)
        
        await query.edit_message_text(
            "✅ Шаг 'Приветствие' добавлен",
            reply_markup=scenario_detail_keyboard(scenario_id)
        )
    
    elif data.startswith("step_text_"):
        scenario_id = int(data.split("_")[2])
        user_states[user_id] = {'action': 'add_step_text', 'scenario_id': scenario_id}
        await query.edit_message_text("💬 Отправьте текст сообщения:")
    
    elif data.startswith("step_sticker_"):
        scenario_id = int(data.split("_")[2])
        user_states[user_id] = {'action': 'add_step_sticker', 'scenario_id': scenario_id}
        await query.edit_message_text("🎨 Отправьте стикер:")
    
    elif data.startswith("step_forward_"):
        scenario_id = int(data.split("_")[2])
        user_states[user_id] = {
            'action': 'add_step_forward',
            'scenario_id': scenario_id,
            'step': 'bot'
        }
        await query.edit_message_text(
            "🔄 <b>Пересылка с /pyid</b>\n\n"
            "Шаг 1/2: Отправьте username бота:",
            parse_mode='HTML'
        )
    
    elif data.startswith("step_channel_"):
        scenario_id = int(data.split("_")[2])
        user_states[user_id] = {'action': 'add_step_channel', 'scenario_id': scenario_id}
        await query.edit_message_text(
            "📢 <b>Пересылка поста из канала</b>\n\n"
            "Отправьте ссылку на пост:\n"
            "Пример: https://t.me/channel/123",
            parse_mode='HTML'
        )
    
    elif data.startswith("step_inline_"):
        scenario_id = int(data.split("_")[2])
        user_states[user_id] = {
            'action': 'add_step_inline',
            'scenario_id': scenario_id,
            'step': 'bot'
        }
        await query.edit_message_text(
            "🤖 <b>Инлайн-сообщение</b>\n\n"
            "Шаг 1/3: Отправьте username инлайн-бота:",
            parse_mode='HTML'
        )
    
    elif data.startswith("step_delay_"):
        scenario_id = int(data.split("_")[2])
        user_states[user_id] = {'action': 'add_step_delay', 'scenario_id': scenario_id}
        await query.edit_message_text("⏱️ Отправьте количество секунд (например: 5):")
    
    elif data.startswith("view_scenario_"):
        scenario_id = int(data.split("_")[2])
        scenarios = load_scenarios(user_id)
        scenario = scenarios[scenario_id]
        
        steps_detail = ""
        for i, step in enumerate(scenario['steps'], 1):
            steps_detail += f"\n<b>{i}. {step['type'].upper()}</b>\n"
            
            if step['type'] == 'text':
                steps_detail += f"   {step['content'][:50]}...\n"
            elif step['type'] == 'forward_from_bot':
                steps_detail += f"   Бот: {step['bot_username']}\n"
                steps_detail += f"   Команда: {step.get('command', '')}\n"
            elif step['type'] == 'forward_from_channel':
                steps_detail += f"   Ссылка: {step['post_link'][:40]}...\n"
            elif step['type'] == 'inline':
                steps_detail += f"   Бот: {step['bot_username']}\n"
                steps_detail += f"   Результат: #{step.get('result_index', 0)}\n"
            elif step['type'] == 'delay':
                steps_detail += f"   {step.get('seconds', 2)} сек\n"
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"scenario_{scenario_id}")]]
        
        await query.edit_message_text(
            f"📋 <b>{scenario['name']}</b>\n{steps_detail}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    elif data.startswith("delete_scenario_"):
        scenario_id = int(data.split("_")[2])
        scenarios = load_scenarios(user_id)
        deleted = scenarios.pop(scenario_id)
        save_scenarios(user_id, scenarios)
        
        await query.edit_message_text(
            f"✅ Сценарий '{deleted['name']}' удален",
            reply_markup=scenarios_keyboard(scenarios)
        )
    
    elif data == "menu_stats":
        accounts = load_accounts(user_id)
        total_active = 0
        total_completed = 0
        total_failed = 0
        
        stats_text = "📊 <b>Статистика</b>\n\n"
        
        for acc in accounts:
            if acc['session_name'] in active_sessions:
                session = active_sessions[acc['session_name']]
                stats = session.get_stats()
                stats_text += f"📱 {acc['phone']}:\n"
                stats_text += f"   🟢 Активные: {stats['active']}\n"
                stats_text += f"   ✅ Завершенные: {stats['completed']}\n"
                stats_text += f"   ❌ Неудачные: {stats['failed']}\n\n"
                total_active += stats['active']
                total_completed += stats['completed']
                total_failed += stats['failed']
        
        stats_text += f"<b>Итого:</b>\n"
        stats_text += f"🟢 Активные: {total_active}\n"
        stats_text += f"✅ Завершенные: {total_completed}\n"
        stats_text += f"❌ Неудачные: {total_failed}"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="menu_stats")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main")]
        ]
        
        await query.edit_message_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

    elif data == "menu_settings":
        config = load_config(user_id)
        delay = config.get('delay', 30)
        
        keyboard = [
            [InlineKeyboardButton("⏱️ Изменить задержку", callback_data="change_delay")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main")]
        ]
        
        await query.edit_message_text(
            f"⚙️ <b>Настройки</b>\n\n"
            f"⏱️ Задержка между сообщениями: <b>{delay} сек</b>\n\n"
            f"Это пауза между отправкой сообщений разным пользователям.\n"
            f"Рекомендуется: 30-60 секунд\n\n"
            f"🔍 Автопроверка сессий: <b>Каждый час</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    elif data == "change_delay":
        user_states[user_id] = {'action': 'set_delay'}
        await query.edit_message_text(
            "⏱️ <b>Настройка задержки</b>\n\n"
            "Введите задержку в секундах (рекомендуется 30-60):\n\n"
            "Например: 30",
            parse_mode='HTML'
        )
    
    elif data == "menu_mailing":
        scenarios = load_scenarios(user_id)
        
        if not scenarios:
            await query.edit_message_text(
                "❌ Сначала создайте сценарий!",
                reply_markup=main_menu_keyboard(user_id)
            )
            return
        
        global_mailing_stop = False
        
        user_states[user_id] = {'action': 'start_mailing', 'step': 'usernames'}
        await query.edit_message_text(
            "🚀 <b>Рассылка</b>\n\n"
            "Шаг 1/3: Отправьте список username:\n\n"
            "@user1\n@user2\n@user3",
            parse_mode='HTML'
        )
    
    elif data.startswith("mailing_scenario_"):
        scenario_id = int(data.split("_")[2])
        
        if user_id not in user_states:
            return
        
        state = user_states[user_id]
        state['scenario_id'] = scenario_id
        
        accounts = load_accounts(user_id)
        
        await query.edit_message_text(
            "Шаг 3/3: Выберите аккаунт:",
            reply_markup=mailing_account_selection_keyboard(accounts)
        )
    
    elif data == "mailing_account_all":
        if user_id not in user_states:
            return
        
        state = user_states[user_id]
        usernames = state['usernames']
        scenario_id = state['scenario_id']
        
        accounts = load_accounts(user_id)
        scenarios = load_scenarios(user_id)
        config = load_config(user_id)
        
        scenario = scenarios[scenario_id]
        delay = config.get('delay', 30)
        
        active_account_sessions = [
            active_sessions[acc['session_name']] 
            for acc in accounts 
            if acc['session_name'] in active_sessions
        ]
        
        if not active_account_sessions:
            await query.edit_message_text(
                "❌ Нет активных аккаунтов!",
                reply_markup=main_menu_keyboard(user_id)
            )
            return
        
        for session in active_account_sessions:
            mailing_paused[session.session_name] = False
        
        await query.edit_message_text(
            f"🚀 <b>МАССОВАЯ РАССЫЛКА ЗАПУЩЕНА!</b>\n\n"
            f"👥 Аккаунтов: {len(active_account_sessions)}\n"
            f"📝 Сценарий: {scenario['name']}\n"
            f"📊 Пользователей: {len(usernames)}\n"
            f"⏱️ Задержка: {delay} сек\n\n"
            f"🔍 Проверка спам-банов...",
            parse_mode='HTML'
        )
        
        asyncio.create_task(run_mailing_task_all(query, active_account_sessions, usernames, scenario))
        del user_states[user_id]
    
    elif data.startswith("mailing_account_"):
        acc_id = int(data.split("_")[2])
        
        if user_id not in user_states:
            return
        
        state = user_states[user_id]
        usernames = state['usernames']
        scenario_id = state['scenario_id']
        
        accounts = load_accounts(user_id)
        scenarios = load_scenarios(user_id)
        config = load_config(user_id)
        
        account = accounts[acc_id]
        scenario = scenarios[scenario_id]
        session = active_sessions[account['session_name']]
        delay = config.get('delay', 30)
        
        mailing_paused[account['session_name']] = False
        
        await query.edit_message_text(
            f"🚀 <b>Рассылка запущена!</b>\n\n"
            f"Аккаунт: {account['phone']}\n"
            f"Сценарий: {scenario['name']}\n"
            f"Пользователей: {len(usernames)}\n"
            f"⏱️ Задержка: {delay} сек\n\n"
            f"🔍 Проверка спам-бана...",
            parse_mode='HTML'
        )
        
        asyncio.create_task(run_mailing_task(query, session, usernames, scenario))
        del user_states[user_id]

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_allowed(user_id):
        return
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    action = state['action']
    
    # Добавление пользователя
    if action == 'add_user':
        if user_id != MAIN_ADMIN_ID:
            return
        
        try:
            new_user_id = int(update.message.text)
            
            if new_user_id in allowed_users:
                await update.message.reply_text(
                    "⚠️ Этот пользователь уже добавлен!",
                    reply_markup=users_keyboard()
                )
            else:
                allowed_users.append(new_user_id)
                save_users()
                
                await update.message.reply_text(
                    f"✅ <b>Пользователь добавлен!</b>\n\n"
                    f"User ID: <code>{new_user_id}</code>\n\n"
                    f"Теперь он может пользоваться ботом.",
                    reply_markup=users_keyboard(),
                    parse_mode='HTML'
                )
            
            del user_states[user_id]
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат!\n\n"
                "Отправьте числовой User ID."
            )
    
    # Остальные обработчики без изменений
    elif action == 'send_reply':
        reply_id = state['reply_id']
        
        if reply_id not in reply_cache:
            await update.message.reply_text(
                "❌ Сессия устарела",
                reply_markup=main_menu_keyboard(user_id)
            )
            del user_states[user_id]
            return
        
        reply_info = reply_cache[reply_id]
        session = active_sessions.get(reply_info['session_name'])
        
        if not session:
            await update.message.reply_text(
                "❌ Аккаунт не активен",
                reply_markup=main_menu_keyboard(user_id)
            )
            del user_states[user_id]
            return
        
        message_text = update.message.text
        
        success = await session.send_reply(reply_info['sender_id'], message_text)
        
        if success:
            await update.message.reply_text(
                f"✅ <b>Сообщение отправлено!</b>\n\n"
                f"👤 Кому: {reply_info['username']}\n"
                f"📱 С аккаунта: {session.phone}\n"
                f"💬 Текст: {message_text[:100]}...",
                reply_markup=main_menu_keyboard(user_id),
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка отправки сообщения",
                reply_markup=main_menu_keyboard(user_id)
            )
        
        del user_states[user_id]
        return
    
    # Остальные обработчики сообщений (add_account, create_scenario и т.д.)
    # Код идентичен предыдущей версии...
    
    elif action == 'add_account':
        step = state['step']
        
        if step == 'api_id':
            state['api_id'] = update.message.text
            state['step'] = 'api_hash'
            await update.message.reply_text("Шаг 2/3: API_HASH:")
            
        elif step == 'api_hash':
            state['api_hash'] = update.message.text
            state['step'] = 'phone'
            await update.message.reply_text("Шаг 3/3: Номер телефона:")
            
        elif step == 'phone':
            phone = update.message.text
            session_name = make_session_name(user_id, phone)

            state['phone'] = phone
            state['session_name'] = session_name

            try:
                await update.message.reply_text("⏳ Отправка кода...")

                client = TelegramClient(
                    user_session_path(user_id, session_name),
                    state['api_id'],
                    state['api_hash'],
                )
                await client.connect()

                if not await client.is_user_authorized():
                    result = await client.send_code_request(phone)
                    state['phone_code_hash'] = result.phone_code_hash
                    state['client'] = client
                    state['step'] = 'code'

                    await update.message.reply_text(
                        "📱 <b>Код отправлен в Telegram!</b>\n\n"
                        "Проверьте ваш Telegram и отправьте код сюда.\n"
                        "Формат: 12345 (без дефисов)",
                        parse_mode='HTML'
                    )
                else:
                    me = await client.get_me()

                    accounts = load_accounts(user_id)
                    accounts.append({
                        'api_id': state['api_id'],
                        'api_hash': state['api_hash'],
                        'phone': phone,
                        'session_name': session_name
                    })
                    save_accounts(user_id, accounts)

                    temp_session = UserbotSession(
                        state['api_id'],
                        state['api_hash'],
                        phone,
                        session_name,
                        user_id,
                    )
                    temp_session.client = client
                    await temp_session.setup_message_handler()
                    active_sessions[session_name] = temp_session
                    
                    await update.message.reply_text(
                        f"✅ Аккаунт уже авторизован!\n\n"
                        f"👤 {me.first_name}\n"
                        f"📱 {phone}",
                        reply_markup=main_menu_keyboard(user_id)
                    )
                    del user_states[user_id]
                    
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Ошибка: {str(e)}\n\n"
                    f"Проверьте API_ID, API_HASH и номер телефона",
                    reply_markup=main_menu_keyboard(user_id)
                )
                del user_states[user_id]
        
        elif step == 'code':
            code = update.message.text.replace('-', '').replace(' ', '')
            
            try:
                await update.message.reply_text("⏳ Проверка кода...")
                
                client = state['client']
                phone = state['phone']
                phone_code_hash = state['phone_code_hash']
                
                try:
                    await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
                    
                except FloodWaitError as flood_error:
                    await update.message.reply_text(
                        f"⚠️ FloodWait: {flood_error.seconds} сек\n\n"
                        f"Попробуйте через {flood_error.seconds} секунд",
                        reply_markup=main_menu_keyboard(user_id)
                    )
                    if 'client' in state:
                        await state['client'].disconnect()
                    del user_states[user_id]
                    return
                    
                except Exception as e:
                    error_str = str(e)
                    
                    if 'expired' in error_str.lower() or 'PHONE_CODE_EXPIRED' in error_str:
                        await update.message.reply_text(
                            "⚠️ <b>Код устарел!</b>\n\n"
                            "Запрашиваю новый код...",
                            parse_mode='HTML'
                        )
                        
                        try:
                            result = await client.send_code_request(phone)
                            state['phone_code_hash'] = result.phone_code_hash
                            
                            await update.message.reply_text(
                                "📱 <b>Новый код отправлен!</b>\n\n"
                                "Отправьте новый код:",
                                parse_mode='HTML'
                            )
                            return
                        except Exception as retry_error:
                            await update.message.reply_text(
                                f"❌ Ошибка запроса нового кода: {str(retry_error)}\n\n"
                                f"Начните добавление заново: /start",
                                reply_markup=main_menu_keyboard(user_id)
                            )
                            if 'client' in state:
                                await state['client'].disconnect()
                            del user_states[user_id]
                            return
                    
                    elif 'PHONE_CODE_INVALID' in error_str:
                        await update.message.reply_text(
                            "❌ <b>Неверный код!</b>\n\n"
                            "Попробуйте ещё раз:",
                            parse_mode='HTML'
                        )
                        return
                    
                    elif 'Two-step verification' in error_str or 'password' in error_str.lower():
                        state['step'] = 'password'
                        await update.message.reply_text(
                            "🔐 <b>Требуется пароль 2FA</b>\n\n"
                            "Введите пароль облачного хранилища Telegram:",
                            parse_mode='HTML'
                        )
                        return
                    else:
                        raise e
                
                me = await client.get_me()

                accounts = load_accounts(user_id)
                accounts.append({
                    'api_id': state['api_id'],
                    'api_hash': state['api_hash'],
                    'phone': phone,
                    'session_name': state['session_name']
                })
                save_accounts(user_id, accounts)

                temp_session = UserbotSession(
                    state['api_id'],
                    state['api_hash'],
                    phone,
                    state['session_name'],
                    user_id,
                )
                temp_session.client = client
                await temp_session.setup_message_handler()
                active_sessions[state['session_name']] = temp_session
                
                await update.message.reply_text(
                    f"✅ <b>Аккаунт успешно добавлен!</b>\n\n"
                    f"👤 {me.first_name}\n"
                    f"📱 {phone}\n"
                    f"🆔 @{me.username if me.username else 'нет username'}\n\n"
                    f"✅ Статус: Активен\n"
                    f"📬 Уведомления о входящих: Включены",
                    reply_markup=main_menu_keyboard(user_id),
                    parse_mode='HTML'
                )
                
                del user_states[user_id]
                
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Ошибка авторизации: {str(e)}\n\n"
                    f"Начните заново: /start",
                    reply_markup=main_menu_keyboard(user_id)
                )
                
                if 'client' in state:
                    await state['client'].disconnect()
                
                del user_states[user_id]
        
        elif step == 'password':
            password = update.message.text
            
            try:
                await update.message.reply_text("⏳ Проверка пароля...")
                
                client = state['client']
                
                await client.sign_in(password=password)
                
                me = await client.get_me()
                
                accounts = load_accounts(user_id)
                accounts.append({
                    'api_id': state['api_id'],
                    'api_hash': state['api_hash'],
                    'phone': state['phone'],
                    'session_name': state['session_name']
                })
                save_accounts(user_id, accounts)

                temp_session = UserbotSession(
                    state['api_id'],
                    state['api_hash'],
                    state['phone'],
                    state['session_name'],
                    user_id,
                )
                temp_session.client = client
                await temp_session.setup_message_handler()
                active_sessions[state['session_name']] = temp_session
                
                await update.message.reply_text(
                    f"✅ <b>Аккаунт добавлен!</b>\n\n"
                    f"👤 {me.first_name}\n"
                    f"📱 {state['phone']}\n"
                    f"📬 Уведомления: Включены",
                    reply_markup=main_menu_keyboard(user_id),
                    parse_mode='HTML'
                )
                
                del user_states[user_id]
                
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Неверный пароль: {str(e)}",
                    reply_markup=main_menu_keyboard(user_id)
                )
                
                if 'client' in state:
                    await state['client'].disconnect()
                
                del user_states[user_id]
    
    elif action == 'create_scenario':
        scenarios = load_scenarios(user_id)
        scenarios.append({'name': update.message.text, 'steps': []})
        save_scenarios(user_id, scenarios)
        
        await update.message.reply_text(
            f"✅ Сценарий '{update.message.text}' создан!",
            reply_markup=scenarios_keyboard(scenarios)
        )
        del user_states[user_id]
    
    elif action == 'add_step_text':
        scenarios = load_scenarios(user_id)
        scenarios[state['scenario_id']]['steps'].append({
            'type': 'text',
            'content': update.message.text
        })
        save_scenarios(user_id, scenarios)
        
        await update.message.reply_text(
            "✅ Текст добавлен",
            reply_markup=scenario_detail_keyboard(state['scenario_id'])
        )
        del user_states[user_id]
    
    elif action == 'add_step_forward':
        step = state['step']
        
        if step == 'bot':
            state['bot_username'] = update.message.text
            state['step'] = 'command'
            await update.message.reply_text("Шаг 2/2: Команда для бота (обычно /pyid):")
        elif step == 'command':
            scenarios = load_scenarios(user_id)
            scenarios[state['scenario_id']]['steps'].append({
                'type': 'forward_from_bot',
                'bot_username': state['bot_username'],
                'command': update.message.text
            })
            save_scenarios(user_id, scenarios)
            
            await update.message.reply_text(
                "✅ Пересылка добавлена",
                reply_markup=scenario_detail_keyboard(state['scenario_id'])
            )
            del user_states[user_id]
    
    elif action == 'add_step_channel':
        scenarios = load_scenarios(user_id)
        scenarios[state['scenario_id']]['steps'].append({
            'type': 'forward_from_channel',
            'post_link': update.message.text
        })
        save_scenarios(user_id, scenarios)
        
        await update.message.reply_text(
            "✅ Пересылка поста добавлена",
            reply_markup=scenario_detail_keyboard(state['scenario_id'])
        )
        del user_states[user_id]
    
    elif action == 'add_step_inline':
        step = state['step']
        
        if step == 'bot':
            state['bot_username'] = update.message.text
            state['step'] = 'query'
            await update.message.reply_text("Шаг 2/3: Текст запроса (или '.'):")
        elif step == 'query':
            state['query'] = update.message.text if update.message.text != '.' else ''
            state['step'] = 'index'
            await update.message.reply_text("Шаг 3/3: Номер результата (0, 1, 2...):")
        elif step == 'index':
            scenarios = load_scenarios(user_id)
            scenarios[state['scenario_id']]['steps'].append({
                'type': 'inline',
                'bot_username': state['bot_username'],
                'query': state['query'],
                'result_index': int(update.message.text)
            })
            save_scenarios(user_id, scenarios)
            
            await update.message.reply_text(
                "✅ Инлайн добавлен",
                reply_markup=scenario_detail_keyboard(state['scenario_id'])
            )
            del user_states[user_id]
    
    elif action == 'add_step_delay':
        scenarios = load_scenarios(user_id)
        scenarios[state['scenario_id']]['steps'].append({
            'type': 'delay',
            'seconds': int(update.message.text)
        })
        save_scenarios(user_id, scenarios)
        
        await update.message.reply_text(
            "✅ Задержка добавлена",
            reply_markup=scenario_detail_keyboard(state['scenario_id'])
        )
        del user_states[user_id]
    
    elif action == 'start_mailing':
        usernames = [line.strip().lstrip('@') for line in update.message.text.split('\n') if line.strip()]
        state['usernames'] = usernames
        
        scenarios = load_scenarios(user_id)
        keyboard = []
        for i, sc in enumerate(scenarios):
            keyboard.append([InlineKeyboardButton(
                f"📋 {sc['name']}", 
                callback_data=f"mailing_scenario_{i}"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Отмена", callback_data="main")])
        
        await update.message.reply_text(
            f"✅ Загружено {len(usernames)} пользователей\n\n"
            "Шаг 2/3: Выберите сценарий:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action == 'set_delay':
        try:
            delay = int(update.message.text)
            
            if delay < 5:
                await update.message.reply_text(
                    "⚠️ Минимальная задержка: 5 секунд\n"
                    "Попробуйте снова:"
                )
                return
            
            if delay > 300:
                await update.message.reply_text(
                    "⚠️ Максимальная задержка: 300 секунд (5 минут)\n"
                    "Попробуйте снова:"
                )
                return
            
            config = load_config(user_id)
            config['delay'] = delay
            save_config(user_id, config)
            
            keyboard = [
                [InlineKeyboardButton("⏱️ Изменить", callback_data="change_delay")],
                [InlineKeyboardButton("◀️ Назад", callback_data="main")]
            ]
            
            await update.message.reply_text(
                f"✅ <b>Задержка установлена!</b>\n\n"
                f"⏱️ Новая задержка: <b>{delay} секунд</b>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
            del user_states[user_id]
            
        except ValueError:
            await update.message.reply_text(
                "❌ Введите число!\n\n"
                "Например: 30"
            )

async def sticker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_allowed(user_id) or user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    if state.get('action') == 'add_step_sticker':
        scenarios = load_scenarios(user_id)
        scenarios[state['scenario_id']]['steps'].append({
            'type': 'sticker',
            'file_id': update.message.sticker.file_id
        })
        save_scenarios(user_id, scenarios)
        
        await update.message.reply_text(
            "✅ Стикер добавлен",
            reply_markup=scenario_detail_keyboard(state['scenario_id'])
        )
        del user_states[user_id]

async def run_mailing_task(query, session, usernames, scenario):
    result = await send_bulk(session, usernames, scenario['steps'])
    
    status_text = "завершена"
    if global_mailing_stop or mailing_paused.get(session.session_name, False):
        status_text = "остановлена"
    
    await query.edit_message_text(
        f"✅ <b>Рассылка {status_text}!</b>\n\n"
        f"✅ Успешно: {result['success']}\n"
        f"⏭️ Пропущено: {result['skipped']}\n"
        f"📝 Всего: {result['total']}",
        reply_markup=main_menu_keyboard(query.from_user.id),
        parse_mode='HTML'
    )

async def run_mailing_task_all(query, sessions, usernames, scenario):
    """Запуск рассылки на всех аккаунтах одновременно"""
    result = await send_bulk_all_accounts(sessions, usernames, scenario['steps'])
    
    status_text = "завершена"
    if global_mailing_stop:
        status_text = "остановлена"
    
    await query.edit_message_text(
        f"✅ <b>МАССОВАЯ РАССЫЛКА {status_text.upper()}!</b>\n\n"
        f"👥 Использовано аккаунтов: {result['accounts_used']}\n"
        f"✅ Успешно: {result['success']}\n"
        f"⏭️ Пропущено: {result['skipped']}\n"
        f"📝 Всего: {result['total']}",
        reply_markup=main_menu_keyboard(query.from_user.id),
        parse_mode='HTML'
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    print(f"⚠️ Ошибка: {context.error}")
    
    if isinstance(context.error, TimedOut):
        print("⏳ Таймаут - игнорируем")
        return
    
    import traceback
    traceback.print_exc()

async def restore_sessions():
    """При старте поднимает telethon-сессии для всех пользователей."""
    for owner_id in list(allowed_users):
        accounts = load_accounts(owner_id)
        for acc in accounts:
            try:
                await load_session(acc, owner_id)
                print(f"✅ [u{owner_id}] Сессия {acc['phone']} восстановлена")
            except Exception as e:
                print(f"⚠️ [u{owner_id}] Не удалось восстановить {acc.get('phone')}: {e}")


def main():
    global admin_bot_app

    print("🚀 Запуск панели управления...")

    if not ADMIN_BOT_TOKEN or MAIN_ADMIN_ID == 0:
        script_dir = Path(__file__).resolve().parent
        print("❌ Не задан ADMIN_BOT_TOKEN и/или MAIN_ADMIN_ID.")
        print("   Создайте файл secrets.json рядом со скриптом:")
        print(f"   {script_dir / 'secrets.json'}")
        print('   {"ADMIN_BOT_TOKEN": "<токен_от_BotFather>", "MAIN_ADMIN_ID": 123456789}')
        print("   Либо задайте переменные окружения ADMIN_BOT_TOKEN и MAIN_ADMIN_ID.")
        return

    # Загружаем пользователей
    load_users()
    print(f"👥 Разрешенных пользователей: {len(allowed_users)}")

    # Готовим директории и переносим legacy-файлы (если остались)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    migrate_legacy_data()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0
    )

    application = (
        Application.builder()
        .token(ADMIN_BOT_TOKEN)
        .request(request)
        .build()
    )

    admin_bot_app = application

    # Перехватываем bot.send_message / bot.edit_message_text:
    # автоматически заменяем эмодзи на premium custom emoji (HTML-теги).
    install_premium_emoji_filter(application)

    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))

    async def _post_init(app):
        # Восстанавливаем активные сессии для каждого пользователя
        await restore_sessions()
        # Запускаем фоновую задачу проверки сессий (требует loop)
        asyncio.create_task(check_sessions_task())

    application.post_init = _post_init

    print("✅ Панель готова! Откройте бота в Telegram")
    print("📬 Уведомления о входящих сообщениях включены (приходят только владельцу аккаунта)")
    print("🚀 Поддержка массовой рассылки на все аккаунты!")
    print("🔍 Автопроверка сессий каждый час!")
    print("✨ Premium custom emoji включены")
    print(f"👑 Главный админ: {MAIN_ADMIN_ID}")

    try:
        application.run_polling(close_loop=False)
    except KeyboardInterrupt:
        print("\n⛔ Остановлено пользователем")

if __name__ == '__main__':
    main()
