import logging
import random
import json
import os
import asyncio
from datetime import datetime, time, date
from filelock import FileLock
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import pytz

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
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
BREAKDOWN_STATE = 1

MORNING_MESSAGES = [
    "Привет. Давай сегодня не будем, хорошо?", "Доброе утро. Не сегодня.", "Привет. Держимся сегодня?",
    "Доброе утро. Сегодня много дел, наверное нет.", "Привет. Сегодня обойдёмся без этого.", "Утро. Давай сегодня пропустим.",
    "Привет. Сегодня пожалуй что не стоит.", "Доброе утро. Напишу ещё сегодня.", "Привет. Сегодня точно не надо.",
    "Доброе! Давай сегодня без этого.", "Привет. Денег жалко, да и не стоит.", "Привет. Всё будет нормально.",
    "Доброе. Сегодня точно нет.", "Привет. Сегодня не в тему.", "Доброе утро. Не сегодня.", "Привет. Может завтра, но сегодня нет.",
    "Утро. Сегодня спокойно обходимся.", "Как дела? Сегодня не стоит пожалуй."
]

EVENING_MESSAGES = [
    "Не сегодня. Держись.", "Я тут. Давай не сегодня.", "Привет. Сегодня держимся, помнишь?",
    "Держись. Сегодня нет.", "Ещё чуть-чуть. Не сегодня.", "Я с тобой. Сегодня точно нет.",
    "Привет. Давай обойдёмся.", "Мы же решили — не сегодня.", "Держись там. Сегодня мимо.",
    "Привет. Сегодня пропустим.", "Сегодня точно можно без этого.", "Сегодня не надо.",
    "Привет. Может завтра, сегодня мимо.", "Как дела? Сегодня обойдёмся.", "Привет. Сегодня не будем.",
    "Привет. Сегодня точно ни к чему.", "Может завтра, а сегодня нет?"
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

TU_TUT_FIRST = ["Тут.", "Привет.", "А куда я денусь?", "Здесь.", "Тут, как всегда.", "Да, да.", "Как дела?", "Ага.", "Здравствуй.", "Тут, не переживай."]
TU_TUT_SECOND = ["Держимся.", "Я с тобой.", "Всё по плану.", "Не хочу сегодня.", "Сегодня не буду.", "Я рядом.", "Держись.", "Всё будет нормально.", "Я в деле.", "Под контролем."]
HOLD_RESPONSES = ["Отправлено. ✊", "Молодец. ✊", "Понял. ✊", "Так держать. ✊"]

HELP_TECHNIQUES = [
    "Лёд на запястья 30-60 сек. Холод активирует блуждающий нерв — тяга падает за минуту.",
    "Дыхание 4-7-8: вдох на 4 → задержка на 7 → выдох на 8. 4 раза. Снижает кортизол.",
    "Таймер на 5 минут: «Просто подожди». Тяга как волна — пройдёт сама за 3-7 минут.",
    "Встань и выйди в другую комнату. Смена контекста разрывает нейронную связь.",
    "Кусок лимона или имбиря в рот. Резкий вкус перебивает дофаминовый сигнал.",
    "Сожми кулаки 10 сек → отпусти. 5 раз. Физическое напряжение уходит.",
    "Умой лицо ледяной водой 30 сек. Активирует рефлекс погружения — мгновенное успокоение.",
    "Напиши 3 причины, почему сейчас не надо. Помоги мозгу вспомнить логику.",
    "10 медленных глубоких вдохов. Кислород снижает адреналин и возвращает контроль.",
    "Планка 45-60 секунд. Пока мышцы горят — голова не думает о тяге.",
    "Быстрая прогулка 7-10 минут. Движение вырабатывает BDNF — природный антидепрессант.",
    "5-4-3-2-1: назови 5 вещей (вижу), 4 (трогаю), 3 (слышу), 2 (запах), 1 (вкус).",
    "Контрастный душ: 30 сек холодной → 1 мин тёплой. Повтори 2 раза.",
    "Съешь горсть орехов или сыра. Белок и жиры стабилизируют сахар в крови.",
    "Сожми теннисный мячик до боли. 10 раз. Физический выброс адреналина через руки.",
    "Поза силы 2 минуты: ноги широко, руки в боки, грудь вперёд.",
    "HALT: голоден? злой? одинок? устал? Исправь хоть одно.",
    "Urge Surfing: представь тягу как волну. Не борись — наблюдай со стороны.",
    "Напиши любому: «Тяжко, брат». Стыдно? Именно поэтому это работает.",
    "20 отжиманий до отказа. Пока тело в шоке — мозг забывает про дофаминовый голод.",
    "Лёд в рот 30 секунд. Максимальная физиологическая перезагрузка.",
    "Скажи вслух 3 раза: «Это пройдёт. Я сильнее».",
    "Медленно выпей большой стакан воды. Объём в желудке даёт сигнал безопасности.",
    "10 бёрпи. Самый быстрый способ сжечь адреналин и кортизол.",
    "Включи любимый трек и подвигайся 3 минуты. Новый дофамин без вещества.",
    "Позвони другу или родителям. Социальная связь повышает окситоцин.",
    "Список из 5 вещей, за которые благодарен. Переключает мозг на позитив.",
    "Съешь что-то сладкое + вода. Быстрый сахар стабилизирует настроение на 15-20 минут.",
    "Ляг на пол и расслабь все мышцы 2 минуты. Полная релаксация снижает кортизол.",
    "Смешное видео или мемы на 5 минут. Смех — природный антидепрессант."
]

SCIENCE_MATERIALS = [
    "🧬 Что сейчас происходит:\nДни 1-3: пик симптомов. Рецепторы требуют дофамин. Это ломка.\nДни 4-7: симптомы -40%. Настроение скачет. Появляются окна ясности.\nДни 8-14: рецепторы оживают. Сон налаживается.\nДни 15-28: мозг работает чище. Энергия возвращается.\nДни 29-90: полная перезагрузка. Жизнь без зависимости.",
    
    "📊 Стадии восстановления:\n1-3 дня: острая фаза. Пик симптомов.\n4-7 дней: подострая. Симптомы спадают.\n8-14 дней: адаптация. Рецепторы оживают.\n15-28 дней: восстановление. Эмоции стабильны.\n29-90 дней: стабилизация. Новая норма.",
    
    "🔬 Факты науки:\n• CB1-рецепторы восстанавливаются за 4-6 недель\n• Дофаминовая система приходит в норму через 2-4 недели\n• Сон нормализуется к 14-21 дню\n• Пик физических симптомов — 72 часа\n• 75% людей срываются в первые 30 дней — это нормально\n• Каждая попытка укрепляет нейронные пути",
    
    "🧠 Нейронаука:\nТяга — это нейрохимический процесс. Мозг требует привычный дофамин. Рецепторы отвыкают за 4 недели. Каждый день чистоты перестраивает нейронные связи. Срыв не стирает прогресс — мозг запоминает каждый день без вещества.",
    
    "⚡ Физиология:\nПервые 72 часа: температура, потливость, тревога 8/10.\nНеделя: энергия нулевая, сон прерывистый.\nДве недели: появляется естественная радость от простых вещей.\nМесяц: мозг производит дофамин сам. Когнитивные функции +25%.\nТри месяца: полное восстановление. Тяга редко и слабо."
]

PROTOCOLS = {
    "сон": [
        "💤 Сон сейчас: За 2 часа до сна — никаких экранов. Температура 18°C.",
        "💤 Сон сейчас: Не спится — встань. 15 мин чтения бумажной книги.",
        "💤 Сон сейчас: Дыхание 4-7-8 в кровати. 6 циклов.",
        "💤 Сон сейчас: Белый шум/дождь 30 мин. Мозг фокусируется на монотонном звуке."
    ],
    "тревога": [
        "😰 Тревога сейчас: Холодное умывание 30 сек. Активирует блуждающий нерв.",
        "😰 Тревога сейчас: 5-4-3-2-1: 5 вижу, 4 трогаю, 3 слышу, 2 нюхаю, 1 вкус.",
        "😰 Тревога сейчас: Планка до отказа. Мышцы горят — мозг забывает про тревогу.",
        "😰 Тревога сейчас: «Это просто тревога. Пройдёт через 15 мин». Скажи вслух 3 раза."
    ],
    "аппетит": [
        "🍽 Аппетит сейчас: Жидкая пища первые дни. Смузи, бульон.",
        "🍽 Аппетит сейчас: Маленькие порции каждые 3 часа. Орехи, банан, йогурт.",
        "🍽 Аппетит сейчас: Имбирь/лимон в воду. Стимулирует ЖКТ.",
        "🍽 Аппетит сейчас: Не заставляй себя. Тело знает, когда готово."
    ],
    "паника": [
        "⚡ Паника сейчас: Лёд в рот 30 сек. Шок для нервной системы.",
        "⚡ Паника сейчас: Быстрая прогулка 7-10 мин. Движение сжигает адреналин.",
        "⚡ Паника сейчас: «Я в безопасности сейчас». Повтори как мантру.",
        "⚡ Паника сейчас: Позвони кому-то. Голос выводит из петли паники."
    ]
}

COGNITIVE_DISTORTIONS = [
    "🤯 «Я всё испортил»\nФакт: Один срыв ≠ провал. Мозг учится. Каждая попытка укрепляет нейронные пути.",
    "🤯 «Ничего не работает»\nФакт: Работает, но медленно. Нейропластичность требует времени.",
    "🤯 «Я слабый»\nФакт: Зависимость — болезнь, а не слабость. Ты борешься с нейрохимическим дисбалансом.",
    "🤯 «Всё бессмысленно»\nФакт: Смысл появится через 2-3 недели. Сейчас мозг в режиме выживания.",
    "🤯 «У других получается»\nФакт: У всех свои сроки. Ты видишь только результат, а не 5 попыток до него."
]

FRIEND_HELP_ADVICE = [
    "🤝 Другу: Напиши «Держусь, брат» раз в день. Не жди ответа.",
    "🤝 Другу: «Гуляю 15 мин, присоединяйся если хочешь». Без давления.",
    "🤝 Другу: Не давай советов. Скажи: «Я рядом. Расскажи, если хочешь».",
    "🤝 Другу: Напомни о прогрессе: «Ты уже 3 дня держишься, это круто».",
    "🤝 Другу: «Давай 4-7-8: вдох… задержка… выдох». Вместе."
]

TRIGGER_RESPONSES = [
    "🧠 Мысль «хочу»\nМысль ≠ команда. Наблюдай за ней, как за облаком.\nПоможет: Упражнение",
    "🌊 Сильная эмоция\nЭмоции как волны: поднимаются и спадают.\nПоможет: Протокол тревоги",
    "⏳ Скука/безделье\nСкука маскируется под тягу. Мозг ищет стимуляцию.\nПоможет: Упражнение",
    "😰 Тревога/стресс\nТревога говорит «Убеги!». Она пройдёт через 15 минут.\nПоможет: Протокол тревоги",
    "👥 Компания/окружение\nСоциальное давление — сильный триггер.\nПоможет: Помощь другу",
    "🤷 Сложно определить\nИногда причины неясны — это нормально.\nПоможет: Упражнение"
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
        [KeyboardButton("🔥 Упражнение"), KeyboardButton("🧠 Наука")],
        [KeyboardButton("💔 Срыв"), KeyboardButton("🤯 Искажения")],
        [KeyboardButton("🤝 Помощь другу"), KeyboardButton("🧘 Триггеры")],
        [KeyboardButton("↩ Назад")]
    ], resize_keyboard=True)

