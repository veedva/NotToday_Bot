import logging
import random
import json
import os
import asyncio
from datetime import datetime, time
from filelock import FileLock
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
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

# ---- Тексты ----
MORNING_MESSAGES = ["Привет. Давай сегодня не будем, хорошо?", "Доброе утро, брат. Не сегодня.", "Привет. Держимся сегодня, да?"]
EVENING_MESSAGES = ["Брат, не сегодня. Держись.", "Эй, я тут. Давай не сегодня.", "Привет. Сегодня держимся, помнишь?"]
NIGHT_MESSAGES = ["Ты молодец. До завтра.", "Красавчик. Спокойной.", "Держался сегодня. Уважаю."]
HELP_TECHNIQUES = [
    "Бери и дыши так по кругу: вдох носом 4 сек → задержка 4 сек → выдох 4 сек → пауза 4 сек. Повтори 6–8 раз.",
    "Падай и делай 20–30 отжиманий или приседаний до жжения.",
    "Ледяная вода на лицо и шею 20–30 сек — мозг забывает про тягу.",
    "Выйди на балкон на 3–5 минут. Даже если -20°C — всё равно выйди."
]
TU_TUT_FIRST = ["Тут.", "Привет.", "А куда я денусь?", "Здесь.", "Тут, как всегда."]
TU_TUT_SECOND = ["Держимся.", "Я с тобой.", "Всё по плану?", "Не хочу сегодня.", "Сегодня не буду."]

# ---- Работа с данными ----
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
            "message_id": None,
            "menu_id": None,
            "hold_count": 0,
            "hold_date": None,
            "hold_time": None,
            "used_tips": []
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

# ---- Кнопки ----
def main_menu():
    keyboard = [
        [InlineKeyboardButton("✊ Держусь", callback_data="hold"), InlineKeyboardButton("😔 Тяжело", callback_data="heavy")],
        [InlineKeyboardButton("📊 Дни", callback_data="days"), InlineKeyboardButton("👋 Ты тут?", callback_data="tutut")],
        [InlineKeyboardButton("❤️ Спасибо", callback_data="thanks"), InlineKeyboardButton("⏸ Пауза", callback_data="pause")]
    ]
    return InlineKeyboardMarkup(keyboard)

