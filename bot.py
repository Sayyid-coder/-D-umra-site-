import asyncio
import os
import sqlite3
import logging
from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO)

TOKEN = "9275762539:AAHaPhSUUm8JmYjJAK9ozuT-12CvFGTckLo"
ADMIN_ID = 6570088926

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

bot = Bot(token=TOKEN)
dp = Dispatcher()

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(dp.start_polling(bot, drop_pending_updates=True))
    logging.info("Бот успешно запущен в фоновом режиме через Lifespan!")
    yield
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

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
    await callback