def get_protocols_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💤 Сон"), KeyboardButton("😰 Тревога")],
        [KeyboardButton("🍽 Аппетит"), KeyboardButton("⚡ Паника")],
        [KeyboardButton("↩ Назад")]
    ], resize_keyboard=True)

def get_exercise_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔄 Другое упражнение")],
        [KeyboardButton("↩ Назад")]
    ], resize_keyboard=True)

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
                        except:
                            user["start_date"] = None
                    if "last_hold_time" in user and user["last_hold_time"]:
                        try:
                            datetime.fromisoformat(user["last_hold_time"])
                        except:
                            user["last_hold_time"] = None
                    user.setdefault("active", False)
                    user.setdefault("best_streak", 0)
                    user.setdefault("hold_count_today", 0)
                    user.setdefault("last_hold_date", None)
                    user.setdefault("used_tips", [])
                    user.setdefault("message_ids", [])
                    user.setdefault("used_science", [])
                return data
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
            if os.path.exists(DATA_FILE):
                backup = f"{DATA_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(DATA_FILE, backup)
            return {}

def save_data(data):
    with FileLock(LOCK_FILE):
        temp = f"{DATA_FILE}.tmp"
        try:
            with open(temp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp, DATA_FILE)
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")
            if os.path.exists(temp):
                os.remove(temp)

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
            "message_ids": [],
            "used_science": []
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
    except Exception as e:
        logger.error(f"Ошибка расчета дней для {user_id}: {e}")
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

