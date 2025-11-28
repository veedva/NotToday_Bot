import logging
import random
import json
import os
import asyncio
from datetime import datetime, time
from filelock import FileLock
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
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

MORNING_MESSAGES = [
    "Привет. Давай сегодня не будем, хорошо?",
    "Доброе утро, брат. Не сегодня.",
    "Привет. Держимся сегодня, да?",
    "Доброе. Сегодня дел много, нет наверное.",
    "Привет. Сегодня обойдёмся и так пиздец.",
    "Утро. Давай только не сегодня.",
    "Привет, брат. Сегодня пожалуй что ну его нахуй, знаешь.",
    "Доброе утро. НУ не прям сегодня же.",
    "Привет. Сегодня точно не надо.",
    "Доброе! Давай сегодня без этого.",
    "Утро. Денег жалко, да и ну его.",
    "Привет. Сегодня легко обойдёмся и без этого.",
    "Братан, доброе. Сегодня точно нет.",
    "Эй. Сегодня не в тему.",
    "Доброе утро. Только не сегодня.",
    "Привет. Может завтра, но сегодня нет.",
    "Утро. Сегодня спокойно обходимся.",
    "Че как? Сегодня не стоит пожалуй."
]

EVENING_MESSAGES = [
    "Брат, не сегодня. Держись.",
    "Эй, я тут. Давай не сегодня.",
    "Привет. Сегодня держимся, помнишь?",
    "Брат, держись. Сегодня нет.",
    "Эй. Ещё чуть-чуть. Не сегодня.",
    "Я с тобой. Сегодня точно нет.",
    "Привет. Давай обойдёмся.",
    "Брат, мы же решили — не сегодня.",
    "Держись там. Сегодня мимо.",
    "Привет. Сегодня пропустим.",
    "Эй. Сегодня точно можно без этого.",
    "Братан, сегодня не надо.",
    "Привет. Может завтра, сегодня мимо.",
    "Как дела? Сегодня обойдёмся.",
    "Эй, брат. Сегодня не будем.",
    "Привет. Сегодня точно ни к чему.",
    "Братан, ну может завтра, а сегодня нет?"
]

NIGHT_MESSAGES = [
    "Ты молодец. До завтра.",
    "Красавчик. Спокойной.",
    "Держался сегодня. Уважаю.",
    "Сегодня справились. До завтра.",
    "Молодец, держишься.",
    "Ещё один день позади.",
    "Ты сильный. До завтра.",
    "Сегодня получилось. Отдыхай.",
    "Справился. Уважение.",
    "Держался весь день. Красава.",
    "Нормально прошёл день.",
    "Сегодня справились. Отдыхай.",
    "Ещё один день прошёл. До завтра.",
    "Держались сегодня. Молодцы.",
    "День зачётный. Спокойной.",
    "Справились. До завтра.",
    "Сегодня получилось. Отдыхай."
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
    "Бери и дыши так по кругу: вдох носом 4 секунды → задержи дыхание считая до 4 → выдох ртом 4 секунды → не дыши 4 секунды. Повтори 6–8 раз подряд. Через минуту мозг переключается и тяга уходит, проверено тысячу раз.",
    "Прямо сейчас падай и делай 20–30 отжиманий или приседаний до жжения в мышцах. Пока мышцы горят — башка не думает о херне.",
    "Открой кран с ледяной водой и суй туда лицо + шею на 20–30 секунд. Мозг получает шок и на несколько минут забывает про всё остальное.",
    "Выйди на балкон или просто открой окно настежь. Стоять и дышать свежим воздухом 3–5 минут. Даже если -20, всё равно выйди.",
    "Налей самый холодный стакан воды из-под крана и пей медленно-медленно, маленькими глотками. Пока пьёшь — тяга слабеет.",
    "Возьми телефон, открой заметки и напиши три вещи, за которые ты сегодня реально благодарен. Хоть «не просрал день», хоть «есть крыша над головой». Мозг переключается на позитив.",
    "Съешь что-то максимально кислое или острое: дольку лимона, ложку горчицы, кусок имбиря, чили-перец. Жжёт рот — башка забывает про тягу.",
    "Включи любой трек и просто ходи быстрым шагом по квартире 3–4 минуты. Главное — не останавливаться.",
    "Сядь на стул или на пол, выпрями спину, руки на колени, закрой глаза и просто сиди минуту молча. Ничего не делай, просто дыши. Это как перезагрузка.",
    "Делай круговые движения плечами назад-вперёд по 15 раз в каждую сторону, потом наклоны головы. Мышцы расслабняются, тревога уходит.",
    "Поставь таймер на 10 минут и говори себе: «Я просто подожду 10 минут, потом решу». В 95 % случаев через 10 минут уже не хочется.",
    "Открой камеру на телефоне, посмотри себе в глаза и скажи вслух: «Я сильнее этой хуйни». Даже если звучит тупо — работает."
]

