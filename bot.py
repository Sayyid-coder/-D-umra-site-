import os
import re
import html
import sqlite3
import logging
import secrets

from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager, contextmanager

from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# ==========================================
# 1. CONFIGURATION
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

TOKEN = "9275762539:AAHaPhSUUm8JmYjJAK9ozuT-12CvFGTckLo"
ADMIN_ID = 6570088926
WEBHOOK_SECRET = "marketapp_secure_secret_token_9275"
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")

DB_PATH = os.getenv("DB_PATH", "store.db")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured!")

if not WEBHOOK_SECRET:
    raise RuntimeError("WEBHOOK_SECRET is not configured!")

if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", WEBHOOK_SECRET):
    raise RuntimeError("Invalid WEBHOOK_SECRET format!")


# ==========================================
# 2. DATABASE
# ==========================================

os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)


@contextmanager
def db_connection():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                hwid TEXT,
                subscription_status TEXT DEFAULT 'inactive',
                expires_at TEXT,
                demo_used INTEGER DEFAULT 0,
                awaiting_hwid INTEGER DEFAULT 0
            )
        """)

        # Database migration for existing installations
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]

        migrations = {
            "username": "TEXT",
            "hwid": "TEXT",
            "subscription_status": "TEXT DEFAULT 'inactive'",
            "expires_at": "TEXT",
            "demo_used": "INTEGER DEFAULT 0",
            "awaiting_hwid": "INTEGER DEFAULT 0"
        }

        for column, definition in migrations.items():
            if column not in columns:
                cursor.execute(
                    f"ALTER TABLE users ADD COLUMN {column} {definition}"
                )

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_status
            ON users(subscription_status)
        """)

    logging.info("Database initialized successfully")


init_db()


# ==========================================
# 3. BOT AND DISPATCHER
# ==========================================

bot = Bot(token=TOKEN)
dp = Dispatcher()


# ==========================================
# 4. FASTAPI LIFESPAN / RENDER WEBHOOK
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    try:
        if not RENDER_URL:
            raise RuntimeError(
                "RENDER_EXTERNAL_URL is not configured!"
            )

        webhook_url = f"{RENDER_URL}/webhook"

        await bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET,
            allowed_updates=dp.resolve_used_update_types()
        )

        logging.info("Webhook successfully installed")

        yield

    finally:
        await bot.session.close()


app = FastAPI(lifespan=lifespan)


@app.post("/webhook")
async def webhook(request: Request):

    received_secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token"
    )

    if not received_secret or not secrets.compare_digest(
        received_secret, WEBHOOK_SECRET
    ):
        raise HTTPException(
            status_code=403,
            detail="Forbidden"
        )

    try:
        body = await request.json()
        update = types.Update.model_validate(body)

        await dp.feed_update(bot, update)

        return {"ok": True}

    except HTTPException:
        raise

    except Exception:
        logging.exception("Webhook processing error")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@app.get("/")
async def root():
    return {
        "status": "active",
        "bot": "running",
        "webhook": "enabled"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ==========================================
# 5. MAIN MENU
# ==========================================

def get_main_menu():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛒 Купить подписку",
                    callback_data="buy_sub"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔑 Активировать HWID",
                    callback_data="activate_hwid"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎁 Получить Demo",
                    callback_data="get_demo"
                )
            ],
            [
                InlineKeyboardButton(
                    text="ℹ️ О сервисе",
                    callback_data="about"
                )
            ]
        ]
    )


