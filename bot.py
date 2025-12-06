import logging
import random
import json
import os
import asyncio
from datetime import datetime, time, date
from functools import partial
from filelock import FileLock
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import pytz

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен!")

DATA_FILE = "user_data.json"
LOCK_FILE = DATA_FILE + ".lock"
MOSCOW_TZ = pytz.timezone('Europe/Moscow')
REFLECTION, BREAKDOWN_STATE = range(2)

MORNING_MESSAGES = [
    "Привет. Давай сегодня не будем, хорошо?", "Доброе утро, брат. Не сегодня.", "Привет. Держимся сегодня, да?",
    "Доброе. Сегодня дел много, нет наверное.", "Привет. Сегодня обойдёмся и так.", "Утро. Давай только не сегодня.",
    "Привет, брат. Сегодня пожалуй что ну его нахуй.", "Доброе утро. Я напишу ещё сегодня.", "Привет. Сегодня точно не надо.",
    "Доброе! Давай сегодня без этого вот.", "Привет лох. Денег жалко, да и ну его.", "Привет. Сегодня всё будет нормально.",
    "Братан, доброе. Сегодня точно нет.", "Эй. Сегодня не в тему.", "Доброе утро. Не сегодня.", "Привет. Может завтра, но сегодня нет.",
    "Утро. Сегодня спокойно обходимся.", "Чё как? Сегодня не стоит пожалуй."
]

EVENING_MESSAGES = [
    "Брат, не сегодня. Держись.", "Эй, я тут. Давай не сегодня.", "Привет. Сегодня держимся, помнишь?",
    "Брат, держись. Сегодня нет.", "Эй. Ещё чуть-чуть. Не сегодня.", "Я с тобой. Сегодня точно нет.",
    "Привет. Давай обойдёмся.", "Брат, мы же решили — не сегодня.", "Держись там. Сегодня мимо.",
    "Привет. Сегодня пропустим.", "Эй. Сегодня точно можно без этого.", "Братан, сегодня не надо.",
    "Привет. Может завтра, сегодня мимо.", "Как дела? Сегодня обойдёмся.", "Эй, брат. Сегодня не будем.",
    "Привет. Сегодня точно ни к чему.", "Братан, ну может завтра, а сегодня нет?"
]

NIGHT_MESSAGES = [
    "Ты молодец. До завтра.", "Красавчик. Спокойной.", "Держался сегодня. Уважаю.",
    "Сегодня справились. До завтра.", "Молодец, держишься.", "Ещё один день позади.",
    "Ты сильный. До завтра.", "Сегодня получилось. Отдыхай.", "Справился. Уважение.",
    "Держался весь день. Красава.", "Нормально прошёл день.", "Сегодня справились. Отдыхай.",
    "Ещё один день прошёл. До завтра.", "Держались сегодня. Молодцы.", "День зачётный. Спокойной.",
    "Справился. До завтра.", "Сегодня получилось. Отдыхай."
]

MILESTONES = {
    3: "✨ Три дня уже. Самое тяжёлое позади, брат.",
    7: "✨ Неделя. Рецепторы начинают восстанавливаться.",
    14: "✨ Две недели! Сон налаживается, голова яснее.",
    21: "✨ Три недели. Ты уже почти не думаешь об этом.",
    30: "✨ Месяц без этой хуйни. Мозг работает по-новому.",
    60: "✨ Два месяца — ты другой человек.",
    90: "✨ Три месяца. Полное восстановление. Ты машина.",
    180: "✨ Полгода. Легенда.",
    365: "✨ ГОД ЧИСТЫМ. Ты сделал это, брат ❤️"
}

TU_TUT_FIRST = ["Тут.", "Привет.", "А куда я денусь?", "Здесь.", "Тут, как всегда.", "Да, да.", "Чё как?", "Ага.", "Здравствуй.", "Тут, не переживай."]
TU_TUT_SECOND = ["Держимся.", "Я с тобой.", "Всё по плану.", "Не хочу сегодня.", "Сегодня не буду.", "Я рядом.", "Держись.", "Всё будет нормально.", "Я в деле.", "Под контролем."]
HOLD_RESPONSES = ["Отправлено. ✊", "Молодец. ✊", "Понял. ✊", "Так держать. ✊"]