TU_TUT_FIRST = ["Тут.", "Привет.", "А куда я денусь?", "Здесь.", "Тут, как всегда.", "Да, да, привет.", "Че как?", "Ага.", "Здраствуй.", "Тут. Не переживай."]
TU_TUT_SECOND = ["Держимся.", "Я с тобой.", "Всё по плану?", "Не хочу сегодня.", "Сегодня не буду.", "Я рядом.", "Держись.", "Все будет нормально.", "Я в деле.", "Всё под контролем."]
HOLD_RESPONSES = ["Отправлено. ✊", "Молодец. ✊", "Красава. ✊", "Респект. ✊", "Так держать. ✊"]

def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Держусь"), KeyboardButton("Тяжело")],
        [KeyboardButton("Дни"), KeyboardButton("Ты тут?")],
        [KeyboardButton("Спасибо"), KeyboardButton("Пауза")]
    ], resize_keyboard=True)

def get_start_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("Начать")]], resize_keyboard=True)

def get_heavy_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Помочь себе"), KeyboardButton("Чуть не сорвался")],
        [KeyboardButton("Срыв"), KeyboardButton("Назад")]
    ], resize_keyboard=True)

def get_help_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Ещё способ")],
        [KeyboardButton("Назад")]
    ], resize_keyboard=True)

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
            "daily_messages": [],
            "hold_count": 0,
            "hold_date": None,
            "hold_time": None,
            "pinned_message_id": None,
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

def get_active_users():
    return [int(uid) for uid, u in load_data().items() if u.get("active")]

def get_next_tip(user_data: dict) -> str:
    used = user_data.setdefault("used_tips", [])
    if len(used) >= len(HELP_TECHNIQUES):
        used.clear()
    available = [i for i in range(len(HELP_TECHNIQUES)) if i not in used]
    choice = random.choice(available)
    used.append(choice)
    return HELP_TECHNIQUES[choice]

async def send(bot, chat_id, text, keyboard=None, lifetime=None):
    kb = keyboard or get_main_keyboard()
    msg = await bot.send_message(chat_id, text, reply_markup=kb)
    if lifetime == "day":
        data, _ = get_user(chat_id)
        data[str(chat_id)].setdefault("daily_messages", []).append(msg.message_id)
        save_data(data)
    if isinstance(lifetime, (int, float)):
        asyncio.create_task(_delete_after(bot, chat_id, msg.message_id, lifetime))
    return msg

async def _delete_after(bot, chat_id, message_id, delay):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except:
        pass

async def midnight_cleanup_daily(context):
    chat_id = context.job.chat_id
    data, user = get_user(chat_id)
    ids = user.get("daily_messages", [])
    user["daily_messages"] = []
    save_data(data)
    for msg_id in ids:
        try:
            await context.bot.delete_message(chat_id, msg_id)
            await asyncio.sleep(0.1)
        except:
            pass

async def update_pin(bot, chat_id):
    days = get_days(chat_id)
    _, user = get_user(chat_id)
    best = user.get("best_streak", 0)
    text = f"Первый день • Лучший стрик: {best}" if days == 0 else f"День {days} • Лучший стрик: {best}"
    pin_id = user.get("pinned_message_id")
    try:
        if pin_id:
            await bot.edit_message_text(chat_id=chat_id, message_id=pin_id, text=text)
        else:
            msg = await bot.send_message(chat_id, text)
            await bot.pin_chat_message(chat_id, msg.message_id, disable_notification=True)
            data, _ = get_user(chat_id)
            data[str(chat_id)]["pinned_message_id"] = msg.message_id
            save_data(data)
    except Exception as e:
        logger.warning(f"Ошибка pin для {chat_id}: {e}")

async def morning_job(context):
    chat_id = context.job.chat_id
    _, user = get_user(chat_id)
    if not user.get("active"): return
    days = get_days(chat_id)
    text = MILESTONES.get(days, random.choice(MORNING_MESSAGES))
    await send(context.bot, chat_id, text, lifetime="day")
    await update_pin(context.bot, chat_id)

async def evening_job(context):
    chat_id = context.job.chat_id
    _, user = get_user(chat_id)
    if not user.get("active"): return
    await send(context.bot, chat_id, random.choice(EVENING_MESSAGES), lifetime="day")

async def night_job(context):
    chat_id = context.job.chat_id
    _, user = get_user(chat_id)
    if not user.get("active"): return
    await send(context.bot, chat_id, random.choice(NIGHT_MESSAGES), lifetime="day")
    await update_pin(context.bot, chat_id)

