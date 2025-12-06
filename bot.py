import logging
import os
import json
import asyncio
import random
from datetime import datetime, date, timedelta
from filelock import FileLock
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
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

# -----------------------------------------
# Данные
# -----------------------------------------
MORNING_MESSAGES = [
    "Привет. Давай сегодня не будем, хорошо?",
    "Доброе утро. Не сегодня.",
    "Привет. Держимся сегодня?",
    "Доброе утро. Сегодня много дел, наверное нет.",
    "Привет. Сегодня обойдёмся без этого."
]

EVENING_MESSAGES = [
    "Не сегодня. Держись.",
    "Я тут. Давай не сегодня.",
    "Привет. Сегодня держимся, помнишь?",
    "Держись. Сегодня нет."
]

NIGHT_MESSAGES = [
    "Ты молодец. До завтра.",
    "Красавчик. Спокойной.",
    "Держался сегодня. Уважаю.",
    "Сегодня справились. До завтра."
]

HOLD_RESPONSES = ["Отправлено. ✊", "Молодец. ✊", "Понял. ✊", "Так держать. ✊"]

HELP_TECHNIQUES = [
    "🧊 Лёд на запястья 30-60 сек. Холод активирует блуждающий нерв — тяга падает за минуту.",
    "🫁 Дыхание 4-7-8: вдох на 4 → задержка на 7 → выдох на 8. 4 раза. Снижает кортизол.",
    "⏱ Таймер на 5 минут: «Просто подожди». Тяга как волна — пройдёт сама за 3-7 минут.",
    "🚪 Встань и выйди в другую комнату. Смена контекста разрывает нейронную связь."
]

RECOVERY_STAGES = [
    "📅 ДНИ 1-3: ОСТРАЯ ФАЗА\n\nПик физических симптомов. Рецепторы требуют привычный дофамин.\n• Тревога 8-10/10\n• Раздражительность\n• Бессонница\n• Сильная тяга каждые 1-2 часа",
    "📅 ДНИ 4-7: ПОДОСТРАЯ ФАЗА\n\nСимптомы снижаются на 40%. Настроение скачет — это нормально.\n• Физические симптомы слабеют\n• Появляются окна ясности\n• Энергия всё ещё низкая\n• Тяга приходит реже",
    "📅 ДНИ 8-14: АДАПТАЦИЯ\n\nРецепторы оживают. Сон налаживается, тяга слабеет, голова яснее.",
    "📅 ДНИ 15-28: ВОССТАНОВЛЕНИЕ\n\nМозг работает чище. Энергия стабильная, эмоции под контролем, радость от простых вещей.",
    "📅 ДНИ 29-90: СТАБИЛИЗАЦИЯ\n\nПолная перезагрузка нейронных связей. Новая норма жизни. Ты свободен."
]

TRIGGERS_INFO = [
    "⚠️ СИЛЬНАЯ ЭМОЦИЯ: злость, тревога — маскируются под желание. Дыши, назови эмоцию вслух.",
    "⚠️ СКУКА: мозг путает скуку с желанием. Займись активностью 10 минут.",
    "⚠️ КОМПАНИЯ: социальное давление. Избегай первые 30 дней, репетируй отказ."
]

COGNITIVE_DISTORTIONS = [
    "🤯 Я ВСЁ ИСПОРТИЛ: ошибка — катастрофизация. Один срыв ≠ конец пути.",
    "🤯 НИЧЕГО НЕ РАБОТАЕТ: ошибка — чёрно-белое мышление. Медленно, но работает.",
    "🤯 Я СЛАБЫЙ: ошибка — персонализация. Это химия мозга, не слабость."
]

SCIENCE_FACTS = [
    "🔬 CB1-РЕЦЕПТОРЫ: ТГК блокирует. Восстановление: неделя +28%, 2 недели +50%, месяц почти полное.",
    "🔬 ДОФАМИНОВАЯ СИСТЕМА: ТГК повышает дофамин. Без вещества мозг вырабатывает естественный.",
    "🔬 СОН: REM нарушен. Через месяц сон качественный."
]

# -----------------------------------------
# Хранилище пользователей
# -----------------------------------------
_user_data_cache = None
_data_lock = asyncio.Lock()

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
                _user_data_cache = json.load(f)
                return _user_data_cache
        except:
            _user_data_cache = {}
            return _user_data_cache

