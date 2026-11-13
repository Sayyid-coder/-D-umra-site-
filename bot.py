import asyncio
import logging
import secrets
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

# ==========================================
# ВСТАВЬТЕ СВОИ ДАННЫЕ СЮДА:
# ==========================================
BOT_TOKEN = "9275762539:AAHaPhSUUm8JmYjJAK9ozuT-12CvfGTckLo" # Токен, который вам дал BotFather
ADMIN_ID = (
    6570088926  # Ваш числовой Telegram ID (узнать можно в боте @userinfobot)
)
VISA_CARD_INFO = (
    "💳 **Реквизиты для оплаты (Visa):**\n"
    "`4276 0000 0000 0000`\n"
    "Получатель: Ваше Имя Ф.\n\n"
    "⚠️ **Обязательно** укажите сгенерированный ниже код в комментарии к переводу!"
)
DEMO_DAYS = 3


# ==========================================
# ИНИЦИАЛИЗАЦИЯ И БАЗА ДАННЫХ (SQLite)
# ==========================================
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


def init_db():
  conn = sqlite3.connect("store_licenses.db")
  cur = conn.cursor()

  cur.execute("""
        CREATE TABLE IF NOT EXISTS apps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            download_link TEXT NOT NULL,
            price_3m REAL NOT NULL,
            price_6m REAL NOT NULL,
            price_12m REAL NOT NULL
        )
    """)

  cur.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            app_id INTEGER NOT NULL,
            sdk_key TEXT UNIQUE NOT NULL,
            plan_type TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            hwid TEXT DEFAULT NULL,
            is_active INTEGER DEFAULT 1
        )
    """)

  cur.execute("""
        CREATE TABLE IF NOT EXISTS demo_history (
            user_id INTEGER NOT NULL,
            app_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, app_id)
        )
    """)

  cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_code TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            app_id INTEGER NOT NULL,
            months INTEGER NOT NULL,
            price REAL NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    """)

  cur.execute("SELECT COUNT(*) FROM apps")
  if cur.fetchone()[0] == 0:
    cur.execute(
        """
            INSERT INTO apps (name, description, download_link, price_3m, price_6m, price_12m)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "Pro Trade Calculator",
            (
                "Профессиональный инструмент для расчета контрактов, логистики"
                " и маржи."
            ),
            "https://example.com/download/app_v1.apk",
            15.0,
            25.0,
            45.0,
        ),
    )

  conn.commit()
  conn.close()


def generate_sdk_key(app_id: int) -> str:
  part1 = secrets.token_hex(2).upper()
  part2 = secrets.token_hex(2).upper()
  part3 = secrets.token_hex(2).upper()
  return f"APP{app_id}-{part1}-{part2}-{part3}"


# ==========================================
# СОСТОЯНИЯ (FSM)
# ==========================================
class PaymentState(StatesGroup):
  waiting_for_transaction_id = State()
  waiting_for_receipt = State()


class AddAppState(StatesGroup):
  name = State()
  description = State()
  download_link = State()
  prices = State()


# ==========================================
# КАТАЛОГ И МЕНЮ
# ==========================================
def main_menu_kb(user_id: int) -> ReplyKeyboardMarkup:
  buttons = [
      [KeyboardButton(text="📱 Магазин приложений")],
      [
          KeyboardButton(text="🔑 Мои ключи и подписки"),
          KeyboardButton(text="ℹ️ Инструкция"),
      ],
  ]
  if user_id == ADMIN_ID:
    buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
  return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
  await state.clear()
  await message.answer(
      f"Добро пожаловать в магазин приложений, {message.from_user.first_name}!\n\n"
      "Здесь вы можете протестировать демо-версии программ, оформить подписку "
      "и получить персональный SDK-ключ для активации.",
      reply_markup=main_menu_kb(message.from_user.id),
  )


@router.message(F.text == "ℹ️ Инструкция")
async def show_help(message: Message):
  await message.answer(
      "📌 **Как устроена безопасная покупка:**\n\n"
      "1. Выберите приложение и тариф в каталоге.\n"
      "2. Бот сгенерирует для вас **уникальный код заказа**.\n"
      "3. Совершите перевод на карту Visa, указав этот код в назначении"
      " платежа.\n"
      "4. Введите номер транзакции и отправьте скриншот чека.\n"
      "5. После проверки администратором вы мгновенно получите свой SDK-ключ."
  )


@router.message(F.text == "📱 Магазин приложений")
async def show_catalog(message: Message):
  conn = sqlite3.connect("store_licenses.db")
  cur = conn.cursor()
  cur.execute("SELECT id, name FROM apps")
  apps = cur.fetchall()
  conn.close()

  if not apps:
    await message.answer("Каталог пока пуст.")
    return

  kb = []
  for app_id, name in apps:
    kb.append([InlineKeyboardButton(text=f"📦 {name}", callback_data=f"app_{app_id}")])

  await message.answer(
      "Выберите приложение из каталога:",
      reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
  )


@router.callback_query(F.data.startswith("app_"))
async def app_details(callback: CallbackQuery):
  app_id = int(callback.data.split("_")[1])
  conn = sqlite3.connect("store_licenses.db")
  cur = conn.cursor()
  cur.execute(
      "SELECT name, description, download_link, price_3m, price_6m, price_12m FROM"
      " apps WHERE id = ?",
      (app_id,),
  )
  app = cur.fetchone()
  conn.close()

  if not app:
    await callback.answer("Приложение не найдено.", show_alert=True)
    return

  name, desc, link, p3, p6, p12 = app
  text = (
      f"📦 **{name}**\n\n"
      f"{desc}\n\n"
      f"📥 **Скачать:** {link}\n\n"
      f"💳 **Тарифы подписки:**\n"
      f"• 3 месяца — **${p3}**\n"
      f"• 6 месяцев — **${p6}**\n"
      f"• 12 месяцев — **${p12}**"
  )

  kb = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text=f"🎁 Попробовать демо ({DEMO_DAYS} дня)",
                  callback_data=f"demo_{app_id}",
              )
          ],
          [
              InlineKeyboardButton(
                  text=f"Купить на 3 мес (${p3})",
                  callback_data=f"buy_{app_id}_3_{p3}",
              )
          ],
          [
              InlineKeyboardButton(
                  text=f"Купить на 6 мес (${p6})",
                  callback_data=f"buy_{app_id}_6_{p6}",
              )
          ],
          [
              InlineKeyboardButton(
                  text=f"Купить на 12 мес (${p12})",
                  callback_data=f"buy_{app_id}_12_{p12}",
              )
          ],
      ]
  )
  await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


# ==========================================
# ДЕМО И ОПЛАТА
# ==========================================
@router.callback_query(F.data.startswith("demo_"))
async def activate_demo(callback: CallbackQuery):
  app_id = int(callback.data.split("_")[1])
  user_id = callback.from_user.id
  username = callback.from_user.username or "NoUsername"

  conn = sqlite3.connect("store_licenses.db")
  cur = conn.cursor()
  cur.execute(
      "SELECT 1 FROM demo_history WHERE user_id = ? AND app_id = ?",
      (user_id, app_id),
  )
  if cur.fetchone():
    conn.close()
    await callback.answer(
        "Вы уже использовали бесплатный демо-период для этого приложения!",
        show_alert=True,
    )
    return

  cur.execute("SELECT name FROM apps WHERE id = ?", (app_id,))
  app_name = cur.fetchone()[0]

  sdk_key = generate_sdk_key(app_id)
  expires_at = (datetime.now() + timedelta(days=DEMO_DAYS)).strftime(
      "%Y-%m-%d %H:%M:%S"
  )

  cur.execute(
      "INSERT INTO demo_history (user_id, app_id) VALUES (?, ?)",
      (user_id, app_id),
  )
  cur.execute(
      """
        INSERT INTO licenses (user_id, username, app_id, sdk_key, plan_type, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
      (
          user_id,
          username,
          app_id,
          sdk_key,
          f"DEMO ({DEMO_DAYS} дн.)",
          expires_at,
      ),
  )
  conn.commit()
  conn.close()

  await callback.message.answer(
      f"🎁 **Демо-доступ активирован!**\n\n"
      f"Приложение: **{app_name}**\n"
      f"SDK-ключ:\n`{sdk_key}`\n\n"
      f"⏳ Действует до: `{expires_at}`",
      parse_mode="Markdown",
  )
  await callback.answer()


@router.callback_query(F.data.startswith("buy_"))
async def start_purchase(callback: CallbackQuery, state: FSMContext):
  _, app_id, months, price = callback.data.split("_")
  order_code = f"ORD-{secrets.token_hex(2).upper()}"

  conn = sqlite3.connect("store_licenses.db")
  cur = conn.cursor()
  cur.execute(
      """
        INSERT INTO orders (order_code, user_id, app_id, months, price)
        VALUES (?, ?, ?, ?, ?)
    """,
      (
          order_code,
          callback.from_user.id,
          int(app_id),
          int(months),
          float(price),
      ),
  )
  conn.commit()
  conn.close()

  await state.update_data(order_code=order_code)
  await state.set_state(PaymentState.waiting_for_transaction_id)

  await callback.message.answer(
      f"🧾 **Заказ создан!**\n\n"
      f"Тариф: **{months} мес.** | К оплате: **${price}**\n\n"
      f"🔐 Ваш индивидуальный защитный код: `#{order_code}`\n\n"
      f"{VISA_CARD_INFO}\n\n"
      "➡️ Шаг 1 из 2: Пожалуйста, введите **номер транзакции (или ID"
      " перевода)** текстом в этот чат.",
      parse_mode="Markdown",
  )
  await callback.answer()


@router.message(PaymentState.waiting_for_transaction_id)
async def receive_transaction_id(message: Message, state: FSMContext):
  tx_id = message.text.strip()
  if len(tx_id) < 3:
    await message.answer(
        "⚠️ Пожалуйста, введите корректный номер транзакции или ID перевода."
    )
    return

  await state.update_data(tx_id=tx_id)
  await state.set_state(PaymentState.waiting_for_receipt)

  await message.answer(
      "✅ Номер транзакции принят.\n\n➡️ Шаг 2 из 2: Теперь отправьте"
      " **фотографию или скриншот** чека."
  )


@router.message(PaymentState.waiting_for_receipt, F.photo | F.document)
async def receive_receipt(message: Message, state: FSMContext):
  data = await state.get_data()
  order_code = data["order_code"]
  tx_id = data["tx_id"]
  user_id = message.from_user.id
  username = message.from_user.username or "Без_ника"

  conn = sqlite3.connect("store_licenses.db")
  cur = conn.cursor()
  cur.execute(
      "SELECT app_id, months, price FROM orders WHERE order_code = ?",
      (order_code,),
  )
  order = cur.fetchone()
  if not order:
    conn.close()
    await message.answer(
        "⚠️ Ошибка сессии. Начните покупку заново через /start."
    )
    await state.clear()
    return

  app_id, months, price = order
  cur.execute("SELECT name FROM apps WHERE id = ?", (app_id,))
  app_name = cur.fetchone()[0]
  conn.close()

  admin_kb = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="✅ Подтвердить и выдать ключ",
                  callback_data=(
                      f"approve_{order_code}_{user_id}_{app_id}_{months}"
                  ),
              )
          ],
          [
              InlineKeyboardButton(
                  text="❌ Отклонить (Фейк/Мошенник)",
                  callback_data=f"reject_{order_code}_{user_id}",
              )
          ],
      ]
  )

  caption = (
      f"🛡 **Проверка безопасности платежа!**\n\n"
      f"👤 Покупатель: @{username} (ID: `{user_id}`)\n"
      f"📦 Приложение: **{app_name}** ({months} мес. / ${price})\n"
      f"🔐 Код заказа: `#{order_code}`\n"
      f"💳 Номер транзакции: `{tx_id}`\n\n"
      "Сверьте номер транзакции перед подтверждением!"
  )

  if message.photo:
    await bot.send_photo(
        ADMIN_ID,
        photo=message.photo[-1].file_id,
        caption=caption,
        reply_markup=admin_kb,
        parse_mode="Markdown",
    )
  else:
    await bot.send_document(
        ADMIN_ID,
        document=message.document.file_id,
        caption=caption,
        reply_markup=admin_kb,
        parse_mode="Markdown",
    )

  await state.clear()
  await message.answer(
      "✅ Чек отправлен администратору на проверку. Ожидайте выдачи ключа!"
  )


