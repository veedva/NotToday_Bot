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

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен!")

DATA_FILE = "user_data.json"
LOCK_FILE = DATA_FILE + ".lock"
MOSCOW_TZ = pytz.timezone('Europe/Moscow')
NOW = lambda: datetime.now(MOSCOW_TZ)

# ======================= ТЕКСТЫ =======================
MORNING_MESSAGES = [
    "Привет. Давай сегодня не будем, хорошо?",
    "Доброе утро, брат. Не сегодня.",
    "Привет. Держимся сегодня, да?",
    "Доброе. Сегодня дел много, нет наверное.",
    "Привет. Сегодня обойдёмся и так пиздец.",
    "Утро. Давай только не сегодня.",
    "Привет, брат. Сегодня пожалуй что ну его нахуй.",
    "Доброе утро. Я напишу ещё сегодня.",
    "Привет. Сегодня точно не надо.",
    "Доброе! Давай сегодня без этого вот.",
    "Привет лох. Денег жалко, да и ну его.",
    "Привет. Сегодня всё будет нормально.",
    "Братан, доброе. Сегодня точно нет.",
    "Эй. Сегодня не в тему.",
    "Доброе утро. Не сегодня.",
    "Привет. Может завтра, но сегодня нет.",
    "Утро. Сегодня спокойно обходимся.",
    "Чё как? Сегодня не стоит пожалуй."
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
    "Справился. До завтра.",
    "Сегодня получилось. Отдыхай."
]

MILESTONES = {
    3: "✨ Три дня уже. Неплохо идём, брат.",
    7: "✨ Неделя. Это уже норм.",
    14: "✨ Две недели! Ты реально держишься.",
    30: "✨ Месяц без этой хуйни. Уважаю по-настоящему.",
    60: "✨ Два месяца — уже другой уровень.",
    90: "✨ Три месяца. Ты машина.",
    180: "✨ Полгода. Легенда.",
    365: "✨ ГОД ЧИСТЫМ. Ты сделал это, брат ❤️"
}

TU_TUT_FIRST = ["Тут.", "Привет.", "А куда я денусь?", "Здесь.", "Тут, как всегда.", "Да, да.", "Чё как?", "Ага.", "Здравствуй.", "Тут, не переживай."]
TU_TUT_SECOND = ["Держимся.", "Я с тобой.", "Всё по плану.", "Не хочу сегодня.", "Сегодня не буду.", "Я рядом.", "Держись.", "Всё будет нормально.", "Я в деле.", "Под контролем."]

HOLD_RESPONSES = ["Отправлено. ✊", "Молодец. ✊", "Понял. ✊", "Так держать. ✊"]