HELP_TECHNIQUES = [
    "Лёд на запястья на 30–60 секунд. Холод активирует блуждающий нерв — тяга падает за минуту.",
    "Дыхание 4-7-8: вдох на 4 → задержка на 7 → выдох на 8. Повтори 4 раза. Снижает кортизол мгновенно.",
    "Таймер на 5 минут: скажи себе «Просто подожду». Тяга как волна — она пройдёт сама за 3-7 минут.",
    "Встань и выйди в другую комнату. Смена контекста разрывает нейронную связь с триггером.",
    "Кусок лимона или имбиря в рот. Резкий вкус перебивает дофаминовый сигнал в мозге.",
    "Сожми кулаки на 10 секунд → резко отпусти. Повтори 5 раз. Физическое напряжение уходит.",
    "Умой лицо ледяной водой 20–30 секунд. Активирует рефлекс погружения — мгновенное успокоение.",
    "Напиши на бумаге 3 причины, почему сейчас НЕ НАДО. Помоги мозгу вспомнить логику.",
    "10 медленных глубоких вдохов. Кислород снижает адреналин и возвращает контроль.",
    "Планка 45–60 секунд. Пока мышцы горят — голова не думает о тяге.",
    "Быстрая прогулка 7–10 минут. Движение вырабатывает BDNF — природный антидепрессант.",
    "Заземление 5-4-3-2-1: назови 5 вещей (вижу), 4 (трогаю), 3 (слышу), 2 (запах), 1 (вкус). Возвращает в реальность.",
    "Контрастный душ: 30 сек холодной → 1 мин тёплой. Повтори 2 раза. Перезагрузка нервной системы.",
    "Съешь горсть орехов или кусок сыра. Белок и жиры стабилизируют сахар в крови.",
    "Сожми теннисный мячик до боли. 10 раз. Физический выброс адреналина через руки.",
    "Поза силы 2 минуты: ноги широко, руки в боки, грудь вперёд. Меняет гормональный фон реально.",
    "HALT-проверка: голоден? (Hungry) злой? (Angry) одинок? (Lonely) устал? (Tired). Исправь хоть одно.",
    "Urge Surfing: представь тягу как волну. Не борись — наблюдай со стороны. Через 3-7 минут она спадёт сама.",
    "Напиши любому человеку: «Тяжко, брат». Стыдно? Именно поэтому это работает.",
    "20 отжиманий до отказа. Пока тело в шоке — мозг забывает про дофаминовый голод.",
    "Лёд в рот на 30 секунд. Максимальная физиологическая перезагрузка за минимальное время.",
    "Скажи вслух 3 раза: «Это пройдёт. Я сильнее». Голос закрепляет мысль в реальности.",
    "Медленно выпей большой стакан воды. Объём в желудке даёт телу сигнал безопасности.",
    "10 бёрпи прямо сейчас. Самый быстрый способ сжечь адреналин и кортизол.",
    "Включи любимый трек и подвигайся 3 минуты. Новый дофамин без вещества.",
    "Позвони другу или родителям. Социальная связь повышает окситоцин — гормон спокойствия.",
    "Напиши список из 5 вещей, за которые благодарен сегодня. Переключает мозг на позитив.",
    "Съешь что-то сладкое + выпей воды. Быстрый сахар стабилизирует настроение на 15-20 минут.",
    "Ляг на пол и расслабь все мышцы на 2 минуты. Полная релаксация снижает кортизол.",
    "Включи смешное видео или мемы на 5 минут. Смех — природный антидепрессант."
]

HELP_ADVICE_BY_DAY = [
    "Дни 1–3: острая нехватка дофамина. Мозг паникует и требует вернуть привычку. Это ломка — она пройдёт через 72 часа. Пик на 3-й день.",
    "Дни 4–7: симптомы идут на спад. Настроение скачет, но уже появляются окна ясности. Сон всё ещё хреновый — это нормально.",
    "Дни 8–14: рецепторы оживают. Простые вещи начинают приносить радость. Сон налаживается. Ты на половине пути.",
    "Дни 15–28: CB1 и дофаминовые рецепторы активно восстанавливаются. Энергия возвращается. Голова работает быстрее.",
    "Дни 29–42: полное восстановление рецепторов. Ты почти не вспоминаешь о тяге. Новая жизнь начинается здесь.",
    "Дни 43–90: нейропластичность на пике. Мозг перестроился. Тяга приходит редко и слабо.",
    "90+ дней: точка невозврата пройдена. Мозг работает как новый. Теперь просто живи и береги себя."
]

