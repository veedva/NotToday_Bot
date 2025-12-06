import logging
import random
import json
import os
import asyncio
from datetime import datetime, time, date, timedelta
from filelock import FileLock
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import pytz

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен!")

DATA_FILE = "user_data.json"
LOCK_FILE = DATA_FILE + ".lock"
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# --- Сообщения ---
MORNING_MESSAGES = [
    "Привет. Давай сегодня не будем, хорошо?", "Доброе утро. Не сегодня.",
    "Привет. Держимся сегодня?", "Доброе утро. Сегодня много дел, наверное нет.",
    "Привет. Сегодня обойдёмся без этого.", "Утро. Давай сегодня пропустим.",
    "Привет. Сегодня пожалуй что не стоит.", "Доброе утро. Напишу ещё сегодня.",
    "Привет. Сегодня точно не надо.", "Доброе! Давай сегодня без этого."
]

EVENING_MESSAGES = [
    "Не сегодня. Держись.", "Я тут. Давай не сегодня.", "Привет. Сегодня держимся, помнишь?",
    "Держись. Сегодня нет.", "Ещё чуть-чуть. Не сегодня.", "Я с тобой. Сегодня точно нет.",
    "Привет. Давай обойдёмся.", "Мы же решили — не сегодня.", "Держись там. Сегодня мимо.",
    "Привет. Сегодня пропустим."
]

NIGHT_MESSAGES = [
    "Ты молодец. До завтра.", "Красавчик. Спокойной.", "Держался сегодня. Уважаю.",
    "Сегодня справились. До завтра.", "Молодец, держишься.", "Ещё один день позади.",
    "Ты сильный. До завтра.", "Сегодня получилось. Отдыхай.", "Справился. Уважение.",
    "Держался весь день. Красава."
]

TU_TUT_FIRST = ["Тут.", "Привет.", "А куда я денусь?", "Здесь.", "Тут, как всегда.",
                "Да, да.", "Как дела?", "Ага.", "Здравствуй.", "Тут, не переживай."]
TU_TUT_SECOND = ["Держимся.", "Я с тобой.", "Всё по плану.", "Не хочу сегодня.", "Сегодня не буду.",
                 "Я рядом.", "Держись.", "Всё будет нормально.", "Я в деле.", "Под контролем."]

HOLD_RESPONSES = ["Отправлено. ✊", "Молодец. ✊", "Понял. ✊", "Так держать. ✊"]

MILESTONES = {
    3: "✨ Три дня уже. Самое тяжёлое позади.",
    7: "✨ Неделя. Рецепторы начинают восстанавливаться.",
    14: "✨ Две недели! Сон налаживается, голова яснее.",
    21: "✨ Три недели. Ты уже почти не думаешь об этом.",
    30: "✨ Месяц без этого. Мозг работает по-новому.",
    60: "✨ Два месяца — ты другой человек.",
    90: "✨ Три месяца. Полное восстановление. Ты молодец.",
    180: "✨ Полгода. Легенда.",
    365: "✨ ГОД ЧИСТЫМ. Ты сделал это ❤️"
}

HELP_TECHNIQUES = [
    "🧊 Лёд на запястья 30-60 сек...", "🫁 Дыхание 4-7-8...", "⏱ Таймер на 5 минут...",
    "🚪 Встань и выйди в другую комнату...", "🍋 Кусок лимона или имбиря...", "✊ Сожми кулаки 10 сек → отпусти...",
    "💧 Умой лицо ледяной водой 30 сек...", "📝 Напиши 3 причины, почему сейчас не надо...",
    "🫁 10 медленных глубоких вдохов...", "💪 Планка 45-60 секунд...", "🚶 Быстрая прогулка 7-10 минут...",
    "👀 5-4-3-2-1...", "🚿 Контрастный душ...", "🥜 Съешь горсть орехов или сыра...", "🎾 Сожми теннисный мячик до боли...",
    "💪 Поза силы 2 минуты...", "🤔 HALT...", "🌊 Urge Surfing...", "💬 Напиши любому: «Тяжко, брат»...", "💪 20 отжиманий до отказа..."
]

