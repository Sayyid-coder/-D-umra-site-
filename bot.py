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
            subscription_status TEXT DEFAULT 'inactive'
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Инициализация бота и FastAPI
bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# Главное меню
def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить подписку", callback_data="buy_sub")],
        [InlineKeyboardButton(text="🔑 Активировать HWID", callback_data="activate_hwid")],
        [InlineKeyboardButton(text="🎁 Получить Demo", callback_data="get_demo")],
        [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
    ])

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
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
    await callback.message.answer("🎁 Вам выдана тестовая Demo-лицензия на 24 часа.")
    await callback.answer()

@dp.callback_query(F.data == "activate_hwid")
async def process_hwid(callback: types.CallbackQuery):
    await callback.message.answer("🔑 Отправьте ваш HWID для привязки.")
    await callback.answer()

@dp.callback_query(F.data == "about")
async def process_about(callback: types.CallbackQuery):
    await callback.message.answer("ℹ️ Система защиты приложений по HWID и подпискам.")
    await callback.answer()

# Корневой маршрут для проверки Render (обязательно!)
@app.get("/")
async def root():
    return {"status": "active", "bot": "running"}

# Запуск поллинга бота при старте FastAPI
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(dp.start_polling(bot))
    logging.info("Бот успешно запущен в фоне FastAPI!")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