def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("✊ Держусь"), KeyboardButton("😔 Тяжело")],
        [KeyboardButton("📊 Дни"), KeyboardButton("👋 Ты тут?")],
        [KeyboardButton("❤️ Спасибо"), KeyboardButton("⏸ Помолчи")]
    ], resize_keyboard=True)

def get_start_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("▶ Начать")]], resize_keyboard=True)

def get_heavy_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔥 Упражнение"), KeyboardButton("🧠 Что происходит с телом")],
        [KeyboardButton("💔 Срыв"), KeyboardButton("↩ Назад")]
    ], resize_keyboard=True)

def get_exercise_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔄 Другое упражнение")],
        [KeyboardButton("↩ Назад")]
    ], resize_keyboard=True)

def get_advice_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("↩ Назад")]], resize_keyboard=True)

def get_current_time():
    return datetime.now(MOSCOW_TZ).replace(microsecond=0)

def get_current_date():
    return get_current_time().date()

def format_days_text(days):
    if days % 10 == 1 and days != 11:
        return f"{days} день"
    elif days % 10 in [2, 3, 4] and days not in [12, 13, 14]:
        return f"{days} дня"
    return f"{days} дней"

def load_data():
    with FileLock(LOCK_FILE):
        if not os.path.exists(DATA_FILE):
            return {}
        
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for uid, user in data.items():
                    if "start_date" in user and user["start_date"]:
                        try:
                            date.fromisoformat(user["start_date"])
                        except (ValueError, TypeError):
                            user["start_date"] = None
                    if "last_hold_time" in user and user["last_hold_time"]:
                        try:
                            datetime.fromisoformat(user["last_hold_time"])
                        except (ValueError, TypeError):
                            user["last_hold_time"] = None
                    user.setdefault("active", False)
                    user.setdefault("best_streak", 0)
                    user.setdefault("hold_count_today", 0)
                    user.setdefault("last_hold_date", None)
                    user.setdefault("used_tips", [])
                    user.setdefault("message_ids", [])
                return data
        except (json.JSONDecodeError, ValueError):
            if os.path.exists(DATA_FILE):
                backup = f"{DATA_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(DATA_FILE, backup)
            return {}

def save_data(data):
    with FileLock(LOCK_FILE):
        temp = f"{DATA_FILE}.tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp, DATA_FILE)

def get_user_data(user_id):
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
            "message_ids": []
        }
        save_data(data)
    return data, data[uid]

def get_days_since_start(user_id):
    _, user = get_user_data(user_id)
    if not user["start_date"]:
        return 0
    try:
        start = date.fromisoformat(user["start_date"])
        return (get_current_date() - start).days
    except (ValueError, TypeError):
        return 0

def get_active_users():
    data = load_data()
    return [int(uid) for uid, user in data.items() if user.get("active", False)]

def get_next_exercise(user_id):
    data, user = get_user_data(user_id)
    used = user.get("used_tips", [])
    total = len(HELP_TECHNIQUES)
    
    if len(used) >= total:
        used = []
        user["used_tips"] = used
    
    available = [i for i in range(total) if i not in used]
    if not available:
        used = []
        available = list(range(total))
    
    choice = random.choice(available)
    used.append(choice)
    user["used_tips"] = used
    data[str(user_id)] = user
    save_data(data)
    return HELP_TECHNIQUES[choice]

def get_advice_for_day(days):
    if days < 1: return "Только начинаешь. Первые шаги самые важные."
    elif days <= 3: return HELP_ADVICE_BY_DAY[0]
    elif days <= 7: return HELP_ADVICE_BY_DAY[1]
    elif days <= 14: return HELP_ADVICE_BY_DAY[2]
    elif days <= 28: return HELP_ADVICE_BY_DAY[3]
    elif days <= 42: return HELP_ADVICE_BY_DAY[4]
    elif days <= 90: return HELP_ADVICE_BY_DAY[5]
    return HELP_ADVICE_BY_DAY[6]

def reset_streak(user_id):
    data, user = get_user_data(user_id)
    current = get_days_since_start(user_id)
    if current > user.get("best_streak", 0):
        user["best_streak"] = current
    user["start_date"] = get_current_date().isoformat()
    user["hold_count_today"] = 0
    user["last_hold_date"] = None
    user["last_hold_time"] = None
    user["used_tips"] = []
    data[str(user_id)] = user
    save_data(data)

