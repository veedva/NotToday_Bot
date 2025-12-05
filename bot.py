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
    raise ValueError("BOT_TOKEN не установлен! Поставь его в переменные окружения.")

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
    "Доброе утро. Я напишу ещё сегодня.",
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
    "Справлись. До завтра.",
    "Сегодня получилось. Отдыхай."
]

MILESTONES = {
    3: "Три дня уже. Неплохо идём, брат.",
    7: "Неделя. Понимаешь, да? Это уже серьёзно.",
    14: "Две недели. Ты реально держишься.",
    30: "Месяц без этой хуйни. Уважаю по-настоящему.",
    60: "Два месяца. Это уже другой уровень.",
    90: "Три месяца. Ты — машина.",
    180: "Полгода. Легенда.",
    365: "Год чистым. Ты сделал это, брат."
}

TU_TUT_FIRST = ["Тут.", "Привет.", "А куда я денусь?", "Здесь.", "Тут, как всегда.", "Да, да, привет.", "Че как?", "Ага.", "Здраствуй.", "Тут. Не переживай."]
TU_TUT_SECOND = ["Держимся.", "Я с тобой.", "Всё по плану?", "Не хочу сегодня.", "Сегодня не буду.", "Я рядом.", "Держись.", "Всё будет нормально.", "Я в деле.", "Всё под контролем."]

HOLD_RESPONSES = ["Отправлено. ✊", "Молодец. ✊", "Ты крутой. ✊", "Так держать. ✊"]

HELP_TECHNIQUES = [
    "Дыши по кругу: вдох 4 сек → задержка 4 сек → выдох 4 сек → пауза 4 сек. Повтори 6–8 раз.",
    "20–30 отжиманий или приседаний до жжения.",
    "Ледяная вода на лицо и шею 20–30 сек.",
    "Выйди на улицу или открой окно. 3–5 мин свежего воздуха.",
    "Выпей холодной воды медленно маленькими глотками.",
    "Запиши 3 вещи, за которые благодарен сегодня.",
    "Съешь что-то кислое или острое: лимон, горчица, имбирь, чили.",
    "Пройдись быстрым шагом 3–4 минуты под музыку.",
    "Сядь, выпрями спину, закрой глаза и просто дыши 1 минуту.",
    "Круговые движения плечами и наклоны головы."
]

HELP_ADVICE = [
    "Наркомания — это зависимость от вещества, она меняет мозг. Теперь держимся.",
    "Дни 1–3: сильная ломка, раздражение. Ограничь триггеры.",
    "Дни 4–7: тяга остаётся, но уже есть первые победы.",
    "Дни 8–14: настроение выравнивается, тяга слабеет.",
    "Дни 15–30: тело начинает восстанавливаться. Спи и ешь нормально.",
    "Дни 31–60: прогресс виден всем. Фиксируй достижения.",
    "Дни 61–90: новые привычки закрепляются.",
    "Дальше — ты уже другой человек. Продолжай."
]

# ======================= Клавиатуры =========================
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("✊ Держусь"), KeyboardButton("Тяжело")],
        [KeyboardButton("Дни"), KeyboardButton("Ты тут?")],
        [KeyboardButton("Спасибо"), KeyboardButton("Пауза")]
    ], resize_keyboard=True)

def get_start_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("Начать")]], resize_keyboard=True)

def get_heavy_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Упражнения"), KeyboardButton("Советы")],
        [KeyboardButton("Срыв"), KeyboardButton("Назад")]
    ], resize_keyboard=True)

def get_help_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Ещё способ")],
        [KeyboardButton("Назад в меню")]
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
            "start_date": None,
            "active": False,
            "best_streak": 0,
            "hold_count_today": 0,
            "last_hold_date": None,
            "last_hold_time": None,
            "used_tips": [],
            "used_advice": [],
            "message_ids": []
        }
        save_data(data)
    return data, data[uid]

def get_days(user_id):
    _, user = get_user(user_id)
    if not user["start_date"]:
        return 0
    start = datetime.fromisoformat(user["start_date"]).date()
    return (NOW().date() - start).days

def get_active_users():
    data = load_data()
    return [int(uid) for uid, u in data.items() if u.get("active")]