def heavy_menu():
    keyboard = [
        [InlineKeyboardButton("💪 Помочь себе", callback_data="help"), InlineKeyboardButton("😅 Чуть не сорвался", callback_data="almost")],
        [InlineKeyboardButton("😞 Срыв", callback_data="fail"), InlineKeyboardButton("↩️ Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def help_menu():
    keyboard = [
        [InlineKeyboardButton("🔄 Ещё способ", callback_data="tip")],
        [InlineKeyboardButton("↩️ Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ---- Основные функции ----
async def send_or_edit(bot, chat_id, text, keyboard=None, message_id=None):
    if message_id:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard)
            return message_id
        except:
            msg = await bot.send_message(chat_id, text, reply_markup=keyboard)
            return msg.message_id
    else:
        msg = await bot.send_message(chat_id, text, reply_markup=keyboard)
        return msg.message_id

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data, user = get_user(chat_id)
    user["active"] = True
    user["state"] = "normal"
    save_data(data)

    text = ("Привет, брат.\n\nЯ буду писать три раза в день — просто напомнить: сегодня не надо.\n\n"
            "Когда тяжело — жми «✊ Держусь».\nВсе получат пуш. Просто узнают, что ты ещё здесь.\n"
            "Можешь жать до 5 раз в день, если совсем пиздец.\n\nДержись, я рядом.")

    # Приветственное сообщение
    if not user.get("message_id"):
        user["message_id"] = await send_or_edit(context.bot, chat_id, text)
    else:
        await send_or_edit(context.bot, chat_id, text, message_id=user["message_id"])

    # Меню «че как?»
    if not user.get("menu_id"):
        menu_msg = await context.bot.send_message(chat_id, "че как?", reply_markup=main_menu())
        user["menu_id"] = menu_msg.message_id
    else:
        await send_or_edit(context.bot, chat_id, "че как?", main_menu(), message_id=user["menu_id"])

    save_data(data)
    schedule_jobs(chat_id, context.job_queue)

# ---- Обработка кнопок ----
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    data, user = get_user(chat_id)
    await query.answer()
    state = user.get("state", "normal")

    if query.data == "hold":
        await handle_hold(chat_id, context)
    elif query.data == "heavy":
        user["state"] = "heavy_menu"
        save_data(data)
        await send_or_edit(context.bot, chat_id, "Что будем делать?", heavy_menu(), user["menu_id"])
    elif query.data == "help" and state == "heavy_menu":
        tip = get_next_tip(user)
        user["state"] = "help_mode"
        save_data(data)
        await send_or_edit(context.bot, chat_id, tip, help_menu(), user["menu_id"])
    elif query.data == "tip" and state == "help_mode":
        tip = get_next_tip(user)
        save_data(data)
        await send_or_edit(context.bot, chat_id, tip, help_menu(), user["menu_id"])
    elif query.data == "back":
        user["state"] = "normal"
        user["used_tips"] = []
        save_data(data)
        await send_or_edit(context.bot, chat_id, "че как?", main_menu(), user["menu_id"])
    elif query.data == "almost" and state == "heavy_menu":
        await send_or_edit(context.bot, chat_id, "Держись брат, скоро пройдет. ✊", main_menu(), user["menu_id"])
        user["state"] = "normal"
        save_data(data)
    elif query.data == "fail" and state == "heavy_menu":
        reset_streak(chat_id)
        await send_or_edit(context.bot, chat_id, "Ничего страшного. Начнём заново. Ты молодец, что сказал честно.", main_menu(), user["menu_id"])
        user["state"] = "normal"
        save_data(data)
    elif query.data == "days":
        days = get_days(chat_id)
        best = user.get("best_streak", 0)
        msg = "Первый день." if days == 0 else f"Прошло {days} дней."
        if best > 0 and best != days:
            msg += f"\nТвой лучший стрик: {best} дней."
        await send_or_edit(context.bot, chat_id, msg, main_menu(), user["menu_id"])
    elif query.data == "tutut":
        await asyncio.sleep(random.uniform(2.8, 5.5))
        await send_or_edit(context.bot, chat_id, random.choice(TU_TUT_FIRST), main_menu(), user["menu_id"])
        await asyncio.sleep(random.uniform(2.0, 4.5))
        await send_or_edit(context.bot, chat_id, random.choice(TU_TUT_SECOND), main_menu(), user["menu_id"])
    elif query.data == "thanks":
        text = "Спасибо, брат. ❤️\n\nЕсли хочешь поддержать:\nСбер 2202 2084 3481 5313\n\nГлавное — держись."
        await send_or_edit(context.bot, chat_id, text, main_menu(), user["menu_id"])
    elif query.data == "pause":
        user["active"] = False
        save_data(data)
        await send_or_edit(context.bot, chat_id, "Уведомления приостановлены. Жми ▶ Начать, когда будешь готов.", None, user["menu_id"])

# ---- Обработка «держусь» ----
async def handle_hold(chat_id, context):
    data, user = get_user(chat_id)
    today = NOW().date()
    last_date = user.get("hold_date")
    last_time = user.get("hold_time")
    count = user.get("hold_count", 0)
    if str(last_date) != str(today):
        count = 0
    if last_time:
        if (NOW() - datetime.fromisoformat(last_time)).total_seconds() < 1800:
            minutes_left = int((1800 - (NOW() - datetime.fromisoformat(last_time)).total_seconds()) / 60)
            await send_or_edit(context.bot, chat_id, f"Погоди ещё {minutes_left} минут, брат.", main_menu(), user["menu_id"])
            return
    if count >= 5:
        await send_or_edit(context.bot, chat_id, "Сегодня это уже 5 раз, брат, тормози. Завтра сможешь отправить еще. ✊", main_menu(), user["menu_id"])
        return
    await send_or_edit(context.bot, chat_id, "Отправлено. ✊", main_menu(), user["menu_id"])
    user["hold_time"] = NOW().isoformat()
    user["hold_date"] = str(today)
    user["hold_count"] = count + 1
    save_data(data)

# ---- Пуши ----
async def send_push(bot, chat_id, messages):
    data, user = get_user(chat_id)
    if not user.get("active"): return
    text = random.choice(messages)
    await send_or_edit(bot, chat_id, text, main_menu(), user["message_id"])

async def morning_job(context): await send_push(context.bot, context.job.chat_id, MORNING_MESSAGES)
async def evening_job(context): await send_push(context.bot, context.job.chat_id, EVENING_MESSAGES)
async def night_job(context): await send_push(context.bot, context.job.chat_id, NIGHT_MESSAGES)

# ---- Расписание ----
def schedule_jobs(chat_id, job_queue):
    for name in [f"morning_{chat_id}", f"evening_{chat_id}", f"night_{chat_id}"]:
        for job in job_queue.get_jobs_by_name(name):
            job.schedule_removal()
    job_queue.run_daily(morning_job, time(9, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"morning_{chat_id}")
    job_queue.run_daily(evening_job, time(18, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"evening_{chat_id}")
    job_queue.run_daily(night_job, time(23, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"night_{chat_id}")

# ---- Ошибки ----
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)

# ---- Главная ----
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_error_handler(error_handler)
    logger.info("Бот на посту ✊")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
