import os
import sqlite3
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from fastapi import FastAPI, Request
import uvicorn

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Ваши данные
TOKEN = "9275762539:AAHaPhSUUm8JmYjJAK9ozuT-12CvFGTckLo"
ADMIN_ID = 6570088926

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect("store.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            hwid TEXT,
            subscription_status TEXT DEFAULT 'inactive',
            expires_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Инициализация бота и FastAPI
bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# Главное меню магазина
def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить подписку", callback_data="buy_sub")],
        [InlineKeyboardButton(text="🔑 Активировать HWID", callback_data="activate_hwid")],
        [InlineKeyboardButton(text="🎁 Получить Demo", callback_data="get_demo")],
        [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
    ])

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    conn = sqlite3.connect("store.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

    await message.answer(
        f"👋 Приветствую, <b>{message.from_user.first_name}</b>!\n\n"
        "🤖 Добро пожаловать в официальный магазин лицензий и приложений.",
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )

@dp.callback_query(F.data == "buy_sub")
async def process_buy(callback: types.CallbackQuery):
    await callback.message.answer("💳 Выберите тариф подписки:\n\n1. 1 Месяц — $10\n2. Навсегда — $50")
    await callback.answer()

@dp.callback_query(F.data == "get_demo")
async def process_demo(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect("store.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET subscription_status = 'demo' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    await callback.message.answer("🎁 Вам успешно активирована тестовая Demo-лицензия на 24 часа!")
    await callback.answer()

@dp.callback_query(F.data == "activate_hwid")
async def process_hwid(callback: types.CallbackQuery):
    await callback.message.answer("🔑 Отправьте ваш **HWID** следующим текстовым сообщением в чат.")
    await callback.answer()

@dp.callback_query(F.data == "about")
async def process_about(callback: types.CallbackQuery):
    await callback.message.answer("ℹ️ Система защиты приложений по HWID и автоматической выдачей подписок.")
    await callback.answer()

# Перехват текста для HWID
@dp.message(F.text & ~F.text.startswith("/"))
async def handle_hwid_input(message: types.Message):
    user_id = message.from_user.id
    hwid_text = message.text.strip()
    
    conn = sqlite3.connect("store.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET hwid = ? WHERE user_id = ?", (hwid_text, user_id))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Ваш HWID:\n<code>{hwid_text}</code>\n\nуспешно сохранен в системе защиты!", parse_mode="HTML")

# Админ-панель
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    conn = sqlite3.connect("store.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    
    await message.answer(
        f"👑 <b>Панель администратора</b>\n\n"
        f"👥 Всего зарегистрировано пользователей: <b>{count}</b>",
        parse_mode="HTML"
    )

# Прием запросов от Telegram (Webhook)
@app.post("/webhook")
async def webhook(request: Request):
    json_data = await request.json()
    update = types.Update(**json_data)
    await dp.feed_update(bot, update)
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"status": "active", "bot": "running"}

# Автоматическая установка вебхука при старте
@app.on_event("startup")
async def on_startup():
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        webhook_url = f"{render_url}/webhook"
        await bot.set_webhook(webhook_url)
        logging.info(f"Вебхук успешно установлен на: {webhook_url}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