# ======================= 25 ЛУЧШИХ ТЕХНИК — 2.0 =======================
HELP_TECHNIQUES = [
    "Лёд на запястья на 30–60 секунд. Холод резко снижает кортизол — тяга уходит за минуту.",
    "Дыхание 4-7-8: вдох на 4 секунды → задержка на 7 → выдох на 8. Повтори 4 раза. Успокаивает мгновенно.",
    "Поставь таймер на 5 минут и скажи себе: «Просто подожду 5 минут». 90% волн проходят сами.",
    "Встань и выйди в другую комнату. Смена контекста разрывает триггер.",
    "Кусок лимона, имбиря или солёного огурца в рот. Резкий вкус перебивает дофаминовый голод.",
    "Сожми кулаки сильно на 10 секунд → резко отпусти. Повтори 5 раз. Напряжение уходит из тела.",
    "Умой лицо ледяной водой 20–30 секунд. Шок для нервной системы — тревога падает.",
    "Быстро напиши 3 причины, почему именно сейчас НЕ НАДО. Помоги мозгу думать.",
    "10 медленных глубоких вдохов и выдохов. Кислород — твой лучший друг прямо сейчас.",
    "Планка 45–60 секунд. Пока мышцы горят — голова молчит.",
    "Быстрая прогулка 7–10 минут. Движение вырабатывает BDNF — естественный антидепрессант.",
    "Заземление 5-4-3-2-1: 5 вещей вижу, 4 трогаю, 3 слышу, 2 запаха, 1 вкус. Возвращает в тело.",
    "Контрастный душ: 30 секунд холодной → 1 минуту тёплой воды. Повтори 2 раза.",
    "Съешь горсть орехов или кусок сыра. Жиры стабилизируют сахар и гормоны.",
    "Сожми теннисный мячик до боли → отпусти. 10 раз. Сброс адреналина.",
    "Поза силы 2 минуты: ноги на ширине плеч, руки в боки, грудь вперёд. Меняет гормональный фон.",
    "HALT-проверка: голоден? злой? одинок? устал? Исправь хотя бы одну букву.",
    "Urge Surfing: представь тягу как волну. Не борись — наблюдай. Она всегда уходит.",
    "Напиши любому человеку: «Тяжко, брат». Стыдно? Именно поэтому это спасает.",
    "20 отжиманий до отказа. Пока тело в шоке — мозг забывает про дофамин.",
    "Лёд на лицо или в рот на 30 секунд. Максимальная физиологическая перезагрузка.",
    "Скажи вслух три раза: «Это пройдёт. Я сильнее». Голос фиксирует мысль.",
    "Медленно выпей большой стакан воды. Объём в желудке даёт сигнал безопасности.",
    "10 бёрпи прямо сейчас. Самый быстрый способ выжечь адреналин и кортизол.",
    "Включи любимый трек на полную и подвигайся 3 минуты. Новый дофамин без вещества."
]

# ======================= ЧТО ПРОИСХОДИТ С ТЕЛОМ — 2.0 =======================
HELP_ADVICE_BY_DAY = [
    "День 0–3: острая нехватка дофамина и серотонина. Мозг в панике орёт «верни привычку». Это физическая ломка. Перетерпи — пик пройдёт через 72 часа.",
    "Дни 4–7: рецепторы начинают оживать. Тяга ещё сильная, но появляются первые окна нормального настроения. Ты уже сильнее, чем вчера.",
    "Дни 8–14: дофаминовая система перестраивается. Простые вещи снова приносят радость. Сон и аппетит возвращаются.",
    "Дни 15–30: мозг активно восстанавливает нейронные связи. Энергия, вкус к жизни, сон — всё приходит в норму.",
    "Дни 31–60: нейропластичность на пике. Новые привычки становятся автоматическими. Ты уже другой человек.",
    "Дни 61–90: тяга становится редким гостем. Ты живёшь без этого и даже не вспоминаешь каждый день.",
    "90+ дней: точка невозврата пройдена. Мозг перестроился навсегда. Теперь главное — беречь себя и гордиться."
]

# ======================= КЛАВИАТУРЫ =======================
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
    return ReplyKeyboardMarkup([
        [KeyboardButton("↩ Назад")]
    ], resize_keyboard=True)

# ======================= ДАННЫЕ =======================
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
            "message_ids": []
        }
        save_data(data)
    return data, data[uid]

def get_days(user_id):
    _, user = get_user(user_id)
    if not user["start_date"]:
        return 0
    return (NOW().date() - datetime.fromisoformat(user["start_date"]).date()).days

def get_active_users():
    return [int(uid) for uid, u in load_data().items() if u.get("active", False)]

def get_next_exercise(user_data):
    used = user_data["used_tips"]
    total = len(HELP_TECHNIQUES)
    if len(used) >= total:
        used.clear()
    available = [i for i in range(total) if i not in used]
    if not available:
        used.clear()
        available = list(range(total))
    choice = random.choice(available)
    used.append(choice)
    return HELP_TECHNIQUES[choice]

