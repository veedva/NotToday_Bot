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

# Сообщения
MORNING_MESSAGES = ["Привет. Давай сегодня не будем, хорошо?", "Доброе утро, брат. Не сегодня.", "..."]
EVENING_MESSAGES = ["Брат, не сегодня. Держись.", "..."]
NIGHT_MESSAGES = ["Ты молодец. До завтра.", "..."]
MILESTONES = {3: "Три дня уже. Неплохо идём.", 7: "Неделя прошла. Продолжаем.", 14: "Две недели! Хорошо идёт."}
HELP_TECHNIQUES = ["Дыши 4-4-4-4...", "20 отжиманий...", "..."]
TU_TUT_FIRST = ["Тут.", "Привет.", "А куда я денусь?", "..."]
TU_TUT_SECOND = ["Держимся.", "Я с тобой.", "Всё по плану?", "..."]
HOLD_RESPONSES = ["Отправлено. ✊", "Молодец. ✊", "Красава. ✊"]

# --- Работа с данными ---
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

# --- Клавиатуры ---
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("✊ Держусь", callback_data="hold"),
         InlineKeyboardButton("😔 Тяжело", callback_data="heavy")],
        [InlineKeyboardButton("📊 Дни", callback_data="days"),
         InlineKeyboardButton("👋 Ты тут?", callback_data="tutut")],
        [InlineKeyboardButton("❤️ Спасибо", callback_data="thanks"),
         InlineKeyboardButton("⏸ Пауза", callback_data="pause")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_heavy_menu():
    keyboard = [
        [InlineKeyboardButton("💪 Помочь себе", callback_data="help_tip"),
         InlineKeyboardButton("😅 Чуть не сорвался", callback_data="almost_fail")],
        [InlineKeyboardButton("😞 Срыв", callback_data="fail"),
         InlineKeyboardButton("↩️ Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_help_menu():
    keyboard = [
        [InlineKeyboardButton("🔄 Ещё способ", callback_data="another_tip")],
        [InlineKeyboardButton("↩️ Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Основной функционал ---
async def send_main_menu(bot, chat_id):
    await bot.send_message(chat_id, "че как?", reply_markup=get_main_menu())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data, user = get_user(chat_id)
    user["active"] = True
    user["state"] = "normal"
    save_data(data)
    await context.bot.send_message(chat_id,
        "Привет, брат.\n\nЯ буду писать три раза в день — просто напомнить: сегодня не надо.\n\n"
        "Когда тяжело — жми «✊ Держусь».\n"
        "Все получат пуш. Просто узнают, что ты ещё здесь.\n"
        "Можешь жать до 5 раз в день, если совсем пиздец.\n\n"
        "Держись, я рядом.")
    await send_main_menu(context.bot, chat_id)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data, user = get_user(chat_id)
    state = user.get("state", "normal")

    if query.data == "hold":
        today = NOW().date()
        last_date = user.get("hold_date")
        last_time = user.get("hold_time")
        count = user.get("hold_count", 0)
        if str(last_date) != str(today):
            count = 0
        if last_time:
            if (NOW() - datetime.fromisoformat(last_time)).total_seconds() < 1800:
                minutes_left = int((1800 - (NOW() - datetime.fromisoformat(last_time)).total_seconds()) / 60)
                await query.message.edit_text(f"Погоди ещё {minutes_left} минут, брат.", reply_markup=None)
                return
        if count >= 5:
            await query.message.edit_text("Сегодня это уже 5 раз, брат, тормози. Завтра сможешь отправить еще. ✊", reply_markup=None)
            return
        await query.message.edit_text(random.choice(HOLD_RESPONSES), reply_markup=None)
        user["hold_time"] = NOW().isoformat()
        user["hold_date"] = str(today)
        user["hold_count"] = count + 1
        save_data(data)
        await send_main_menu(context.bot, chat_id)

    elif query.data == "heavy":
        user["state"] = "heavy_menu"
        save_data(data)
        await query.message.edit_text("Что будем делать?", reply_markup=get_heavy_menu())

    elif query.data == "help_tip":
        tip = get_next_tip(user)
        user["state"] = "help_mode"
        save_data(data)
        await query.message.edit_text(tip, reply_markup=get_help_menu())

    elif query.data == "another_tip":
        tip = get_next_tip(user)
        save_data(data)
        await query.message.edit_text(tip, reply_markup=get_help_menu())

    elif query.data == "back":
        user["state"] = "normal"
        user["used_tips"] = []
        save_data(data)
        await send_main_menu(context.bot, chat_id)

    elif query.data == "almost_fail":
        await query.message.edit_text("А че было?", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Скучно", callback_data="reason_bored"),
             InlineKeyboardButton("Да тянет пиздец", callback_data="reason_strong")],
            [InlineKeyboardButton("↩️ Назад", callback_data="back")]
        ]))

    elif query.data.startswith("reason_"):
        if query.data == "reason_strong":
            await query.message.edit_text("Научные исследования показывают, что чтобы увидеть результат, нужно подождать немного. Так что держись, брат!", reply_markup=get_main_menu())
        elif query.data == "reason_bored":
            await query.message.edit_text("Ну ебать, держись, займи себя чем-нибудь!", reply_markup=get_main_menu())

    elif query.data == "fail":
        reset_streak(chat_id)
        user["state"] = "normal"
        save_data(data)
        await query.message.edit_text("Ничего страшного.\nНачнём заново. Ты молодец, что сказал честно.", reply_markup=get_main_menu())

    elif query.data == "tutut":
        await query.message.edit_text(random.choice(TU_TUT_FIRST))
        await asyncio.sleep(1)
        await query.message.reply_text(random.choice(TU_TUT_SECOND), reply_markup=get_main_menu())

    elif query.data == "days":
        days = get_days(chat_id)
        best = user.get("best_streak", 0)
        msg = "Первый день." if days == 0 else f"Прошло {days} дней."
        if best > 0 and best != days:
            msg += f"\n\nТвой лучший стрик: {best} дней."
        await query.message.edit_text(msg, reply_markup=get_main_menu())

    elif query.data == "thanks":
        await query.message.edit_text("Спасибо, брат. ❤️\n\nЕсли хочешь поддержать:\nСбер 2202 2084 3481 5313\n\nГлавное — держись.", reply_markup=get_main_menu())

    elif query.data == "pause":
        user["active"] = False
        save_data(data)
        start_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("▶ Начать", callback_data="start_again")]])
        await query.message.edit_text("Уведомления приостановлены.", reply_markup=None)
        await query.message.reply_text("Жми ▶ Начать, когда будешь готов.", reply_markup=start_keyboard)

    elif query.data == "start_again":
        user["active"] = True
        user["state"] = "normal"
        save_data(data)
        await query.message.edit_text("Привет, брат.\n\nЯ снова на посту.", reply_markup=None)
        await send_main_menu(context.bot, chat_id)

# --- Пуши ---
async def morning_job(context):
    for uid in get_active_users():
        await context.bot.send_message(uid, random.choice(MORNING_MESSAGES))

async def evening_job(context):
    for uid in get_active_users():
        await context.bot.send_message(uid, random.choice(EVENING_MESSAGES))

async def night_job(context):
    for uid in get_active_users():
        await context.bot.send_message(uid, random.choice(NIGHT_MESSAGES))

def get_active_users():
    return [int(uid) for uid, u in load_data().items() if u.get("active")]

# --- Ошибки ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)

# --- Запуск ---
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_error_handler(error_handler)

    tz = MOSCOW_TZ
    # Пуши
    app.job_queue.run_daily(morning_job, time(9, 0, tzinfo=tz))
    app.job_queue.run_daily(evening_job, time(18, 0, tzinfo=tz))
    app.job_queue.run_daily(night_job, time(23, 0, tzinfo=tz))

    logger.info("Кент на посту ✊")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