def get_next_science(user_id):
    data, user = get_user_data(user_id)
    used = user.get("used_science", [])
    total = len(SCIENCE_MATERIALS)
    
    if len(used) >= total:
        used = []
        user["used_science"] = used
    
    available = [i for i in range(total) if i not in used]
    if not available:
        used = []
        available = list(range(total))
    
    choice = random.choice(available)
    used.append(choice)
    user["used_science"] = used
    data[str(user_id)] = user
    save_data(data)
    return SCIENCE_MATERIALS[choice]

def get_stage_for_day(days):
    if days <= 3: return "🔥 Дни 1-3: Острая фаза. Пик симптомов. Самое тяжёлое."
    elif days <= 7: return "🌧 Дни 4-7: Подострая фаза. Симптомы -40%. Настроение скачет."
    elif days <= 14: return "⛅ Дни 8-14: Адаптация. Рецепторы оживают. Сон налаживается."
    elif days <= 28: return "🌈 Дни 15-28: Восстановление. Мозг чище. Энергия возвращается."
    return "🚀 Дни 29-90: Стабилизация. Новая норма. Жизнь без зависимости."

def get_protocol(protocol_type):
    return random.choice(PROTOCOLS.get(protocol_type, ["Попробуй упражнение."]))

def reset_streak(user_id):
    data, user = get_user_data(user_id)
    current = get_days_since_start(user_id)
    if current > user.get("best_streak", 0):
        user["best_streak"] = current
    
    user.setdefault("relapses", [])
    user["relapses"].append({
        "date": get_current_date().isoformat(),
        "streak": current,
        "best_streak": user.get("best_streak", 0)
    })
    
    user["start_date"] = get_current_date().isoformat()
    user["hold_count_today"] = 0
    user["last_hold_date"] = None
    user["last_hold_time"] = None
    user["used_tips"] = []
    user["used_science"] = []
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
    try:
        data, user = get_user_data(chat_id)
        msg_ids = user.get("message_ids", [])
        user["message_ids"] = []
        data[str(chat_id)] = user
        save_data(data)
        
        for i in range(0, len(msg_ids), 5):
            batch = msg_ids[i:i+5]
            for msg_id in batch:
                try:
                    await context.bot.delete_message(chat_id, msg_id)
                except:
                    pass
            await asyncio.sleep(0.3)
    except Exception as e:
        logger.error(f"Ошибка очистки для {chat_id}: {e}")