async def save_data():
    global _user_data_cache
    async with _data_lock:
        with FileLock(LOCK_FILE):
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(_user_data_cache, f, ensure_ascii=False, indent=2)

def get_user(user_id):
    data = load_data()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "active": False,
            "start_date": None,
            "hold_count_today": 0,
            "last_hold_time": None,
            "last_stage_index": 0,
            "used_tips": [], "used_triggers": [], "used_distortions": [], "used_facts": [],
            "best_streak": 0
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

# -----------------------------------------
# Кнопки
# -----------------------------------------
def get_main_keyboard():
    buttons = [
        [InlineKeyboardButton("✊ Держусь", callback_data="hold"),
         InlineKeyboardButton("😔 Тяжело", callback_data="heavy")],
        [InlineKeyboardButton("👋 Ты тут?", callback_data="are_you_here"),
         InlineKeyboardButton("📊 Дни", callback_data="days")],
        [InlineKeyboardButton("❤️ Спасибо", callback_data="thank_you"),
         InlineKeyboardButton("⏸ Помолчи", callback_data="stop")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_info_keyboard():
    buttons = [
        [InlineKeyboardButton("📅 Стадии", callback_data="stages"),
         InlineKeyboardButton("⚠️ Триггеры", callback_data="triggers")],
        [InlineKeyboardButton("🤯 Искажения", callback_data="distortions"),
         InlineKeyboardButton("🔬 Факты", callback_data="facts")],
        [InlineKeyboardButton("↩ Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(buttons)

# -----------------------------------------
# Хэндлеры
# -----------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    await save_user(chat_id, {"active": True, "start_date": str(date.today())})
    await update.message.reply_text(
        "Привет! Я буду писать три раза в день — просто напомнить: сегодня не стоит.\nНажимай кнопки ниже.",
        reply_markup=get_main_keyboard()
    )

async def handle_hold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user = get_user(chat_id)
    if user.get("hold_count_today",0)>=5:
        await query.edit_message_text("Сегодня уже 5 раз. Завтра снова сможешь.", reply_markup=get_main_keyboard())
        return
    user["hold_count_today"] = user.get("hold_count_today",0)+1
    user["last_hold_time"] = datetime.now(MOSCOW_TZ).isoformat()
    await save_user(chat_id, user)
    await query.edit_message_text(random.choice(HOLD_RESPONSES), reply_markup=get_main_keyboard())

async def handle_are_you_here(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    msg = await query.edit_message_text("...", reply_markup=get_main_keyboard())
    await asyncio.sleep(random.uniform(1.5,3.5))
    first = random.choice(["Тут.","Привет.","А куда я денусь?","Здесь.","Тут, как всегда."])
    second = random.choice(["Держимся.","Я с тобой.","Всё по плану.","Не хочу сегодня.","Сегодня не буду."])
    await msg.edit_text(f"{first}\n{second}", reply_markup=get_main_keyboard())

async def handle_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    days = (date.today() - date.fromisoformat(get_user(chat_id)["start_date"])).days
    await query.edit_message_text(f"Ты держишься {days} дней.", reply_markup=get_main_keyboard())

async def handle_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cb = query.data
    chat_id = query.message.chat_id
    if cb=="stages":
        text = random.choice(RECOVERY_STAGES)
    elif cb=="triggers":
        text = random.choice(TRIGGERS_INFO)
    elif cb=="distortions":
        text = random.choice(COGNITIVE_DISTORTIONS)
    elif cb=="facts":
        text = random.choice(SCIENCE_FACTS)
    elif cb=="back":
        text="Возвращаемся в главное меню"
        await query.edit_message_text(text, reply_markup=get_main_keyboard())
        return
    await query.edit_message_text(text, reply_markup=get_info_keyboard())

# -----------------------------------------
# Основная функция
# -----------------------------------------
def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(handle_hold, pattern="^hold$"))
    application.add_handler(CallbackQueryHandler(handle_are_you_here, pattern="^are_you_here$"))
    application.add_handler(CallbackQueryHandler(handle_days, pattern="^days$"))
    application.add_handler(CallbackQueryHandler(handle_info, pattern="^(stages|triggers|distortions|facts|back)$"))
    application.run_polling()

if __name__=="__main__":
    main()