async def send_message(bot, chat_id, text, keyboard=None, save=True):
    try:
        reply_markup = keyboard if keyboard else get_main_keyboard()
        msg = await bot.send_message(chat_id, text, reply_markup=reply_markup)
        if save:
            data, user = get_user_data(chat_id)
            user.setdefault("message_ids", [])
            user["message_ids"].append(msg.message_id)
            if len(user["message_ids"]) > 300:
                user["message_ids"] = user["message_ids"][-300:]
            data[str(chat_id)] = user
            save_data(data)
        return msg
    except Exception as e:
        logger.error(f"Ошибка отправки {chat_id}: {e}")
        return None

async def midnight_cleanup(context):
    chat_id = context.job.chat_id
    data, user = get_user_data(chat_id)
    msg_ids = user.get("message_ids", [])
    user["message_ids"] = []
    data[str(chat_id)] = user
    save_data(data)
    
    for msg_id in msg_ids[:50]:
        try:
            await context.bot.delete_message(chat_id, msg_id)
            await asyncio.sleep(0.3)
        except:
            pass

def schedule_user_jobs(chat_id, job_queue):
    for prefix in ["morning", "evening", "night", "cleanup"]:
        for job in job_queue.jobs():
            if job.name == f"{prefix}_{chat_id}":
                job.schedule_removal()
    
    job_queue.run_daily(morning_job, time(9, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"morning_{chat_id}")
    job_queue.run_daily(evening_job, time(18, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"evening_{chat_id}")
    job_queue.run_daily(night_job, time(23, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"night_{chat_id}")
    job_queue.run_daily(midnight_cleanup, time(0, 1, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"cleanup_{chat_id}")

async def morning_job(context):
    chat_id = context.job.chat_id
    _, user = get_user_data(chat_id)
    if not user.get("active", False):
        return
    days = get_days_since_start(chat_id)
    if days in MILESTONES:
        await send_message(context.bot, chat_id, MILESTONES[days])
    else:
        await send_message(context.bot, chat_id, random.choice(MORNING_MESSAGES))

async def evening_job(context):
    chat_id = context.job.chat_id
    _, user = get_user_data(chat_id)
    if not user.get("active", False):
        return
    await send_message(context.bot, chat_id, random.choice(EVENING_MESSAGES))

async def night_job(context):
    chat_id = context.job.chat_id
    _, user = get_user_data(chat_id)
    if not user.get("active", False):
        return
    await send_message(context.bot, chat_id, random.choice(NIGHT_MESSAGES))

async def start_command(update, context):
    chat_id = update.effective_chat.id
    data, user = get_user_data(chat_id)
    
    if user.get("start_date") and user.get("active"):
        await send_message(context.bot, chat_id, "Ты уже начал. Продолжай держаться.", save=False)
        return
    
    user["active"] = True
    user["start_date"] = get_current_date().isoformat()
    user["used_tips"] = []
    user["hold_count_today"] = 0
    user["last_hold_date"] = None
    user["last_hold_time"] = None
    data[str(chat_id)] = user
    save_data(data)
    
    schedule_user_jobs(chat_id, context.job_queue)
    
    welcome = (
        "Привет, брат.\n\n"
        "Я буду писать три раза в день — просто напомню: сегодня не надо.\n\n"
        "Когда тяжело — жми ✊ Держусь\n"
        "Все получат пуш и узнают, что ты ещё здесь.\n"
        "Можешь жать до 5 раз в сутки.\n\n"
        "Держись. Я рядом."
    )
    await send_message(context.bot, chat_id, welcome, save=False)

async def stop_command(update, context):
    chat_id = update.effective_chat.id
    data, user = get_user_data(chat_id)
    user["active"] = False
    data[str(chat_id)] = user
    save_data(data)
    
    for prefix in ["morning", "evening", "night", "cleanup"]:
        for job in context.job_queue.jobs():
            if job.name == f"{prefix}_{chat_id}":
                job.schedule_removal()
    
    await send_message(context.bot, chat_id, "Уведомления остановлены.\nКогда будешь готов — жми ▶ Начать", get_start_keyboard(), False)

async def handle_hold(update, context):
    chat_id = update.effective_chat.id
    _, user = get_user_data(chat_id)
    if not user.get("active", False):
        await update.message.reply_text("Сначала нажми ▶ Начать", reply_markup=get_start_keyboard())
        return ConversationHandler.END
    
    data, user = get_user_data(chat_id)
    current = get_current_time()
    today = get_current_date()
    
    if user.get("last_hold_date") != today.isoformat():
        user["hold_count_today"] = 0
        user["last_hold_date"] = today.isoformat()
    
    if user.get("last_hold_time"):
        try:
            last = datetime.fromisoformat(user["last_hold_time"])
            diff = (current - last).total_seconds()
            if diff < 1800:
                mins = int((1800 - diff) / 60) + 1
                if mins == 1:
                    await update.message.reply_text("Погоди ещё 1 минуту, брат.", reply_markup=get_main_keyboard())
                elif mins in [2, 3, 4]:
                    await update.message.reply_text(f"Погоди ещё {mins} минуты, брат.", reply_markup=get_main_keyboard())
                else:
                    await update.message.reply_text(f"Погоди ещё {mins} минут, брат.", reply_markup=get_main_keyboard())
                return ConversationHandler.END
        except:
            pass
    
    if user.get("hold_count_today", 0) >= 5:
        await update.message.reply_text("Сегодня уже 5 раз, брат.\nЗавтра снова сможешь.", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    user["last_hold_time"] = current.isoformat()
    user["last_hold_date"] = today.isoformat()
    user["hold_count_today"] = user.get("hold_count_today", 0) + 1
    data[str(chat_id)] = user
    save_data(data)
    
    await update.message.reply_text(random.choice(HOLD_RESPONSES), reply_markup=get_main_keyboard())
    
    active = get_active_users()
    for uid in active:
        if uid != chat_id:
            try:
                await context.bot.send_message(uid, "✊")
                await asyncio.sleep(0.2)
            except:
                pass
    
    reflection_keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("🧠 Мысль «хочу»"), KeyboardButton("😡 Эмоция")],
        [KeyboardButton("💭 Скука"), KeyboardButton("😰 Тревога")],
        [KeyboardButton("🤝 Компания"), KeyboardButton("🤷 Не знаю")],
        [KeyboardButton("✊ Я в порядке")]
    ], resize_keyboard=True)
    
    await update.message.reply_text("Красавчик. Что было ближе всего?", reply_markup=reflection_keyboard)
    return REFLECTION

async def handle_reflection(update, context):
    text = update.message.text
    chat_id = update.effective_chat.id
    
    responses = {
        "🧠 Мысль «хочу»": "Это просто мысль. Она не приказ.",
        "😡 Эмоция": "Эмоция — как волна. Поднимается и спадает.",
        "💭 Скука": "Скука часто маскируется под тягу.",
        "😰 Тревога": "Тревога хочет, чтобы ты убежал.",
        "🤝 Компания": "Социальное давление — самый сильный триггер.",
        "🤷 Не знаю": "Не знать — тоже нормально.",
        "✊ Я в порядке": "Ты в порядке. Горжусь тобой."
    }
    
    response = responses.get(text, "Ты молодец, что держишься.")
    
    if text != "✊ Я в порядке":
        exercise = get_next_exercise(chat_id)
        await update.message.reply_text(f"{response}\n\n{exercise}", reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text(response, reply_markup=get_main_keyboard())
    
    return ConversationHandler.END

async def handle_heavy(update, context):
    await update.message.reply_text("Я здесь, брат. Что тебе нужно прямо сейчас?", reply_markup=get_heavy_keyboard())

async def handle_exercise(update, context):
    exercise = get_next_exercise(update.effective_chat.id)
    await send_message(context.bot, update.effective_chat.id, exercise, get_exercise_keyboard(), False)

async def handle_another_exercise(update, context):
    exercise = get_next_exercise(update.effective_chat.id)
    await update.message.reply_text(exercise, reply_markup=get_exercise_keyboard())

async def handle_body_info(update, context):
    days = get_days_since_start(update.effective_chat.id)
    advice = get_advice_for_day(days)
    await send_message(context.bot, update.effective_chat.id, advice, get_advice_keyboard(), False)

async def handle_breakdown(update, context):
    await update.message.reply_text(
        "Спасибо, что сказал честно.\nЧто было ближе всего?",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("🧠 «Похер всё»"), KeyboardButton("😡 Эмоция сильнее")],
            [KeyboardButton("💭 Просто привычка"), KeyboardButton("🤝 Друзья/окружение")],
            [KeyboardButton("🧱 Не понимаю")]
        ], resize_keyboard=True)
    )
    return BREAKDOWN_STATE

