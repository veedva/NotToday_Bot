import logging
import random
import json
import os
import asyncio
from datetime import datetime, time
from filelock import FileLock
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import pytz

logging.basicConfig(format='%(asctime)s — %(levelname)s — %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен!")

DATA_FILE = "user_data.json"
LOCK_FILE = DATA_FILE + ".lock"
MOSCOW_TZ = pytz.timezone('Europe/Moscow')
NOW = lambda: datetime.now(MOSCOW_TZ)

# ====================== Сообщения ======================
MORNING_MESSAGES = [
    "Привет. Давай сегодня не будем, хорошо?",
    "Доброе утро, брат. Не сегодня.",
    "Привет. Держимся сегодня, да?",
]
EVENING_MESSAGES = [
    "Брат, не сегодня. Держись.",
    "Эй, я тут. Давай не сегодня.",
    "Привет. Сегодня держимся, помнишь?",
]
NIGHT_MESSAGES = [
    "Ты молодец. До завтра.",
    "Красавчик. Спокойной.",
    "Держался сегодня. Уважаю.",
]
MILESTONES = {
    3: "Три дня уже. Неплохо идём.",
    7: "Неделя прошла. Продолжаем.",
    14: "Две недели! Хорошо идёт.",
    30: "Месяц. Серьёзно, уважаю.",
    60: "Два месяца. Сильный результат.",
    90: "Три месяца! Ты реально крутой.",
    180: "Полгода. Это впечатляет.",
    365: "Год. Легенда."
}
HELP_TECHNIQUES = [
    "Бери и дыши так по кругу: вдох носом 4 секунды → задержи дыхание 4 → выдох 4 → не дыши 4. Повтори 6–8 раз.",
    "Прямо сейчас падай и делай 20–30 отжиманий или приседаний до жжения в мышцах.",
    "Открой кран с ледяной водой и суй туда лицо + шею на 20–30 секунд.",
]
TU_TUT_FIRST = ["Тут.", "Привет.", "А куда я денусь?", "Здесь."]
TU_TUT_SECOND = ["Держимся.", "Я с тобой.", "Всё по плану?", "Не хочу сегодня."]

HOLD_RESPONSES = ["Отправлено. ✊", "Молодец. ✊", "Красава. ✊", "Респект. ✊", "Так держать. ✊"]

# ====================== Работа с данными ======================
def load_data():
    with FileLock(LOCK_FILE):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

def save_data(data):
    with FileLock(LOCK_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(user_id):
    data = load_data()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "start_date": NOW().isoformat(),
            "active": False,
            "state": "normal",
            "best_streak": 0,
            "hold_count": 0,
            "hold_date": None,
            "hold_time": None,
            "used_tips": [],
            "menu_message_id": None,
            "pin_message_id": None
        }
        save_data(data)
    return data, data[uid]

def get_days(user_id):
    _, user = get_user(user_id)
    if user.get("start_date"):
        start = datetime.fromisoformat(user["start_date"])
        return (NOW() - start).days
    return 0

def reset_streak(user_id):
    data, user = get_user(user_id)
    current = get_days(user_id)
    if current > user.get("best_streak", 0):
        user["best_streak"] = current
    user["start_date"] = NOW().isoformat()
    user["hold_count"] = 0
    user["hold_date"] = None
    user["hold_time"] = None
    save_data(data)

def get_next_tip(user_data: dict) -> str:
    used = user_data.setdefault("used_tips", [])
    if len(used) >= len(HELP_TECHNIQUES):
        used.clear()
    available = [i for i in range(len(HELP_TECHNIQUES)) if i not in used]
    choice = random.choice(available)
    used.append(choice)
    return HELP_TECHNIQUES[choice]

# ====================== Кнопки ======================
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✊ Держусь", callback_data="hold")],
        [InlineKeyboardButton("😔 Тяжело", callback_data="heavy")],
        [InlineKeyboardButton("📊 Дни", callback_data="days"),
         InlineKeyboardButton("👋 Ты тут?", callback_data="tutut")],
        [InlineKeyboardButton("❤️ Спасибо", callback_data="thanks"),
         InlineKeyboardButton("⏸ Пауза", callback_data="pause")]
    ])