def get_advice_for_day(days):
    if days == 0:
        return "День 0–3: острая нехватка дофамина и серотонина. Мозг в панике орёт «верни привычку». Это физическая ломка. Перетерпи — пик пройдёт через 72 часа."
    elif days <= 3:   return HELP_ADVICE_BY_DAY[0]
    elif days <= 7:   return HELP_ADVICE_BY_DAY[1]
    elif days <= 14:  return HELP_ADVICE_BY_DAY[2]
    elif days <= 30:  return HELP_ADVICE_BY_DAY[3]
    elif days <= 60:  return HELP_ADVICE_BY_DAY[4]
    elif days <= 90:  return HELP_ADVICE_BY_DAY[5]
    else:             return HELP_ADVICE_BY_DAY[6]

# ======================= ОТПРАВКА =======================
async def send(bot, chat_id, text, keyboard=None, save=True):
    kb = keyboard or get_main_keyboard()
    msg = await bot.send_message(chat_id, text, reply_markup=kb)
    if save:
        data, user = get_user(chat_id)
        user["message_ids"].append(msg.message_id)
        if len(user["message_ids"]) > 300:
            user["message_ids"] = user["message_ids"][-300:]
        save_data(data)
    return msg

async def midnight_clean(context):
    chat_id = context.job.chat_id
    data, user = get_user(chat_id)
    for msg_id in user.get("message_ids", []):
        try:
            await context.bot.delete_message(chat_id, msg_id)
            await asyncio.sleep(0.1)
        except:
            pass
    user["message_ids"] = []
    save_data(data)