async def handle_breakdown_response(update, context):
    text = update.message.text
    chat_id = update.effective_chat.id
    
    responses = {
        "🧠 «Похер всё»": "«Похер» — это про усталость и боль.",
        "😡 Эмоция сильнее": "Эмоции — сигналы. Ты уже научился их замечать.",
        "💭 Просто привычка": "Привычка — это мозг на автопилоте.",
        "🤝 Друзья/окружение": "Ты имеешь право выбирать своё окружение.",
        "🧱 Не понимаю": "Не понимать — нормально. Главное — ты не сдался."
    }
    
    reset_streak(chat_id)
    
    await update.message.reply_text(
        f"{responses.get(text, 'Ты сделал шаг вперёд.')}\n\nНачинаем с чистого листа.",
        reply_markup=get_main_keyboard()
    )
    
    return ConversationHandler.END

async def handle_days(update, context):
    chat_id = update.effective_chat.id
    _, user = get_user_data(chat_id)
    days = get_days_since_start(chat_id)
    best = user.get("best_streak", 0)
    
    if days == 0:
        msg = "Только начал. Первый день — самый тяжёлый."
    else:
        days_text = format_days_text(days)
        msg = f"Ты держишься {days_text}"
        if best > days:
            best_text = format_days_text(best)
            msg += f"\n\nЛучший стрик был: {best_text}"
        elif best > 0 and best == days:
            msg += f"\n\nЭто твой лучший стрик прямо сейчас"
    
    await send_message(context.bot, chat_id, msg, save=False)
    if days in MILESTONES:
        await send_message(context.bot, chat_id, MILESTONES[days], save=False)