RECOVERY_STAGES = [
    "📅 ДНИ 1-3: ОСТРАЯ ФАЗА\n\nПик физических симптомов...",
    "📅 ДНИ 4-7: ПОДОСТРАЯ ФАЗА\n\nСимптомы снижаются...",
    "📅 ДНИ 8-14: АДАПТАЦИЯ\n\nРецепторы оживают...",
    "📅 ДНИ 15-28: ВОССТАНОВЛЕНИЕ\n\nМозг работает чище...",
    "📅 ДНИ 29-90: СТАБИЛИЗАЦИЯ\n\nПолная перезагрузка нейронных связей..."
]

COGNITIVE_DISTORTIONS = [
    "🤯 «Я ВСЁ ИСПОРТИЛ»...", "🤯 «НИЧЕГО НЕ РАБОТАЕТ»...", "🤯 «Я СЛАБЫЙ»...",
    "🤯 «ВСЁ БЕССМЫСЛЕННО»...", "🤯 «У ДРУГИХ ПОЛУЧАЕТСЯ»...", "🤯 «ОДИН РАЗ НЕ СЧИТАЕТСЯ»..."
]

TRIGGERS_INFO = [
    "⚠️ МЫСЛЬ «ХОЧУ»...", "⚠️ СИЛЬНАЯ ЭМОЦИЯ...", "⚠️ СКУКА / БЕЗДЕЛЬЕ...",
    "⚠️ СТРЕСС / ТРЕВОГА...", "⚠️ КОМПАНИЯ / ОКРУЖЕНИЕ..."
]

SCIENCE_FACTS = [
    "🔬 CB1-РЕЦЕПТОРЫ...", "🔬 ДОФАМИНОВАЯ СИСТЕМА...", "🔬 СОН И МЕЛАТОНИН...",
    "🔬 ПАМЯТЬ И ГИППОКАМП...", "🔬 СТАТИСТИКА СРЫВОВ...", "🔬 ПРЕФРОНТАЛЬНАЯ КОРА...",
    "🔬 BDNF (Brain-Derived Neurotrophic Factor)...", "🔬 СЕРДЕЧНО-СОСУДИСТАЯ СИСТЕМА...",
    "🔬 МОТИВАЦИЯ И АНГЕДОНИЯ...", "🔬 НЕЙРОПЛАСТИЧНОСТЬ...", "🔬 ГОРМОНАЛЬНЫЙ БАЛАНС...",
    "🔬 КОГНИТИВНЫЕ ФУНКЦИИ...", "🔬 СОЦИАЛЬНОЕ ВОССТАНОВЛЕНИЕ...", "🔬 ФИЗИЧЕСКОЕ ВОССТАНОВЛЕНИЕ...",
    "🔬 ЭКОНОМИКА ЗАВИСИМОСТИ..."
]

_user_data_cache = None
_data_lock = asyncio.Lock()

# --- Кнопки инлайн ---
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✊ Держусь", callback_data="hold"),
         InlineKeyboardButton("😔 Тяжело", callback_data="heavy")],
        [InlineKeyboardButton("👋 Ты тут?", callback_data="tutut"),
         InlineKeyboardButton("📊 Дни", callback_data="days")],
        [InlineKeyboardButton("❤️ Спасибо", callback_data="thank"),
         InlineKeyboardButton("⏸ Помолчи", callback_data="stop")]
    ])

def start_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶ Начать", callback_data="start")]
    ])

def heavy_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Сделать упражнение", callback_data="exercise"),
         InlineKeyboardButton("🧠 Информация", callback_data="info")],
        [InlineKeyboardButton("💔 Срыв", callback_data="breakdown"),
         InlineKeyboardButton("↩ Назад", callback_data="back")]
    ])

def info_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Стадии", callback_data="stages"),
         InlineKeyboardButton("⚠️ Триггеры", callback_data="triggers")],
        [InlineKeyboardButton("🤯 Искажения", callback_data="distortions"),
         InlineKeyboardButton("🔬 Факты", callback_data="facts")],
        [InlineKeyboardButton("↩ Назад", callback_data="back")]
    ])

# --- Загрузка/сохранение данных ---
def load_data():
    global _user_data_cache
    if _user_data_cache is not None:
        return _user_data_cache
    with FileLock(LOCK_FILE):
        if not os.path.exists(DATA_FILE):
            _user_data_cache = {}
            return _user_data_cache
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                _user_data_cache = data
                return data
        except Exception:
            _user_data_cache = {}
            return {}