def get_next_tip(user_data):
    used = user_data["used_tips"]
    available = [i for i in range(len(HELP_TECHNIQUES)) if i not in used]
    if not available:
        used.clear()
        available = list(range(len(HELP_TECHNIQUES)))
    choice = random.choice(available)
    used.append(choice)
    return HELP_TECHNIQUES[choice]

def get_next_advice(user_data):
    used = user_data["used_advice"]
    available = [i for i in range(len(HELP_ADVICE)) if i not in used]
    if not available:
        used.clear()
        available = list(range(len(HELP_ADVICE)))
    choice = random.choice(available)
    used.append(choice)
    return HELP_ADVICE[choice]

# ======================= Отправка и чистка =========================
async def send(bot, chat_id, text, keyboard=None, save=True):
    kb = keyboard or get_main_keyboard()
    msg = await bot.send_message(chat_id, text, reply_markup=kb)
    if save:
        _, user = get_user(chat_id)
        user["message_ids"].append(msg.message_id)
        if len(user["message_ids"]) > 500:
            user["message_ids"] = user["message_ids"][-500:]
        save_data(load_data())
    return msg

async def midnight_clean(context):
    chat_id = context.job.chat_id
    _, user = get_user(chat_id)
    for msg_id in user.get("message_ids", []):
        try:
            await context.bot.delete_message(chat_id, msg_id)
            await asyncio.sleep(0.05)
        except:
            pass
    user["message_ids"] = []