# ======================= РАСПИСАНИЕ =======================
def schedule_jobs(chat_id, job_queue):
    for prefix in ["m", "e", "n", "c"]:
        for job in job_queue.get_jobs_by_name(f"{prefix}_{chat_id}"):
            job.schedule_removal()
    job_queue.run_daily(lambda ctx: morning_job(ctx, chat_id), time(9, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"m_{chat_id}")
    job_queue.run_daily(lambda ctx: evening_job(ctx, chat_id), time(18, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"e_{chat_id}")
    job_queue.run_daily(lambda ctx: night_job(ctx, chat_id), time(23, 0, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"n_{chat_id}")
    job_queue.run_daily(midnight_clean, time(0, 1, tzinfo=MOSCOW_TZ), chat_id=chat_id, name=f"c_{chat_id}")

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

# ======================= ✊ ДЕРЖУСЬ — С ГРАМОТНЫМИ ПАДЕЖАМИ =======================
async def handle_hold(chat_id, context):
    data, user = get_user(chat_id)
    today = NOW().date()
    count_today = user.get("hold_count_today", 0)
    last_time = user.get("last_hold_time")

    if user.get("last_hold_date") != str(today):
        count_today = 0

    if last_time:
        delta = (NOW() - datetime.fromisoformat(last_time)).total_seconds()
        if delta < 1800:
            mins = int((1800 - delta + 59) // 60)
            if mins == 1:
                await send(context.bot, chat_id, "Погоди ещё 1 минуту, брат.", save=False)
            elif mins in [2, 3, 4]:
                await send(context.bot, chat_id, f"Погоди ещё {mins} минуты, брат.", save=False)
            else:
                await send(context.bot, chat_id, f"Погоди ещё {mins} минут, брат.", save=False)
            return

    if count_today >= 5:
        await send(context.bot, chat_id, "Сегодня уже 5 раз, брат.\nЗавтра снова сможешь.", save=False)
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

# ======================= КОМАНДЫ =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data, user = get_user(chat_id)
    user["active"] = True
    user["start_date"] = NOW().isoformat()
    user["used_tips"] = []
    user["hold_count_today"] = 0
    user["last_hold_date"] = None
    user["last_hold_time"] = None
    save_data(data)

    await send(context.bot, chat_id,
        "Привет, брат.\n\n"
        "Я буду писать три раза в день — просто напомню: сегодня не надо.\n\n"
        "Когда тяжело — жми ✊ Держусь\nВсе получат пуш и узнают, что ты ещё здесь.\n"
        "Можешь жать до 5 раз в сутки.\n\n"
        "Держись. Я рядом.", save=False)

    schedule_jobs(chat_id, context.job_queue)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data, user = get_user(chat_id)
    user["active"] = False
    save_data(data)
    for prefix in ["m", "e", "n", "c"]:
        for job in context.job_queue.get_jobs_by_name(f"{prefix}_{chat_id}"):
            job.schedule_removal()
    await send(context.bot, chat_id, "Уведомления остановлены.\nКогда будешь готов — жми ▶ Начать", get_start_keyboard(), False)

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
    save_data(data)

# ======================= ОБРАБОТЧИК =======================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    _, user = get_user(chat_id)

    if text == "▶ Начать":
        await start(update, context)
        return

    if not user.get("active", False):
        return

    days = get_days(chat_id)

    if text == "✊ Держусь":
        await handle_hold(chat_id, context)
        return

    if text == "😔 Тяжело":
        await send(context.bot, chat_id, "Держись, брат. Что будем делать?", get_heavy_keyboard(), False)
        return

    if text == "📊 Дни":
        best = user.get("best_streak", 0)
        msg = f"Ты держишься {days} дней"
        if best > days:
            msg += f"\n\nЛучший стрик был: {best} дней"
        elif best > 0 and best == days:
            msg += f"\n\nЭто твой лучший стрик прямо сейчас"
        await send(context.bot, chat_id, msg, save=False)
        if days in MILESTONES:
            await send(context.bot, chat_id, MILESTONES[days], save=False)
        return

    if text == "👋 Ты тут?":
        await asyncio.sleep(random.randint(2, 6))
        await send(context.bot, chat_id, random.choice(TU_TUT_FIRST), save=False)
        await asyncio.sleep(random.randint(2, 5))
        await send(context.bot, chat_id, random.choice(TU_TUT_SECOND), save=False)
        return

    if text == "❤️ Спасибо":
        await send(context.bot, chat_id,
            "Спасибо тебе, брат, что ты есть. ❤️\n\n"
            "Если хочешь поддержать того, кто это всё написал:\n"
            "Сбер 2202 2084 3481 5313\n\n"
            "Любая сумма = ещё одному человеку поможем.\n\n"
            "Главное — держись.", save=False)
        return

    if text == "⏸ Помолчи":
        await stop(update, context)
        return

    # ЭМОДЗИ-КНОПКИ
    if text in ["🔥 Упражнение", "Упражнения", "Упражнение"]:
        await send(context.bot, chat_id, get_next_exercise(user), get_exercise_keyboard(), False)
        return

    if text in ["🧠 Что происходит с телом", "Что происходит с телом"]:
        await send(context.bot, chat_id, get_advice_for_day(days), get_advice_keyboard(), False)
        return

    if text in ["🔄 Другое упражнение", "Другое упражнение"]:
        await send(context.bot, chat_id, get_next_exercise(user), get_exercise_keyboard(), False)
        return

    if text in ["💔 Срыв", "Срыв"]:
        reset_streak(chat_id)
        await send(context.bot, chat_id,
            "Ничего страшного, брат.\nГлавное — ты сказал честно.\nЭто уже победа.\n"
            "Начинаем с чистого листа. Я с тобой.", get_main_keyboard(), False)
        return

    if text in ["↩ Назад", "Назад"]:
        await send(context.bot, chat_id, "Возвращаемся.", get_main_keyboard(), False)
        return

    if len(text) > 8:
        await send(context.bot, chat_id,
            "Понимаю, брат. Тяжко.\n"
            "Жми ✊ Держусь — всем разошлю.\n"
            "Или 😔 Тяжело — подберём приём прямо сейчас.", save=False)

# ======================= ЗАПУСК =======================
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("БОТ ХЕЛПА 2.0 — ФИНАЛЬНАЯ ВЕРСИЯ — ЗАПУЩЕН ✊")
    app.run_polling()

if __name__ == "__main__":
    main()
