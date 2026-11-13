import asyncio
import os
import sqlite3
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from fastapi import FastAPI
import uvicorn

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# ==================== НАСТРОЙКИ ====================
TOKEN = "9275762539:AAHaPhSUUm8JmYjJAK9ozuT-12CvfGTckLo"
ADMIN_ID = 6570088926
# ====================================================

# Инициализация бота и диспетчера aiogram
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Инициализация базы данных SQLite для лицензий и пользователей
def init_db():
    conn = sqlite3.connect("store.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            hwid TEXT,
            subscription_status TEXT DEFAULT 'inactive'
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Главное меню (магазин, подписки, демо, HWID DRM)
def get_main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить подписку", callback_data="buy_sub")],
        [InlineKeyboardButton(text="🔑 Активировать HWID", callback_data="activate_hwid")],
        [InlineKeyboardButton(text="🎁 Получить Demo", callback_data="get_demo")],
        [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
    ])
    return keyboard

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Сохраняем пользователя в БД
    conn = sqlite3.connect("store.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

    welcome_text = (
        f"👋 Приветствую, <b>{message.from_user.first_name}</b>!\n\n"
        "🤖 Добро пожаловать в официальный магазин лицензий и приложений.\n"
        "Здесь вы можете приобрести доступ, активировать HWID-привязку и управлять подписками."
    )
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=get_main_menu())

# Обработка кнопок меню
@dp.callback_query(F.data == "buy_sub")
async def process_buy(callback: types.CallbackQuery):
    await callback.message.answer("💳 Выберите тариф подписки:\n\n1. 1 Месяц — $10\n2. Навсегда (Lifetime) — $50", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатить 1 Месяц", callback_data="pay_month")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_home")]
    ]))
    await callback.answer()

@dp.callback_query(F.data == "get_demo")
async def process_demo(callback: types.CallbackQuery):
    await callback.message.answer("🎁 Вам выдана тестовая Demo-лицензия на 24 часа. Привяжите ваш HWID через меню активации.")
    await callback.answer()

@dp.callback_query(F.data == "activate_hwid")
async def process_hwid(callback: types.CallbackQuery):
    await callback.message.answer("🔑 Отправьте ваш HWID в ответном сообщении для привязки к системе защиты DRM.")
    await callback.answer()

@dp.callback_query(F.data == "about")
async def process_about(callback: types.CallbackQuery):
    await callback.message.answer("ℹ️ Наша система обеспечивает защиту приложений по HWID и автоматическую выдачу подписок 24/7.")
    await callback.answer()

@dp.callback_query(F.data == "back_home")
async def process_home(callback: types.CallbackQuery):
    await callback.message.answer("🏠 Главное меню:", reply_markup=get_main_menu())
    await callback.answer()


# ==================== НАСТРОЙКА FASTAPI (ДЛЯ RENDER) ====================
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "Bot Store is running successfully!", "mode": "Long Polling"}

async def run_telegram_bot():
    """Фоновое запуски поллинга Telegram-бота"""
    await dp.start_polling(bot)

@app.on_event("startup")
async def startup_event():
    # Запускаем бота в асинхронном фоне при старте FastAPI
    asyncio.create_task(run_telegram_bot())

if __name__ == "__main__":
    # Получаем порт от Render или используем 10000 по умолчанию
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
