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

# ======================= Тексты =========================
MORNING_MESSAGES = [
    "Привет. Давай сегодня не будем, хорошо?",
    "Доброе утро, брат. Не сегодня.",
    "Привет. Держимся сегодня, да?",
    "Доброе. Сегодня дел много, нет наверное.",
    "Привет. Сегодня обойдёмся и так пиздец.",
    "Утро. Давай только не сегодня.",
    "Привет, брат. Сегодня пожалуй что ну его нахуй, знаешь.",
    "Доброе утро. Я напишу ёщё сегодня.",
    "Привет. Сегодня точно не надо.",
    "Доброе! Давай сегодня без этого вот.",
    "Привет лох. Денег жалко, да и ну его.",
    "Привет. Сегодня все будет нормально.",
    "Братан, доброе. Сегодня точно нет.",
    "Эй. Сегодня не в тему.",
    "Доброе утро. Не сегодня.",
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

TU_TUT_FIRST = ["Тут.", "Привет.", "А куда я денусь?", "Здесь.", "Тут, как всегда.", "Да, да, привет.", "Че как?", "Ага.", "Здраствуй.", "Тут. Не переживай."]
TU_TUT_SECOND = ["Держимся.", "Я с тобой.", "Всё по плану?", "Не хочу сегодня.", "Сегодня не буду.", "Я рядом.", "Держись.", "Все будет нормально.", "Я в деле.", "Всё под контролем."]

HOLD_RESPONSES = ["Отправлено. ✊", "Молодец. ✊", "Ты крутой. ✊", "Так держать. ✊"]

# =================== Упражнения и Советы =====================
HELP_TECHNIQUES = [
    "Дыши по кругу: вдох 4 сек → задержка 4 сек → выдох 4 сек → пауза 4 сек. Повтори 6–8 раз. Мозг переключается и тяга уходит.",
    "20–30 отжиманий или приседаний до жжения. Пока мышцы горят, голова не думает о херне.",
    "Ледяная вода на лицо и шею 20–30 сек. Шок мозга, тяга уходит.",
    "Выйди на улицу или открой окно. 3–5 мин свежего воздуха. Даже -20°C, всё равно выйди.",
    "Выпей холодной воды медленно маленькими глотками. Пока пьёшь — тяга слабеет.",
    "Запиши 3 вещи, за которые благодарен сегодня. Мозг переключается на позитив.",
    "Съешь что-то кислое или острое: лимон, горчица, имбирь, чили. Жжёт рот — голова забывает про тягу.",
    "Пройдись быстрым шагом 3–4 минуты под музыку. Движение переключает мозг.",
    "Сядь, выпрями спину, закрой глаза и просто дыши 1 мин. Перезагрузка.",
    "Круговые движения плечами и наклоны головы. Расслабление мышц и снижение тревоги."
]

HELP_ADVICE = [
    "Наркомания — это зависимость от вещества, она меняет мозг. Соси бибу теперь.",
    "Дни 1–3: сильная ломка, беспокойство, раздражение. Ограничь контакты с триггерами.",
    "Дни 4–7: тяга остаётся, появляются первые победы. Поддержка важна.",
    "Дни 8–14: настроение стабилизируется, тяга уменьшается. Продолжай упражнения.",
    "Дни 15–30: тело и мозг начинают восстанавливаться. Следи за сном и питанием.",
    "Дни 31–60: устойчивое улучшение. Прогресс виден, фиксируй достижения.",
    "Дни 61–90: привычки укреплены. Можно добавить новые цели.",
    "Дальше: организм и мозг адаптируются. Продолжай практики и поддерживай себя."
]

# ======================= Клавиатуры =========================
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("✊ Держусь"), KeyboardButton("😔 Тяжело")],
        [KeyboardButton("📊 Дни"), KeyboardButton("👋 Ты тут?")],
        [KeyboardButton("❤️ Спасибо"), KeyboardButton("⏸ Пауза")]
    ], resize_keyboard=True)