@router.message(PaymentState.waiting_for_receipt)
async def invalid_receipt(message: Message):
  await message.answer("⚠️ Пожалуйста, отправьте скриншот чека.")


# ==========================================
# ПОДТВЕРЖДЕНИЕ И АДМИНКА
# ==========================================
@router.callback_query(F.data.startswith("approve_"))
async def approve_payment(callback: CallbackQuery):
  if callback.from_user.id != ADMIN_ID:
    return

  _, order_code, user_id, app_id, months = callback.data.split("_")
  user_id = int(user_id)
  app_id = int(app_id)
  months = int(months)

  conn = sqlite3.connect("store_licenses.db")
  cur = conn.cursor()
  cur.execute("SELECT name FROM apps WHERE id = ?", (app_id,))
  app_name = cur.fetchone()[0]

  sdk_key = generate_sdk_key(app_id)
  days = months * 30
  expires_at = (datetime.now() + timedelta(days=days)).strftime(
      "%Y-%m-%d %H:%M:%S"
  )

  cur.execute(
      """
        INSERT INTO licenses (user_id, username, app_id, sdk_key, plan_type, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
      (user_id, "VerifiedClient", app_id, sdk_key, f"{months} мес.", expires_at),
  )
  cur.execute(
      "UPDATE orders SET status = 'approved' WHERE order_code = ?",
      (order_code,),
  )
  conn.commit()
  conn.close()

  await bot.send_message(
      user_id,
      f"🎉 **Оплата успешно подтверждена!**\n\n"
      f"Приложение: **{app_name}**\n"
      f"Тариф: **{months} мес.**\n"
      f"Ваш индивидуальный SDK-ключ:\n`{sdk_key}`\n\n"
      f"⏳ Активен до: `{expires_at}`",
      parse_mode="Markdown",
  )
  await callback.message.edit_caption(
      caption=(
          callback.message.caption
          + f"\n\n✅ **ОПЛАТА ПОДТВЕРЖДЕНА.** Выдан ключ: `{sdk_key}`"
      ),
      parse_mode="Markdown",
  )
  await callback.answer("Ключ успешно выдан!")


@router.callback_query(F.data.startswith("reject_"))
async def reject_payment(callback: CallbackQuery):
  if callback.from_user.id != ADMIN_ID:
    return

  _, order_code, user_id = callback.data.split("_")
  user_id = int(user_id)

  conn = sqlite3.connect("store_licenses.db")
  cur = conn.cursor()
  cur.execute(
      "UPDATE orders SET status = 'rejected' WHERE order_code = ?", (order_code,)
  )
  conn.commit()
  conn.close()

  await bot.send_message(
      user_id,
      "❌ **Оплата отклонена.**\nЧек не прошел проверку безопасности.",
      parse_mode="Markdown",
  )
  await callback.message.edit_caption(
      caption=callback.message.caption + "\n\n❌ **ОТКЛОНЕНО (ФЕЙК).**",
      parse_mode="Markdown",
  )
  await callback.answer("Заявка отклонена.")


@router.message(F.text == "🔑 Мои ключи и подписки")
async def my_licenses(message: Message):
  user_id = message.from_user.id
  conn = sqlite3.connect("store_licenses.db")
  cur = conn.cursor()
  cur.execute(
      """
        SELECT a.name, l.sdk_key, l.plan_type, l.expires_at, l.hwid
        FROM licenses l
        JOIN apps a ON l.app_id = a.id
        WHERE l.user_id = ?
        ORDER BY l.id DESC
    """,
      (user_id,),
  )
  rows = cur.fetchall()
  conn.close()

  if not rows:
    await message.answer("У вас пока нет активных ключей.")
    return

  text = "🔑 **Ваши лицензионные ключи:**\n\n"
  now = datetime.now()
  for name, key, plan, exp_str, hwid in rows:
    exp_dt = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S")
    status = "🟢 Активен" if exp_dt > now else "🔴 Истек"
    device_status = "Привязан" if hwid else "Ожидает активации"
    text += (
        f"📦 **{name}** ({plan})\n"
        f"Ключ: `{key}`\n"
        f"Статус: {status} (до `{exp_str}`)\n"
        f"Устройство: {device_status}\n"
        f"-------------------\n"
    )
  await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message):
  if message.from_user.id != ADMIN_ID:
    return

  conn = sqlite3.connect("store_licenses.db")
  cur = conn.cursor()
  cur.execute("SELECT COUNT(*) FROM licenses")
  total_keys = cur.fetchone()[0]
  conn.close()

  kb = InlineKeyboardMarkup(
      inline_keyboard=[[
          InlineKeyboardButton(
              text="➕ Добавить новое приложение", callback_data="admin_add_app"
          )
      ]]
  )
  await message.answer(
      f"⚙️ **Панель владельца**\nВсего ключей в базе: **{total_keys}**\n\nСброс"
      " HWID: `/reset_hwid КЛЮЧ`",
      reply_markup=kb,
      parse_mode="Markdown",
  )


@router.message(Command("reset_hwid"))
async def reset_hwid_cmd(message: Message):
  if message.from_user.id != ADMIN_ID:
    return
  parts = message.text.split()
  if len(parts) != 2:
    await message.answer("Использование: `/reset_hwid APP1-XXXX-YYYY-ZZZZ`")
    return
  key = parts[1].strip()
  conn = sqlite3.connect("store_licenses.db")
  cur = conn.cursor()
  cur.execute("UPDATE licenses SET hwid = NULL WHERE sdk_key = ?", (key,))
  updated = cur.rowcount
  conn.commit()
  conn.close()
  if updated:
    await message.answer(f"✅ Привязка сброшена для ключа `{key}`")
  else:
    await message.answer("❌ Ключ не найден.")


@router.callback_query(F.data == "admin_add_app")
async def add_app_start(callback: CallbackQuery, state: FSMContext):
  if callback.from_user.id != ADMIN_ID:
    return
  await state.set_state(AddAppState.name)
  await callback.message.answer("Введите **название** нового приложения:")
  await callback.answer()


@router.message(AddAppState.name)
async def add_app_name(message: Message, state: FSMContext):
  await state.update_data(name=message.text)
  await state.set_state(AddAppState.description)
  await message.answer("Введите **описание** приложения:")


@router.message(AddAppState.description)
async def add_app_desc(message: Message, state: FSMContext):
  await state.update_data(description=message.text)
  await state.set_state(AddAppState.download_link)
  await message.answer("Отправьте **ссылку на скачивание** файла:")


@router.message(AddAppState.download_link)
async def add_app_link(message: Message, state: FSMContext):
  await state.update_data(download_link=message.text)
  await state.set_state(AddAppState.prices)
  await message.answer(
      "Введите **цены** для 3, 6 и 12 месяцев через пробел (например: `10 18"
      " 30`):"
  )


@router.message(AddAppState.prices)
async def add_app_prices(message: Message, state: FSMContext):
  try:
    p3, p6, p12 = map(float, message.text.split())
  except ValueError:
    await message.answer("⚠️ Введите три числа через пробел: `15 25 45`")
    return

  data = await state.get_data()
  conn = sqlite3.connect("store_licenses.db")
  cur = conn.cursor()
  cur.execute(
      """
        INSERT INTO apps (name, description, download_link, price_3m, price_6m, price_12m)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
      (
          data["name"],
          data["description"],
          data["download_link"],
          p3,
          p6,
          p12,
      ),
  )
  conn.commit()
  conn.close()

  await state.clear()
  await message.answer(f"✅ Приложение **{data['name']}** успешно добавлено!")


async def main():
  init_db()
  print("Бот-магазин запущен и защищен...")
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