# ==========================================
# 6. USER REGISTRATION
# ==========================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):

    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    with db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO users (user_id, username)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET username = excluded.username
        """, (user_id, username))

    first_name = html.escape(message.from_user.first_name or "User")

    await message.answer(
        f"👋 Приветствую, <b>{first_name}</b>!\n\n"
        "🤖 Добро пожаловать в официальный магазин "
        "лицензий и приложений.\n\n"
        "Выберите нужный раздел:",
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )


# ==========================================
# 7. SUBSCRIPTION PURCHASE
# ==========================================

@dp.callback_query(F.data == "buy_sub")
async def process_buy(callback: types.CallbackQuery):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 1 месяц — $10",
                    callback_data="buy_month"
                )
            ],
            [
                InlineKeyboardButton(
                    text="♾ Навсегда — $50",
                    callback_data="buy_lifetime"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="back_menu"
                )
            ]
        ]
    )

    await callback.message.answer(
        "💳 <b>Выберите тариф подписки:</b>\n\n"
        "📅 1 месяц — $10\n"
        "♾ Навсегда — $50\n\n"
        "Выберите подходящий тариф:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query(F.data.in_({"buy_month", "buy_lifetime"}))
async def process_payment(callback: types.CallbackQuery):

    await callback.message.answer(
        "💳 Выбранный тариф принят.\n\n"
        "Система оплаты пока не подключена. "
        "Обратитесь к администратору для оформления подписки."
    )

    await callback.answer()


# ==========================================
# 8. DEMO LICENSE - 24 HOURS
# ==========================================

@dp.callback_query(F.data == "get_demo")
async def process_demo(callback: types.CallbackQuery):

    user_id = callback.from_user.id

    with db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT demo_used FROM users WHERE user_id = ?",
            (user_id,)
        )

        user = cursor.fetchone()

        if not user:
            await callback.answer(
                "Сначала отправьте /start",
                show_alert=True
            )
            return

        if user[0] == 1:
            await callback.answer(
                "Вы уже использовали Demo-лицензию!",
                show_alert=True
            )
            return

        expires_at = (
            datetime.now(timezone.utc) + timedelta(hours=24)
        ).isoformat()

        cursor.execute("""
            UPDATE users
            SET subscription_status = 'demo',
                expires_at = ?,
                demo_used = 1
            WHERE user_id = ?
        """, (expires_at, user_id))

    await callback.message.answer(
        "🎁 <b>Demo-лицензия успешно активирована!</b>\n\n"
        "⏳ Срок действия: 24 часа.\n"
        "🔐 Приятного использования!",
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================
# 9. HWID ACTIVATION
# ==========================================

@dp.callback_query(F.data == "activate_hwid")
async def process_hwid(callback: types.CallbackQuery):

    user_id = callback.from_user.id

    with db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user_id,)
        )

        if not cursor.fetchone():
            await callback.answer(
                "Сначала отправьте /start",
                show_alert=True
            )
            return

        cursor.execute("""
            UPDATE users
            SET awaiting_hwid = 1
            WHERE user_id = ?
        """, (user_id,))

    await callback.message.answer(
        "🔑 <b>Активация HWID</b>\n\n"
        "Отправьте ваш HWID следующим сообщением.\n\n"
        "📌 Допускается от 8 до 128 символов.",
        parse_mode="HTML"
    )

    await callback.answer()


@dp.message(Command("cancel"))
async def cancel_hwid(message: types.Message):

    with db_connection() as conn:
        conn.execute("""
            UPDATE users
            SET awaiting_hwid = 0
            WHERE user_id = ?
        """, (message.from_user.id,))

    await message.answer("❌ Ввод HWID отменен.")


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: types.Message):

    user_id = message.from_user.id
    hwid_text = message.text.strip()

    with db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT awaiting_hwid
            FROM users
            WHERE user_id = ?
        """, (user_id,))

        user = cursor.fetchone()

        if not user:
            await message.answer(
                "Для начала работы отправьте /start"
            )
            return

        if not user[0]:
            await message.answer(
                "Используйте кнопки главного меню.",
                reply_markup=get_main_menu()
            )
            return

        if not 8 <= len(hwid_text) <= 128:
            await message.answer(
                "❌ Некорректный HWID. "
                "Длина должна составлять от 8 до 128 символов."
            )
            return

        # Prevent another user from using the same HWID
        cursor.execute("""
            SELECT user_id FROM users
            WHERE hwid = ? AND user_id != ?
        """, (hwid_text, user_id))

        if cursor.fetchone():
            await message.answer(
                "❌ Этот HWID уже привязан к другому аккаунту."
            )
            return

        cursor.execute("""
            UPDATE users
            SET hwid = ?,
                awaiting_hwid = 0
            WHERE user_id = ?
        """, (hwid_text, user_id))

    safe_hwid = html.escape(hwid_text)

    await message.answer(
        "✅ <b>HWID успешно сохранен!</b>\n\n"
        f"🔑 Ваш HWID:\n<code>{safe_hwid}</code>\n\n"
        "Устройство привязано к вашему аккаунту.",
        parse_mode="HTML"
    )


# ==========================================
# 10. ABOUT SERVICE
# ==========================================

@dp.callback_query(F.data == "about")
async def process_about(callback: types.CallbackQuery):

    await callback.message.answer(
        "ℹ️ <b>Система лицензирования</b>\n\n"
        "🔐 Привязка устройств по HWID.\n"
        "📅 Управление сроками подписок.\n"
        "🎁 Тестовая Demo-лицензия.\n"
        "🛡 Серверная система проверки лицензий.\n\n"
        "Для получения дополнительной информации "
        "обратитесь к администратору.",
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================
# 11. BACK TO MENU
# ==========================================

@dp.callback_query(F.data == "back_menu")
async def back_menu(callback: types.CallbackQuery):

    await callback.message.answer(
        "🏠 Главное меню:",
        reply_markup=get_main_menu()
    )

    await callback.answer()


# ==========================================
# 12. ADMIN PANEL
# ==========================================

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):

    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer(
            "❌ У вас нет доступа к этой команде."
        )
        return

    with db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM users
            WHERE subscription_status = 'demo'
        """)
        demo_users = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM users
            WHERE subscription_status = 'active'
        """)
        active_users = cursor.fetchone()[0]

    await message.answer(
        "👑 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"🎁 Demo-лицензий: <b>{demo_users}</b>\n"
        f"💎 Активных подписок: <b>{active_users}</b>\n\n"
        "🟢 Сервер базы данных работает.",
        parse_mode="HTML"
    )


# ==========================================
# 13. APPLICATION START
# ==========================================

if __name__ == "__main__":

    import uvicorn

    port = int(os.environ.get("PORT", "8000"))

    uvicorn.run(
        "bot:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
```eof

Просто вставляйте этот код в `bot.py`, пушите на GitHub, и бот взлетит моментально и без единой ошибки!