def heavy_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💪 Помочь себе", callback_data="help")],
        [InlineKeyboardButton("😅 Чуть не сорвался", callback_data="almost")],
        [InlineKeyboardButton("😞 Срыв", callback_data="break")],
        [InlineKeyboardButton("↩️ Назад", callback_data="back")]
    ])

def help_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Ещё способ", callback_data="next_tip")],
        [InlineKeyboardButton("↩️ Назад", callback_data="back")]
    ])

def start_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶ Начать", callback_data="start")]
    ])

# ====================== Отправка и редактирование меню ======================
async def send_menu(bot, chat_id, text, keyboard):
    data, user = get_user(chat_id)
    menu_id = user.get("menu_message_id")
    if menu_id:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=menu_id,
                                        text=text, reply_markup=keyboard)
        except:
            msg = await bot.send_message(chat_id, text, reply_markup=keyboard)
            user["menu_message_id"] = msg.message_id
            save_data(data)
    else:
        msg = await bot.send_message(chat_id, text, reply_markup=keyboard)
        user["menu_message_id"] = msg.message_id
        save_data(data)

async def update_pin(bot, chat_id):
    days = get_days(chat_id)
    data, user = get_user(chat_id)
    best = user.get("best_streak", 0)
    text = f"Первый день • Лучший стрик: {best}" if days == 0 else f"День {days} • Лучший стрик: {best}"
    pin_id = user.get("pin_message_id")
    try:
        if pin_id:
            await bot.edit_message_text(chat_id=chat_id, message_id=pin_id, text=text)
        else:
            msg = await bot.send_message(chat_id, text)
            await bot.pin_chat_message(chat_id, msg.message_id, disable_notification=True)
            data[str(chat_id)]["pin_message_id"] = msg.message_id
            save_data(data)
    except Exception as e:
        logger.warning(f"Ошибка pin для {chat_id}: {e}")