async def save_data():
    global _user_data_cache
    if _user_data_cache is None:
        return
    async with _data_lock:
        with FileLock(LOCK_FILE):
            try:
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(_user_data_cache, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Ошибка сохранения данных: {e}")

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
            "last_stage_index": 0,
            "used_tips": [],
            "used_triggers": [],
            "used_distortions": [],
            "used_facts": []
        }
        asyncio.create_task(save_data())
    return data[uid]

async def save_user(user_id, updates=None):
    data = load_data()
    uid = str(user_id)
    if updates:
        if uid not in data:
            data[uid] = {}
        data[uid].update(updates)
    await save_data()

def get_active_users():
    data = load_data()
    return [int(uid) for uid, user in data.items() if user.get("active", False)]

def get_current_time():
    return datetime.now(MOSCOW_TZ)

def get_current_date():
    return get_current_time().date()

def get_days_since_start(user_id):
    user = get_user(user_id)
    if not user["start_date"]:
        return 0
    try:
        start = date.fromisoformat(user["start_date"])
        current = get_current_date()
        days = (current - start).days
        return max(days, 0)
    except:
        return 0

def format_days(days):
    if 11 <= days % 100 <= 19:
        return f"{days} дней"
    if days % 10 == 1:
        return f"{days} день"
    if days % 10 in [2, 3, 4]:
        return f"{days} дня"
    return f"{days} дней"

# --- Логика выбора следующего элемента ---
def get_next_item(user_id, items_list, used_key):
    user = get_user(user_id)
    used = user.get(used_key, [])
    if len(used) >= len(items_list):
        used = []
    available = [i for i in range(len(items_list)) if i not in used]
    if not available:
        available = list(range(len(items_list)))
        used = []
    choice = random.choice(available)
    used.append(choice)
    asyncio.create_task(save_user(user_id, {used_key: used}))
    return items_list[choice]

def get_next_exercise(user_id):
    return get_next_item(user_id, HELP_TECHNIQUES, "used_tips")

def get_next_stage(user_id):
    user = get_user(user_id)
    idx = user.get("last_stage_index", 0)
    text = RECOVERY_STAGES[idx]
    next_idx = (idx + 1) % len(RECOVERY_STAGES)
    if next_idx == 0:
        text += "\n\n✨ Это была последняя стадия. Нажми ещё раз, чтобы начать сначала."
    else:
        stage_num = next_idx + 1
        text += f"\n\n📌 Стадия {stage_num}/{len(RECOVERY_STAGES)}. Нажми ещё раз для следующей."
    asyncio.create_task(save_user(user_id, {"last_stage_index": next_idx}))
    return text

async def reset_streak(user_id):
    current = get_days_since_start(user_id)
    user = get_user(user_id)
    if current > user.get("best_streak", 0):
        await save_user(user_id, {"best_streak": current})
    await save_user(user_id, {
        "start_date": get_current_date().isoformat(),
        "last_stage_index": 0,
        "hold_count_today": 0,
        "last_hold_date": None,
        "last_hold_time": None,
        "used_tips": [],
        "used_triggers": [],
        "used_distortions": [],
        "used_facts": []
    })
    return current

# --- Джобы пушей ---
def remove_user_jobs(chat_id, job_queue):
    removed = 0
    for name in [f"morning_{chat_id}", f"evening_{chat_id}", f"night_{chat_id}"]:
        jobs = job_queue.get_jobs_by_name(name)
        for job in jobs:
            job.schedule_removal()
            removed += 1
    return removed

def schedule_jobs(chat_id, job_queue):
    remove_user_jobs(chat_id, job_queue)
    job_queue.run_daily(send_morning, time(9,0, tzinfo=MOSCOW_TZ), data={'chat_id': chat_id}, name=f"morning_{chat_id}")
    job_queue.run_daily(send_evening, time(18,0, tzinfo=MOSCOW_TZ), data={'chat_id': chat_id}, name=f"evening_{chat_id}")
    job_queue.run_daily(send_night, time(23,0, tzinfo=MOSCOW_TZ), data={'chat_id': chat_id}, name=f"night_{chat_id}")

async def send_morning(context):
    chat_id = context.job.data['chat_id']
    user = get_user(chat_id)
    if not user.get("active"):
        return
    days = get_days_since_start(chat_id)
    msg = random.choice(MORNING_MESSAGES)
    if days in MILESTONES:
        msg += f"\n\n{MILESTONES[days]}"
    await context.bot.send_message(chat_id, msg, reply_markup=main_menu())