def get_start_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("▶ Начать")]], resize_keyboard=True)

def get_heavy_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💪 Упражнения"), KeyboardButton("📖 Советы")],
        [KeyboardButton("😞 Срыв"), KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)

def get_help_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔄 Ещё способ")],
        [KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)

# ======================= Работа с данными =========================
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
            "message_ids": [],
            "hold_count": 0,
            "hold_date": None,
            "hold_time": None,
            "used_tips": [],
            "used_advice": []
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

def get_next_advice(user_data: dict) -> str:
    used = user_data.setdefault("used_advice", [])
    if len(used) >= len(HELP_ADVICE):
        used.clear()
    available = [i for i in range(len(HELP_ADVICE)) if i not in used]
    choice = random.choice(available)
    used.append(choice)
    return HELP_ADVICE[choice]

# ======================= Отправка сообщений =========================
async def send(bot, chat_id, text, keyboard=None, save=True):
    kb = keyboard or get_main_keyboard()
    msg = await bot.send_message(chat_id, text, reply_markup=kb)
    if save:
        data, _ = get_user(chat_id)
        data[str(chat_id)].setdefault("message_ids", []).append(msg.message_id)
        if len(data[str(chat_id)]["message_ids"]) > 500:
            data[str(chat_id)]["message_ids"] = data[str(chat_id)]["message_ids"][-500:]
        save_data(data)
    return msg

# ======================= Задачи =========================
async def morning_job(context):
    chat_id = context.job.chat_id
    _, user = get_user(chat_id)
    if not user.get("active"): return
    days = get_days(chat_id)
    text = MILESTONES.get(days, random.choice(MORNING_MESSAGES))
    await send(context.bot, chat_id, text)

async def evening_job(context):
    chat_id = context.job.chat_id
    _, user = get_user(chat_id)
    if not user.get("active"): return
    await send(context.bot, chat_id, random.choice(EVENING_MESSAGES))

async def night_job(context):
    chat_id = context.job.chat_id
    _, user = get_user(chat_id)
    if not user.get("active"): return
    await send(context.bot, chat_id, random.choice(NIGHT_MESSAGES))

async def midnight_clean(context):
    chat_id = context.job.chat_id
    data, user = get_user(chat_id)
    ids = user.get("message_ids", [])
    user["message_ids"] = []
    save_data(data)
    for msg_id in ids:
        try:
            await context.bot.delete_message(chat_id, msg_id)
            await asyncio.sleep(0.05)
        except:
            pass