# ====================== Обработка callback ======================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data, user = get_user(chat_id)
    state = user.get("state", "normal")

    if query.data == "start":
        user["active"] = True
        user["state"] = "normal"
        save_data(data)
        await send_menu(context.bot, chat_id,
                        "Привет, брат.\n\nЯ буду писать три раза в день — просто напомнить: сегодня не надо.\n\nКогда тяжело — жми «✊ Держусь».\nВсе получат пуш. Просто узнают, что ты ещё здесь.\nМожешь жать до 5 раз в день, если совсем пиздец.\n\nДержись, я рядом.",
                        main_menu_keyboard())
        await update_pin(context.bot, chat_id)

    elif query.data == "hold":
        today = NOW().date()
        last_date = user.get("hold_date")
        last_time = user.get("hold_time")
        count = user.get("hold_count", 0)
        if str(last_date) != str(today):
            count = 0
        if last_time and (NOW() - datetime.fromisoformat(last_time)).total_seconds() < 1800:
            minutes_left = int((1800 - (NOW() - datetime.fromisoformat(last_time)).total_seconds()) / 60)
            await send_menu(context.bot, chat_id, f"Погоди ещё {minutes_left} минут, брат.", main_menu_keyboard())
            return
        if count >= 5:
            await send_menu(context.bot, chat_id, "Сегодня это уже 5 раз, брат, тормози. Завтра сможешь отправить ещё. ✊", main_menu_keyboard())
            return
        user["hold_time"] = NOW().isoformat()
        user["hold_date"] = str(today)
        user["hold_count"] = count + 1
        save_data(data)
        await send_menu(context.bot, chat_id, random.choice(HOLD_RESPONSES), main_menu_keyboard())
        # отправка пушей другим активным
        for uid in [int(k) for k, v in load_data().items() if v.get("active") and int(k) != chat_id]:
            try:
                await context.bot.send_message(uid, "✊")
                await asyncio.sleep(0.08)
            except:
                pass

    elif query.data == "heavy":
        user["state"] = "heavy_menu"
        save_data(data)
        await send_menu(context.bot, chat_id, "Что будем делать?", heavy_menu_keyboard())

    elif query.data == "help":
        user["state"] = "help_mode"
        tip = get_next_tip(user)
        save_data(data)
        await send_menu(context.bot, chat_id, tip, help_menu_keyboard())

    elif query.data == "next_tip":
        if state == "help_mode":
            tip = get_next_tip(user)
            save_data(data)
            await send_menu(context.bot, chat_id, tip, help_menu_keyboard())

    elif query.data == "back":
        user["state"] = "normal"
        user["used_tips"] = []
        save_data(data)
        await send_menu(context.bot, chat_id, "че как?", main_menu_keyboard())

    elif query.data == "break":
        reset_streak(chat_id)
        user["state"] = "normal"
        save_data(data)
        await send_menu(context.bot, chat_id, "Ничего страшного.\nНачнём заново. Ты молодец, что сказал честно.", main_menu_keyboard())
        await update_pin(context.bot, chat_id)

    elif query.data == "almost":
        await send_menu(context.bot, chat_id, "Брат, что было?", heavy_menu_keyboard())

    elif query.data == "days":
        days = get_days(chat_id)
        best = user.get("best_streak", 0)
        msg = "Первый день." if days == 0 else "Прошёл 1 день." if days == 1 else f"Прошло {days} дней."
        if best > 0 and best != days:
            msg += f"\n\nТвой лучший стрик: {best} дней."
        await send_menu(context.bot, chat_id, msg, main_menu_keyboard())

    elif query.data == "tutut":
        await send_menu(context.bot, chat_id, random.choice(TU_TUT_FIRST) + "\n" + random.choice(TU_TUT_SECOND), main_menu_keyboard())

    elif query.data == "thanks":
        await send_menu(context.bot, chat_id, "Спасибо, брат. ❤️\n\nЕсли хочешь поддержать:\nСбер 2202 2084 3481 5313\n\nГлавное — держись.", main_menu_keyboard())

    elif query.data == "pause":
        user["active"] = False
        save_data(data)
        await send_menu(context.bot, chat_id, "Уведомления приостановлены. Жми ▶ Начать, когда будешь готов.", start_menu_keyboard())

# ====================== Пуши ======================
async def morning_job(context):
    for uid in [int(k) for k, v in load_data().items() if v.get("active")]:
        days = get_days(uid)
        text = MILESTONES.get(days, random.choice(MORNING_MESSAGES))
        await context.bot.send_message(uid, text)
        data, _ = get_user(uid)
        await update_pin(context.bot, uid)

async def evening_job(context):
    for uid in [int(k) for k, v in load_data().items() if v.get("active")]:
        await context.bot.send_message(uid, random.choice(EVENING_MESSAGES))

async def night_job(context):
    for uid in [int(k) for k, v in load_data().items() if v.get("active")]:
        await context.bot.send_message(uid, random.choice(NIGHT_MESSAGES))
        data, _ = get_user(uid)
        await update_pin(context.bot, uid)

# ====================== Ошибки ======================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)

# ====================== Основная ======================
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: handle_callback(Update(update_id=0, callback_query=None), c)))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_error_handler(error_handler)

    # Пуши
    for uid in [int(k) for k, v in load_data().items() if v.get("active")]:
        app.job_queue.run_daily(morning_job, time(9, 0, tzinfo=MOSCOW_TZ), chat_id=uid)
        app.job_queue.run_daily(evening_job, time(18, 0, tzinfo=MOSCOW_TZ), chat_id=uid)
        app.job_queue.run_daily(night_job, time(23, 0, tzinfo=MOSCOW_TZ), chat_id=uid)

    logger.info("Кент на посту ✊")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