async def handle_are_you_here(update, context):
    chat_id = update.effective_chat.id
    await asyncio.sleep(random.randint(2, 6))
    await send_message(context.bot, chat_id, random.choice(TU_TUT_FIRST), save=False)
    await asyncio.sleep(random.randint(2, 5))
    await send_message(context.bot, chat_id, random.choice(TU_TUT_SECOND), save=False)

async def handle_thank_you(update, context):
    text = "Спасибо тебе, брат, что ты есть. ❤️\n\nЕсли хочешь поддержать:\nСбер 2202 2084 3481 5313\n\nЛюбая сумма = ещё одному человеку поможем.\n\nГлавное — держись."
    await send_message(context.bot, update.effective_chat.id, text, save=False)

async def handle_back(update, context):
    await send_message(context.bot, update.effective_chat.id, "Возвращаемся.", get_main_keyboard(), False)

async def handle_text_message(update, context):
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    
    _, user = get_user_data(chat_id)
    
    if not user.get("active", False) and text != "▶ Начать":
        return
    
    if text == "▶ Начать":
        await start_command(update, context)
        return
    
    if text == "⏸ Помолчи":
        await stop_command(update, context)
        return
    
    if len(text) > 8 and text not in ["🔥 Упражнение", "🧠 Что происходит с телом", "🔄 Другое упражнение", "↩ Назад"]:
        await send_message(context.bot, chat_id, "Понимаю, брат. Тяжко.\nЖми ✊ Держусь или 😔 Тяжело.", save=False)

async def restore_jobs_on_startup(application):
    active = get_active_users()
    for user_id in active:
        try:
            schedule_user_jobs(user_id, application.job_queue)
        except:
            pass

def main():
    application = Application.builder().token(TOKEN).build()
    
    hold_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^✊ Держусь$"), handle_hold)],
        states={REFLECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reflection)]},
        fallbacks=[],
        conversation_timeout=300
    )
    
    breakdown_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💔 Срыв$"), handle_breakdown)],
        states={BREAKDOWN_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_breakdown_response)]},
        fallbacks=[],
        conversation_timeout=300
    )
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(hold_conv)
    application.add_handler(breakdown_conv)
    application.add_handler(MessageHandler(filters.Regex("^😔 Тяжело$"), handle_heavy))
    application.add_handler(MessageHandler(filters.Regex("^🔥 Упражнение$"), handle_exercise))
    application.add_handler(MessageHandler(filters.Regex("^🔄 Другое упражнение$"), handle_another_exercise))
    application.add_handler(MessageHandler(filters.Regex("^🧠 Что происходит с телом$"), handle_body_info))
    application.add_handler(MessageHandler(filters.Regex("^📊 Дни$"), handle_days))
    application.add_handler(MessageHandler(filters.Regex("^👋 Ты тут\?$"), handle_are_you_here))
    application.add_handler(MessageHandler(filters.Regex("^❤️ Спасибо$"), handle_thank_you))
    application.add_handler(MessageHandler(filters.Regex("^↩ Назад$"), handle_back))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    application.post_init = restore_jobs_on_startup
    
    logger.info("БОТ ЗАПУЩЕН")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