def schedule_jobs(chat_id, job_queue):
    for name in [f"morning_{chat_id}", f"evening_{chat_id}", f"night_{chat_id}", f"midnight_{chat_id}"]:
        for job in job_queue.get_jobs_by_name(name):
            job.schedule_removal()
    job_queue.run_daily(morning_job, time(9, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"morning_{chat_id}")
    job_queue.run_daily(evening_job, time(18, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"evening_{chat_id}")
    job_queue.run_daily(night_job, time(23, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"night_{chat_id}")
    job_queue.run_daily(midnight_clean, time(0, 1, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"midnight_{chat_id}")

# ======================= Команды =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data, user = get_user(chat_id)
    user["active"] = True
    user["state"] = "normal"
    save_data(data)
    await send(context.bot, chat_id,
        "Привет, брат.\n\n"
        "Я буду писать три раза в день — просто напомнить: сегодня не надо.\n\n"
        "Когда тяжело — жми «✊ Держусь».\n"
        "Все получат пуш. Просто узнают, что ты ещё здесь.\n"
        "Можешь жать до 5 раз в день, если совсем пиздец.\n\n"
        "Держись, я рядом.",
        save=False)
    schedule_jobs(chat_id, context.job_queue)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data, user = get_user(chat_id)
    user["active"] = False
    user["state"] = "normal"
    save_data(data)
    for name in [f"morning_{chat_id}", f"evening_{chat_id}", f"night_{chat_id}", f"midnight_{chat_id}"]:
        for job in context.job_queue.get_jobs_by_name(name):
            job.schedule_removal()
    await send(context.bot, chat_id, "Уведомления приостановлены. Жми ▶ Начать, когда будешь готов.", get_start_keyboard(), False)

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
            await send(context.bot, chat_id, f"Погоди ещё {minutes_left} минут, брат.")
            return
    if count >= 5:
        await send(context.bot, chat_id, "Сегодня это уже 5 раз, брат, тормози. Завтра сможешь отправить еще. ✊")
        return
    await send(context.bot, chat_id, random.choice(HOLD_RESPONSES), save=False)
    for uid in get_active_users():
        if uid != chat_id:
            try:
                await context.bot.send_message(uid, "✊")
                await asyncio.sleep(0.08)
            except:
                pass
    user["hold_time"] = NOW().isoformat()
    user["hold_date"] = str(today)
    user["hold_count"] = count + 1
    save_data(data)

# ======================= Обработка сообщений =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    data, user = get_user(chat_id)
    state = user.get("state", "normal")

    # Меню тяжело
    if state == "heavy_menu":
        if text == "💪 Упражнения":
            tip = get_next_tip(user)
            await send(context.bot, chat_id, tip, get_help_keyboard(), False)
            user["state"] = "help_mode_exercise"
            save_data(data)
            return
        if text == "📖 Советы":
            advice = get_next_advice(user)
            await send(context.bot, chat_id, advice, get_help_keyboard(), False)
            user["state"] = "help_mode_advice"
            save_data(data)
            return
        if text == "😞 Срыв":
            reset_streak(chat_id)
            await send(context.bot, chat_id, "Ничего страшного.\nНачнём заново. Ты молодец, что сказал честно.", get_main_keyboard(), False)
            user["state"] = "normal"
            save_data(data)
            return
        if text == "↩️ Назад":
            await send(context.bot, chat_id, "Главное меню.", get_main_keyboard(), False)
            user["state"] = "normal"
            save_data(data)
            return

    # Режим показа упражнений/советов
    if state.startswith("help_mode"):
        if text == "🔄 Ещё способ":
            if state == "help_mode_exercise":
                tip = get_next_tip(user)
                await send(context.bot, chat_id, tip, get_help_keyboard(), False)
            else:
                advice = get_next_advice(user)
                await send(context.bot, chat_id, advice, get_help_keyboard(), False)
            save_data(data)
            return
        if text == "↩️ Назад":
            await send(context.bot, chat_id, "Главное меню.", get_heavy_keyboard(), False)
            user["state"] = "heavy_menu"
            save_data(data)
            return

    # Главное меню
    if text == "✊ Держусь":
        await handle_hold(chat_id, context)
        return
    if text == "😔 Тяжело":
        await send(context.bot, chat_id, "Выбирай:", get_heavy_keyboard(), False)
        user["state"] = "heavy_menu"
        save_data(data)
        return
    if text == "📊 Дни":
        days = get_days(chat_id)
        await send(context.bot, chat_id, f"Ты держишься {days} дней.\nЛучший стрик: {user.get('best_streak',0)}", get_main_keyboard(), False)
        return
    if text == "👋 Ты тут?":
        await asyncio.sleep(random.randint(2,5))
        await send(context.bot, chat_id, random.choice(TU_TUT_FIRST), get_main_keyboard(), False)
        await asyncio.sleep(random.randint(2,4))
        await send(context.bot, chat_id, random.choice(TU_TUT_SECOND), get_main_keyboard(), False)
        return
    if text == "⏸ Пауза":
        await stop(update, context)
        return
    if text == "❤️ Спасибо":
        await send(context.bot, chat_id, "Рад, что помогаю.", get_main_keyboard(), False)
        return
    if text == "▶ Начать":
        await start(update, context)
        return

# ======================= Main =========================
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