def schedule_jobs(chat_id, job_queue):
    for name in [f"morning_{chat_id}", f"evening_{chat_id}", f"night_{chat_id}", f"midnight_daily_{chat_id}"]:
        for job in job_queue.get_jobs_by_name(name):
            job.schedule_removal()
    job_queue.run_daily(morning_job, time(9, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"morning_{chat_id}")
    job_queue.run_daily(evening_job, time(18, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"evening_{chat_id}")
    job_queue.run_daily(night_job, time(23, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"night_{chat_id}")
    job_queue.run_daily(midnight_cleanup_daily, time(0, 5, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"midnight_daily_{chat_id}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data, user = get_user(chat_id)
    user["active"] = True
    user["state"] = "normal"
    save_data(data)
    await send(context.bot, chat_id,
        "Привет, брат.\n\n"
        "Я буду писать три раза в день — просто напомнить: сегодня не надо.\n\n"
        "Когда тяжело — жми «Держусь».\n"
        "Все получат пуш. Просто узнают, что ты ещё здесь.\n"
        "Можешь жать до 5 раз в день, если совсем пиздец.\n\n"
        "Держись, я рядом.")
    await update_pin(context.bot, chat_id)
    schedule_jobs(chat_id, context.job_queue)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data, user = get_user(chat_id)
    user["active"] = False
    user["state"] = "normal"
    save_data(data)
    for name in [f"morning_{chat_id}", f"evening_{chat_id}", f"night_{chat_id}", f"midnight_daily_{chat_id}"]:
        for job in context.job_queue.get_jobs_by_name(name):
            job.schedule_removal()
    await send(context.bot, chat_id, "Уведомления приостановлены. Жми Начать, когда будешь готов.", get_start_keyboard())

async def handle_hold(chat_id, context):
    data, user = get_user(chat_id)
    today = NOW().date()
    last_date = user.get("hold_date")
    last_time = user.get("hold_time")
    count = user.get("hold_count", 0)
    if str(last_date) != str(today):
        count = 0
    if last_time and (NOW() - datetime.fromisoformat(last_time)).total_seconds() < 1800:
        minutes_left = int((1800 - (NOW() - datetime.fromisoformat(last_time)).total_seconds()) / 60)
        await send(context.bot, chat_id, f"Погоди ещё {minutes_left} минут, брат.", lifetime=60)
        return
    if count >= 5:
        await send(context.bot, chat_id, "Сегодня это уже 5 раз, брат, тормози. Завтра сможешь отправить еще.", lifetime=60)
        return
    await send(context.bot, chat_id, random.choice(HOLD_RESPONSES), lifetime=45)
    for uid in get_active_users():
        if uid != chat_id:
            try:
                await context.bot.send_message(uid, "")
                await asyncio.sleep(0.08)
            except:
                pass
    user["hold_time"] = NOW().isoformat()
    user["hold_date"] = str(today)
    user["hold_count"] = count + 1
    save_data(data)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    data, user = get_user(chat_id)
    state = user.get("state", "normal")

    if state == "heavy_menu":
        if text == "Помочь себе":
            tip = get_next_tip(user)
            await send(context.bot, chat_id, tip, get_help_keyboard(), lifetime=60)
            user["state"] = "help_mode"
            save_data(data)
            return
        if text == "Срыв":
            reset_streak(chat_id)
            await send(context.bot, chat_id, "Ничего страшного.\nНачнём заново. Ты молодец, что сказал честно.", get_main_keyboard(), lifetime=60)
            await update_pin(context.bot, chat_id)
            user["state"] = "normal"
            save_data(data)
            return
        if text == "Чуть не сорвался":
            await send(context.bot, chat_id, "Красавчик. Это и есть победа.", get_main_keyboard(), lifetime=60)
            user["state"] = "normal"
            save_data(data)
            return
        if text == "Назад":
            user["state"] = "normal"
            user["used_tips"] = []
            save_data(data)
            await send(context.bot, chat_id, "Держись.", get_main_keyboard(), lifetime=60)
            return

    if state == "help_mode":
        if text == "Ещё способ":
            tip = get_next_tip(user)
            await send(context.bot, chat_id, tip, get_help_keyboard(), lifetime=60)
            save_data(data)
            return
        if text == "Назад":
            user["state"] = "normal"
            user["used_tips"] = []
            save_data(data)
            await send(context.bot, chat_id, "Держись там.", get_main_keyboard(), lifetime=60)
            return

    if text == "Начать":
        await start(update, context)
    elif text == "Ты тут?":
        await asyncio.sleep(random.uniform(2.8, 5.5))
        await send(context.bot, chat_id, random.choice(TU_TUT_FIRST), lifetime=45)
        await asyncio.sleep(random.uniform(2.0, 4.5))
        await send(context.bot, chat_id, random.choice(TU_TUT_SECOND), lifetime=45)
    elif text == "Держусь":
        await handle_hold(chat_id, context)
    elif text == "Тяжело":
        user["state"] = "heavy_menu"
        user["used_tips"] = []
        save_data(data)
        await send(context.bot, chat_id, "Что будем делать?", get_heavy_keyboard(), lifetime=60)
    elif text == "Дни":
        days = get_days(chat_id)
        best = user.get("best_streak", 0)
        msg = "Первый день." if days == 0 else "Прошёл 1 день." if days == 1 else f"Прошло {days} дней."
        if best > 0 and best != days:
            msg += f"\n\nТвой лучший стрик: {best} дней."
        await send(context.bot, chat_id, msg, lifetime=60)
    elif text == "Спасибо":
        await send(context.bot, chat_id,
            "Спасибо, брат.\n\nЕсли хочешь поддержать:\nСбер 2202 2084 3481 5313\n\nГлавное — держись.",
            lifetime=60)
    elif text == "Пауза":
        await stop(update, context)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    logger.info("Кент на посту")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