async def send_evening(context):
    chat_id = context.job.data['chat_id']
    user = get_user(chat_id)
    if not user.get("active"):
        return
    await context.bot.send_message(chat_id, random.choice(EVENING_MESSAGES), reply_markup=main_menu())

async def send_night(context):
    chat_id = context.job.data['chat_id']
    user = get_user(chat_id)
    if not user.get("active"):
        return
    await context.bot.send_message(chat_id, random.choice(NIGHT_MESSAGES), reply_markup=main_menu())

# --- Обработчики кнопок ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "start":
        user = get_user(user_id)
        was_active = user.get("active", False)
        await save_user(user_id, {"active": True, "start_date": get_current_date().isoformat()})
        if not was_active:
            schedule_jobs(user_id, context.application.job_queue)
        days = get_days_since_start(user_id)
        msg = f"Привет! Ты держишься {format_days(days)}. Я рядом." if days > 0 else "Привет, брат! 👋 Держимся сегодня!"
        await query.message.edit_text(msg, reply_markup=main_menu())

    elif data == "stop":
        await save_user(user_id, {"active": False})
        remove_user_jobs(user_id, context.application.job_queue)
        await query.message.edit_text("Уведомления остановлены.\nКогда будешь готов — жми ▶ Начать", reply_markup=start_menu())

    elif data == "hold":
        user = get_user(user_id)
        if not user.get("active"):
            await query.message.edit_text("Сначала нажми ▶ Начать", reply_markup=start_menu())
            return
        today_str = get_current_date().isoformat()
        if user.get("last_hold_date") != today_str:
            await save_user(user_id, {"hold_count_today":0, "last_hold_date":today_str})
        if user.get("hold_count_today",0)>=5:
            await query.message.edit_text("Сегодня уже 5 раз.\nЗавтра снова сможешь.", reply_markup=main_menu())
            return
        await save_user(user_id, {
            "hold_count_today": user.get("hold_count_today",0)+1,
            "last_hold_date": today_str,
            "last_hold_time": get_current_time().isoformat()
        })
        await query.message.edit_text(random.choice(HOLD_RESPONSES), reply_markup=main_menu())

    elif data == "heavy":
        await query.message.edit_text("Тяжело? Выбирай:", reply_markup=heavy_menu())

    elif data == "exercise":
        ex = get_next_exercise(user_id)
        await query.message.edit_text(f"💡 Техника:\n\n{ex}", reply_markup=heavy_menu())

    elif data == "info":
        await query.message.edit_text("Выбирай категорию информации:", reply_markup=info_menu())

    elif data == "stages":
        stage = get_next_stage(user_id)
        await query.message.edit_text(stage, reply_markup=info_menu())

    elif data == "distortions":
        d = get_next_item(user_id, COGNITIVE_DISTORTIONS, "used_distortions")
        await query.message.edit_text(d, reply_markup=info_menu())

    elif data == "triggers":
        t = get_next_item(user_id, TRIGGERS_INFO, "used_triggers")
        await query.message.edit_text(t, reply_markup=info_menu())

    elif data == "facts":
        f = get_next_item(user_id, SCIENCE_FACTS, "used_facts")
        await query.message.edit_text(f, reply_markup=info_menu())

    elif data == "back":
        await query.message.edit_text("Главное меню:", reply_markup=main_menu())

    elif data == "breakdown":
        await reset_streak(user_id)
        await query.message.edit_text("Срыв зафиксирован. Счётчик сброшен. Держись!", reply_markup=start_menu())

    elif data == "tutut":
        msg = random.choice(TU_TUT_FIRST) + " " + random.choice(TU_TUT_SECOND)
        await query.message.edit_text(msg, reply_markup=main_menu())

    elif data == "days":
        days = get_days_since_start(user_id)
        msg = f"Ты держишься {format_days(days)}."
        milestone = MILESTONES.get(days)
        if milestone:
            msg += f"\n\n{milestone}"
        await query.message.edit_text(msg, reply_markup=main_menu())

    elif data == "thank":
        await query.message.edit_text("❤️ Я рад, что могу помогать!", reply_markup=main_menu())

# --- Старт ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Держимся?", reply_markup=start_menu())

# --- Основное ---
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("Бот запущен")
    application.run_polling()

if __name__ == "__main__":
    main()