def schedule_user_jobs(chat_id, job_queue):
    for prefix in ["morning", "evening", "night", "cleanup"]:
        for job in job_queue.jobs():
            if job.name == f"{prefix}_{chat_id}":
                job.schedule_removal()
    
    try:
        job_queue.run_daily(morning_job, time(9, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"morning_{chat_id}")
        job_queue.run_daily(evening_job, time(18, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"evening_{chat_id}")
        job_queue.run_daily(night_job, time(23, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"night_{chat_id}")
        job_queue.run_daily(midnight_cleanup, time(0, 1, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"cleanup_{chat_id}")
    except Exception as e:
        logger.error(f"Ошибка планирования заданий для {chat_id}: {e}")

async def morning_job(context):
    chat_id = context.job.chat_id
    try:
        _, user = get_user_data(chat_id)
        if not user.get("active", False):
            return
        
        days = get_days_since_start(chat_id)
        
        if days in MILESTONES:
            await send_message(context.bot, chat_id, f"{random.choice(MORNING_MESSAGES)}\n\n{MILESTONES[days]}")
        else:
            await send_message(context.bot, chat_id, random.choice(MORNING_MESSAGES))
    except Exception as e:
        logger.error(f"Ошибка утреннего задания для {chat_id}: {e}")

async def evening_job(context):
    chat_id = context.job.chat_id
    try:
        _, user = get_user_data(chat_id)
        if not user.get("active", False):
            return
        await send_message(context.bot, chat_id, random.choice(EVENING_MESSAGES))
    except Exception as e:
        logger.error(f"Ошибка вечернего задания для {chat_id}: {e}")

async def night_job(context):
    chat_id = context.job.chat_id
    try:
        _, user = get_user_data(chat_id)
        if not user.get("active", False):
            return
        await send_message(context.bot, chat_id, random.choice(NIGHT_MESSAGES))
    except Exception as e:
        logger.error(f"Ошибка ночного задания для {chat_id}: {e}")

async def start_command(update, context):
    chat_id = update.effective_chat.id
    try:
        data, user = get_user_data(chat_id)
        
        if not user.get("active", False):
            user["active"] = True
            user["start_date"] = get_current_date().isoformat()
            user["used_tips"] = []
            user["hold_count_today"] = 0
            user["last_hold_date"] = None
            user["last_hold_time"] = None
            user["used_science"] = []
            data[str(chat_id)] = user
            save_data(data)
            
            schedule_user_jobs(chat_id, context.job_queue)
        
        days = get_days_since_start(chat_id)
        if days == 0:
            welcome = "Привет. Ты начинаешь путь. Первые шаги самые важные."
        else:
            welcome = f"Привет. Ты держишься {format_days_text(days)}. Я рядом."
        
        welcome += "\n\nЯ буду писать три раза в день.\nКогда тяжело — жми ✊ Держусь\nВсе узнают, что ты ещё здесь.\nМожешь жать до 5 раз в сутки.\n\nДержись."
        
        await update.message.reply_text(welcome, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Ошибка в start_command для {chat_id}: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте снова.")

async def stop_command(update, context):
    chat_id = update.effective_chat.id
    try:
        data, user = get_user_data(chat_id)
        user["active"] = False
        data[str(chat_id)] = user
        save_data(data)
        
        for prefix in ["morning", "evening", "night", "cleanup"]:
            for job in context.job_queue.jobs():
                if job.name == f"{prefix}_{chat_id}":
                    job.schedule_removal()
        
        await update.message.reply_text("Уведомления остановлены.\nКогда будешь готов — жми ▶ Начать", reply_markup=get_start_keyboard())
    except Exception as e:
        logger.error(f"Ошибка в stop_command для {chat_id}: {e}")

async def handle_hold(update, context):
    chat_id = update.effective_chat.id
    try:
        _, user = get_user_data(chat_id)
        if not user.get("active", False):
            await update.message.reply_text("Сначала нажми ▶ Начать", reply_markup=get_start_keyboard())
            return
        
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
                    mins = int((1800 - diff + 59) // 60)
                    if mins == 1:
                        await update.message.reply_text("Подожди ещё минуту.", reply_markup=get_main_keyboard())
                        return
                    else:
                        await update.message.reply_text(f"Подожди ещё {mins} минут.", reply_markup=get_main_keyboard())
                        return
            except:
                pass
        
        if user.get("hold_count_today", 0) >= 5:
            await update.message.reply_text("Сегодня уже 5 раз.\nЗавтра снова сможешь.", reply_markup=get_main_keyboard())
            return
        
        user["last_hold_time"] = current.isoformat()
        user["last_hold_date"] = today.isoformat()
        user["hold_count_today"] = user.get("hold_count_today", 0) + 1
        data[str(chat_id)] = user
        save_data(data)
        
        await update.message.reply_text(random.choice(HOLD_RESPONSES), reply_markup=get_main_keyboard())
        
        # Отправка кулачков другим пользователям
        active = get_active_users()
        sent = 0
        for uid in active:
            if uid != chat_id and sent < 20:
                try:
                    await context.bot.send_message(uid, "✊")
                    sent += 1
                    if sent % 5 == 0:
                        await asyncio.sleep(0.3)
                except Exception as e:
                    logger.error(f"Ошибка отправки кулачка {uid}: {e}")
        
    except Exception as e:
        logger.error(f"Ошибка в handle_hold для {chat_id}: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте снова.", reply_markup=get_main_keyboard())

async def handle_heavy(update, context):
    await update.message.reply_text("Что нужно?", reply_markup=get_heavy_keyboard())

async def handle_exercise(update, context):
    exercise = get_next_exercise(update.effective_chat.id)
    await update.message.reply_text(exercise, reply_markup=get_exercise_keyboard())

async def handle_another_exercise(update, context):
    exercise = get_next_exercise(update.effective_chat.id)
    await update.message.reply_text(exercise, reply_markup=get_exercise_keyboard())

async def handle_science(update, context):
    science = get_next_science(update.effective_chat.id)
    await update.message.reply_text(science, reply_markup=get_heavy_keyboard())

async def handle_breakdown(update, context):
    breakdown_text = (
        "Срыв — это часть процесса\n\n"
        "Факт: 85% людей срываются в первые 30 дней.\n"
        "Факт: Среднее число попыток до устойчивой ремиссии — 3-5.\n"
        "Факт: Каждая попытка укрепляет нейронные пути.\n\n"
        "Это не провал. Это данные для следующей попытки.\n\n"
        "Что было ближе всего?"
    )
    
    await update.message.reply_text(
        breakdown_text,
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("😔 Усталость/апатия"), KeyboardButton("🌊 Эмоциональный всплеск")],
            [KeyboardButton("🔄 Автоматическая привычка"), KeyboardButton("👥 Социальное влияние")],
            [KeyboardButton("🤷 Не понимаю причину")]
        ], resize_keyboard=True)
    )
    return BREAKDOWN_STATE

async def handle_breakdown_response(update, context):
    text = update.message.text
    chat_id = update.effective_chat.id
    
    try:
        responses = {
            "😔 Усталость/апатия": "«Всё равно» — часто говорит об истощении.",
            "🌊 Эмоциональный всплеск": "Иногда эмоции накрывают с головой. Это информация.",
            "🔄 Автоматическая привычка": "Мозг на автопилоте. Ты уже вышел из автоматизма.",
            "👥 Социальное влияние": "Окружение формирует привычки. Новые стратегии.",
            "🤷 Не понимаю причину": "Не всегда можно понять причину. Главное — ты вернулся."
        }
        
        reset_streak(chat_id)
        
        recovery_protocol = (
            "\n\nПротокол восстановления:\n"
            "1. 10 глубоких вдохов\n"
            "2. Стакан воды\n"
            "3. Скажи: «Начинаю с чистого листа»\n"
            "4. Жми ▶ Начать когда готов"
        )
        
        await update.message.reply_text(
            f"{responses.get(text, 'Ты сделал шаг вперёд.')}{recovery_protocol}",
            reply_markup=get_start_keyboard()
        )
        
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка в handle_breakdown_response для {chat_id}: {e}")
        await update.message.reply_text("Произошла ошибка.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

async def handle_distortions(update, context):
    distortion = random.choice(COGNITIVE_DISTORTIONS)
    await update.message.reply_text(distortion, reply_markup=get_heavy_keyboard())

async def handle_friend_help(update, context):
    advice = random.choice(FRIEND_HELP_ADVICE)
    await update.message.reply_text(advice, reply_markup=get_heavy_keyboard())

async def handle_triggers(update, context):
    trigger = random.choice(TRIGGER_RESPONSES)
    await update.message.reply_text(trigger, reply_markup=get_heavy_keyboard())

async def handle_protocol(update, context):
    text = update.message.text
    chat_id = update.effective_chat.id
    
    protocol_map = {
        "💤 Сон": "сон",
        "😰 Тревога": "тревога", 
        "🍽 Аппетит": "аппетит",
        "⚡ Паника": "паника"
    }
    
    protocol_type = protocol_map.get(text)
    if protocol_type:
        protocol = get_protocol(protocol_type)
        await update.message.reply_text(protocol, reply_markup=get_protocols_keyboard())

async def handle_days(update, context):
    chat_id = update.effective_chat.id
    try:
        _, user = get_user_data(chat_id)
        days = get_days_since_start(chat_id)
        best = user.get("best_streak", 0)
        
        if days == 0:
            msg = "Ты только начинаешь. Первый день — самый важный."
        else:
            days_text = format_days_text(days)
            msg = f"Ты держишься {days_text}."
            if best > days:
                best_text = format_days_text(best)
                msg += f"\n\nЛучший стрик: {best_text}"
            elif best > 0 and best == days:
                msg += f"\n\nЭто твой лучший стрик прямо сейчас"
        
        if days > 0:
            stage = get_stage_for_day(days)
            msg += f"\n\n{stage}"
        
        await update.message.reply_text(msg, reply_markup=get_main_keyboard())
        if days in MILESTONES:
            await update.message.reply_text(MILESTONES[days], reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Ошибка в handle_days для {chat_id}: {e}")
        await update.message.reply_text("Произошла ошибка.", reply_markup=get_main_keyboard())

async def handle_are_you_here(update, context):
    chat_id = update.effective_chat.id
    try:
        await asyncio.sleep(random.randint(2, 6))
        await update.message.reply_text(random.choice(TU_TUT_FIRST), reply_markup=get_main_keyboard())
        await asyncio.sleep(random.randint(2, 5))
        await update.message.reply_text(random.choice(TU_TUT_SECOND), reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Ошибка в handle_are_you_here для {chat_id}: {e}")

async def handle_thank_you(update, context):
    text = "Спасибо тебе, что ты есть. ❤️\n\nЕсли хочешь поддержать:\nСбер 2202 2084 3481 5313\n\nЛюбая сумма = ещё одному человеку поможем.\n\nГлавное — держись."
    await update.message.reply_text(text, reply_markup=get_main_keyboard())

async def handle_back(update, context):
    await update.message.reply_text("Окей", reply_markup=get_main_keyboard())

async def handle_text_message(update, context):
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    
    try:
        _, user = get_user_data(chat_id)
        
        if not user.get("active", False):
            if text == "▶ Начать":
                await start_command(update, context)
            return
        
        if text == "▶ Начать":
            await start_command(update, context)
            return
        
        if text == "⏸ Помолчи":
            await stop_command(update, context)
            return
    except Exception as e:
        logger.error(f"Ошибка в handle_text_message для {chat_id}: {e}")

async def restore_jobs_on_startup(application):
    active = get_active_users()
    logger.info(f"Восстанавливаем задания для {len(active)} активных пользователей")
    for user_id in active:
        try:
            schedule_user_jobs(user_id, application.job_queue)
        except Exception as e:
            logger.error(f"Ошибка восстановления заданий для {user_id}: {e}")

def main():
    application = Application.builder().token(TOKEN).build()
    
    breakdown_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💔 Срыв$"), handle_breakdown)],
        states={BREAKDOWN_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_breakdown_response)]},
        fallbacks=[],
        conversation_timeout=300
    )
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(breakdown_conv)
    
    application.add_handler(MessageHandler(filters.Regex("^✊ Держусь$"), handle_hold))
    application.add_handler(MessageHandler(filters.Regex("^😔 Тяжело$"), handle_heavy))
    application.add_handler(MessageHandler(filters.Regex("^🔥 Упражнение$"), handle_exercise))
    application.add_handler(MessageHandler(filters.Regex("^🔄 Другое упражнение$"), handle_another_exercise))
    application.add_handler(MessageHandler(filters.Regex("^🧠 Наука$"), handle_science))
    application.add_handler(MessageHandler(filters.Regex("^📊 Дни$"), handle_days))
    application.add_handler(MessageHandler(filters.Regex("^👋 Ты тут\?$"), handle_are_you_here))
    application.add_handler(MessageHandler(filters.Regex("^❤️ Спасибо$"), handle_thank_you))
    application.add_handler(MessageHandler(filters.Regex("^↩ Назад$"), handle_back))
    application.add_handler(MessageHandler(filters.Regex("^🤯 Искажения$"), handle_distortions))
    application.add_handler(MessageHandler(filters.Regex("^🤝 Помощь другу$"), handle_friend_help))
    application.add_handler(MessageHandler(filters.Regex("^🧘 Триггеры$"), handle_triggers))
    
    application.add_handler(MessageHandler(filters.Regex("^💤 Сон$"), handle_protocol))
    application.add_handler(MessageHandler(filters.Regex("^😰 Тревога$"), handle_protocol))
    application.add_handler(MessageHandler(filters.Regex("^🍽 Аппетит$"), handle_protocol))
    application.add_handler(MessageHandler(filters.Regex("^⚡ Паника$"), handle_protocol))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    application.post_init = restore_jobs_on_startup
    
    logger.info("Бот запущен")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