# ======================= Джобы =========================
def schedule_jobs(chat_id, job_queue):
    names = [f"morning_{chat_id}", f"evening_{chat_id}", f"night_{chat_id}", f"midnight_{chat_id}"]
    for name in names:
        for job in job_queue.get_jobs_by_name(name):
            job.schedule_removal()

    job_queue.run_daily(lambda c: morning_job(c, chat_id), time(9, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"morning_{chat_id}")
    job_queue.run_daily(lambda c: evening_job(c, chat_id), time(18, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"evening_{chat_id}")
    job_queue.run_daily(lambda c: night_job(c, chat_id), time(23, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"night_{chat_id}")
    job_queue.run_daily(midnight_clean, time(0, 1, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"midnight_{chat_id}")

async def morning_job(context, chat_id):
    _, user = get_user(chat_id)
    if not user["active"]: return
    days = get_days(chat_id)
    text = MILESTONES.get(days, random.choice(MORNING_MESSAGES))
    await send(context.bot, chat_id, text)
    if days in MILESTONES:
        await send(context.bot, chat_id, MILESTONES[days])

async def evening_job(context, chat_id):
    _, user = get_user(chat_id)
    if not user["active"]: return
    await send(context.bot, chat_id, random.choice(EVENING_MESSAGES))

async def night_job(context, chat_id):
    _, user = get_user(chat_id)
    if not user["active"]: return
    await send(context.bot, chat_id, random.choice(NIGHT_MESSAGES))

# ======================= Держусь =========================
async def handle_hold(chat_id, context):
    data, user = get_user(chat_id)
    today = NOW().date()
    count_today = user.get("hold_count_today", 0)
    last_time = user.get("last_hold_time")

    if user.get("last_hold_date") != str(today):
        count_today = 0

    if last_time:
        delta = (NOW() - datetime.fromisoformat(last_time)).total_seconds()
        if delta < 1800:  # 30 минут
            mins = int((1800 - delta) // 60) + 1
            await send(context.bot, chat_id, f"Погоди ещё {mins} мин, брат.", save=False)
            return

    if count_today >= 5:
        await send(context.bot, chat_id, "Сегодня уже 5 раз, брат. Хватит на сегодня ✊\nЗавтра снова сможешь.", save=False)
        return

    await send(context.bot, chat_id, random.choice(HOLD_RESPONSES), save=False)

    for uid in get_active_users():
        if uid != chat_id:
            try:
                await context.bot.send_message(uid, "✊")
                await asyncio.sleep(0.15)
            except:
                pass

    user["last_hold_time"] = NOW().isoformat()
    user["last_hold_date"] = str(today)
    user["hold_count_today"] = count_today + 1
    save_data(data)

# ======================= Команды и обработка =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data, user = get_user(chat_id)
    user["active"] = True
    user["start_date"] = NOW().isoformat()
    save_data(data)
    await send(context.bot, chat_id,
        "Привет, брат.\n\n"
        "Я буду писать три раза в день — просто напомнить: сегодня не надо.\n"
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
    save_data(data)
    for name in [f"morning_{chat_id}", f"evening_{chat_id}", f"night_{chat_id}", f"midnight_{chat_id}"]:
        for job in context.job_queue.get_jobs_by_name(name):
            job.schedule_removal()
    await send(context.bot, chat_id, "Уведомления приостановлены.\nЖми ▶ Начать, когда будешь готов.", get_start_keyboard(), False)

def reset_streak(user_id):
    data, user = get_user(user_id)
    current = get_days(user_id)
    if current > user["best_streak"]:
        user["best_streak"] = current
    user["start_date"] = NOW().isoformat()
    user["hold_count_today"] = 0
    user["last_hold_date"] = None
    user["last_hold_time"] = None
    user["used_tips"] = []
    user["used_advice"] = []
    save_data(data)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    _, user = get_user(chat_id)

    if text == "▶ Начать":
        await start(update, context)
        return

    if not user["active"]:
        return

    if text == "✊ Держусь":
        await handle_hold(chat_id, context)
        return

    if text == "Тяжело":
        await send(context.bot, chat_id, "Держись, брат. Что нужно?", get_heavy_keyboard(), False)
        return

    if text == "Дни":
        days = get_days(chat_id)
        best = user.get("best_streak", 0)
        msg = f"Ты держишься {days} дней."
        if best > days:
            msg += f"\n\nТвой лучший стрик: {best} дней."
        elif best > 0:
            msg += f"\nСейчас идёт твой лучший стрик — {days} дней."
        await send(context.bot, chat_id, msg, get_main_keyboard(), False)
        if days in MILESTONES:
            await send(context.bot, chat_id, MILESTONES[days], get_main_keyboard(), False)
        return

    if text == "Ты тут?":
        await asyncio.sleep(random.randint(2,6))
        await send(context.bot, chat_id, random.choice(TU_TUT_FIRST), get_main_keyboard(), False)
        await asyncio.sleep(random.randint(2,5))
        await send(context.bot, chat_id, random.choice(TU_TUT_SECOND), get_main_keyboard(), False)
        return

    if text == "Спасибо":
        await send(context.bot, chat_id,
            "Спасибо, брат, что ты есть. ❤️\n\n"
            "Если хочешь поддержать того, кто это всё написал:\n"
            "Сбер 2202 2084 3481 5313\n\n"
            "Любая сумма — это ещё один человек, которому мы сможем помочь.\n\n"
            "Главное — держись.", get_main_keyboard(), False)
        return

    if text == "Пауза":
        await stop(update, context)
        return

    if text == "Упражнения":
        await send(context.bot, chat_id, get_next_tip(user), get_help_keyboard(), False)
        return

    if text == "Советы":
        await send(context.bot, chat_id, get_next_advice(user), get_help_keyboard(), False)
        return

    if text == "Срыв":
        reset_streak(chat_id)
        await send(context.bot, chat_id,
            "Ничего страшного, брат.\n"
            "Главное — ты сказал честно. Это уже победа.\n"
            "Начинаем с чистого листа. Я с тобой.", get_main_keyboard(), False)
        return

    if text in ["Назад", "Назад в меню"]:
        await send(context.bot, chat_id, "Возвращаемся в меню.", get_main_keyboard(), False)
        return

    if text == "Ещё способ":
        # определяем по последнему сообщению бота, что показывали
        last_text = update.message.reply_to_message.text if update.message.reply_to_message else ""
        if any(word in last_text for word in ["отжиманий", "вдох", "ледяная", "улицу", "воды", "благодарен", "кислое", "пройдись", "спину"]):
            await send(context.bot, chat_id, get_next_tip(user), get_help_keyboard(), False)
        else:
            await send(context.bot, chat_id, get_next_advice(user), get_help_keyboard(), False)
        return

    # Если человек просто написал текст — поддержим
    if len(text) > 8:
        await send(context.bot, chat_id,
            "Понимаю, брат. Тяжко.\n"
            "Жми «✊ Держусь» — всем разошлю, что ты ещё тут.\n"
            "Или «Тяжело» — подберём способ прямо сейчас.",
            get_main_keyboard(), False)

# ======================= Main =========================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
