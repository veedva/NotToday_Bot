# bot.py
import logging
import random
import json
import os
import asyncio
from datetime import datetime, date, time, timedelta
from filelock import FileLock
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
import pytz

# ------------------ CONFIG ------------------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен в окружении")

DATA_FILE = "user_data.json"
LOCK_FILE = DATA_FILE + ".lock"
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log", encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ------------------ CONTENT (full-ish) ------------------
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

MILESTONES = {
    3: "✨ Три дня уже. Самое тяжёлое позади.",
    7: "✨ Неделя. Рецепторы начинают восстанавливаться.",
    14: "✨ Две недели! Сон налаживается, голова яснее.",
    21: "✨ Три недели. Ты уже почти не думаешь об этом.",
    30: "✨ Месяц без этого. Мозг работает по-новому.",
    60: "✨ Два месяца — ты другой человек.",
    90: "✨ Три месяца. Полное восстановление. Ты молодец."
}

HELP_TECHNIQUES = [
    "🧊 Лёд на запястья 30-60 сек. Холод активирует блуждающий нерв — тяга падает за минуту.",
    "🫁 Дыхание 4-7-8: вдох 4 → задержка 7 → выдох 8. 4 раза. Снижает кортизол.",
    "⏱ Таймер на 5 минут: «Просто подожди». Тяга как волна — пройдёт сама за 3-7 минут.",
    "🚪 Встань и выйди в другую комнату. Смена контекста разрывает нейронную связь.",
    "🍋 Кусочек лимона или имбиря в рот — резкий вкус перебивает сигнал.",
    "✊ Сожми кулаки 10 сек → отпусти. 5 раз.",
    "💧 Умой лицо ледяной водой 30 сек.",
    "📝 Напиши 3 причины, почему сейчас не надо.",
    "💪 20 отжиманий до отказа — переключи тело.",
]

RECOVERY_STAGES = [
    "📅 ДНИ 1-3: ОСТРАЯ ФАЗА\n\nПик физических симптомов. Рецепторы требуют привычный дофамин.\n• Тревога, бессонница, сильная тяга каждые 1-2 часа.",
    "📅 ДНИ 4-7: ПОДОСТРАЯ ФАЗА\n\nСимптомы снижаются. Могут быть эмоциональные качели.",
    "📅 ДНИ 8-14: АДАПТАЦИЯ\n\nСон налаживается, тяга уменьшается, ясность мыслей возвращается.",
    "📅 ДНИ 15-28: ВОССТАНОВЛЕНИЕ\n\nЭнергия стабильна. Радость от простых вещей возвращается.",
    "📅 ДНИ 29-90: СТАБИЛИЗАЦИЯ\n\nПолная перезагрузка нейронных связей. Жизнь без зависимости."
]

TRIGGERS_INFO = [
    "⚠️ МЫСЛЬ «ХОЧУ»: просто наблюдай за мыслью как за облаком — она пройдет через 3-7 минут.",
    "⚠️ СИЛЬНАЯ ЭМОЦИЯ: назови эмоцию вслух — 'Это злость' и дыши 4-7-8.",
    "⚠️ СКУКА: займись любой активностью 10 минут — прогулка, зарядка.",
    "⚠️ КОМПАНИЯ/ОКРУЖЕНИЕ: избегай старой компании первые 30 дней."
]

COGNITIVE_DISTORTIONS = [
    "🤯 «Я ВСЁ ИСПОРТИЛ» — катастрофизация. Один срыв ≠ конец пути.",
    "🤯 «НИЧЕГО НЕ РАБОТАЕТ» — черно-белое мышление. Маленький прогресс — прогресс.",
    "🤯 «Я СЛАБЫЙ» — персонализация. Это химия, не характеристика личности."
]

SCIENCE_FACTS = [
    "🔬 CB1-РЕЦЕПТОРЫ: восстанавливаются постепенно — заметные улучшения через 2-4 недели.",
    "🔬 ДОФАМИН: режим восстановления — 2-3 недели заметного улучшения, 2-3 месяца значимой разницы.",
    "🔬 СОН: REM-фаза восстанавливается примерно за 3 недели."
]

TU_TUT_FIRST = ["Тут.", "Привет.", "Здесь.", "Тут, как всегда."]
TU_TUT_SECOND = ["Держимся.", "Я с тобой.", "Всё по плану.", "Не хочу сегодня."]

# ======= STORAGE =======
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
        except Exception as e:
            logger.warning("Файл данных повреждён или отсутствует, создаём новый: %s", e)
            _user_data_cache = {}
            return _user_data_cache

async def save_data():
    global _user_data_cache
    if _user_data_cache is None:
        return
    async with _data_lock:
        with FileLock(LOCK_FILE):
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(_user_data_cache, f, ensure_ascii=False, indent=2)

def get_user(uid):
    data = load_data()
    key = str(uid)
    if key not in data:
        data[key] = {
            "start_date": None,
            "active": False,
            "best_streak": 0,
            "hold_count_today": 0,
            "last_hold_time": None,
            "last_stage_index": 0,
            "used_tips": [],
            "used_triggers": [],
            "used_distortions": [],
            "used_facts": [],
            "heavy_count": 0,   # для персонализации
            "challenge_in_progress": False
        }
        asyncio.create_task(save_data())
    return data[key]

async def save_user(uid, updates=None):
    data = load_data()
    key = str(uid)
    if updates:
        if key not in data:
            data[key] = {}
        data[key].update(updates)
    await save_data()

def get_current_time():
    return datetime.now(MOSCOW_TZ)

def get_current_date():
    return get_current_time().date()

def get_days_since_start(uid):
    user = get_user(uid)
    if not user["start_date"]:
        return 0
    try:
        start = date.fromisoformat(user["start_date"])
        days = (get_current_date() - start).days
        return max(days, 0)
    except Exception:
        return 0

def format_days(n):
    if 11 <= n % 100 <= 19:
        return f"{n} дней"
    if n % 10 == 1:
        return f"{n} день"
    if n % 10 in [2,3,4]:
        return f"{n} дня"
    return f"{n} дней"

# ======= KEYBOARDS (fixed visual width via spacing) =======
# We can't control exact pixel width; we make labels concise and consistent.
def main_keyboard():
    kb = [
        [InlineKeyboardButton("✊ Держусь", callback_data="hold"),
         InlineKeyboardButton("😔 Тяжело", callback_data="heavy")],
        [InlineKeyboardButton("👋 Ты тут?", callback_data="here"),
         InlineKeyboardButton("📊 Дни", callback_data="days")],
        [InlineKeyboardButton("❤️ Спасибо", callback_data="thank"),
         InlineKeyboardButton("⏸ Помолчи", callback_data="stop")]
    ]
    return InlineKeyboardMarkup(kb)

def heavy_keyboard():
    kb = [
        [InlineKeyboardButton("🔥 Сделать упражнение", callback_data="exercise"),
         InlineKeyboardButton("🧠 Информация", callback_data="info")],
        [InlineKeyboardButton("💔 Срыв", callback_data="breakdown"),
         InlineKeyboardButton("↩ Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(kb)

def info_keyboard():
    kb = [
        [InlineKeyboardButton("📅 Стадии", callback_data="stages"),
         InlineKeyboardButton("⚠️ Триггеры", callback_data="triggers")],
        [InlineKeyboardButton("🤯 Искажения", callback_data="distortions"),
         InlineKeyboardButton("🔬 Факты", callback_data="facts")],
        [InlineKeyboardButton("↩ Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(kb)

def challenge_keyboard():
    kb = [
        [InlineKeyboardButton("▶ 30 сек челлендж", callback_data="challenge_30"),
         InlineKeyboardButton("▶ 60 сек челлендж", callback_data="challenge_60")],
        [InlineKeyboardButton("↩ Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(kb)

# ======= HELPERS (Typing simulation + Countdown) =======
async def simulate_typing_edit(bot, chat_id, message_id, full_text, steps=6, delay_total=0.9):
    """
    Симуляция «набора»: постепенно редактируем message до full_text.
    steps — количество шагов, delay_total — общее время.
    """
    if steps < 2:
        await bot.edit_message_text(full_text, chat_id, message_id)
        return
    base = ""  # start from empty or "..."
    per = max(1, len(full_text) // steps)
    t_sleep = delay_total / steps
    for i in range(1, steps+1):
        chunk = full_text[: min(len(full_text), i*per) ]
        try:
            await bot.edit_message_text(chunk, chat_id, message_id, parse_mode=ParseMode.HTML)
        except Exception:
            # иногда редактирование может падать, просто continue
            pass
        await asyncio.sleep(t_sleep)
    try:
        await bot.edit_message_text(full_text, chat_id, message_id, parse_mode=ParseMode.HTML)
    except Exception:
        pass

async def countdown_edit(bot, chat_id, message_id, seconds, prefix="Отсчёт"):
    """
    Обновляет одно и то же сообщение каждую секунду с обратным отсчётом.
    """
    try:
        for rem in range(seconds, 0, -1):
            txt = f"{prefix}: {rem} сек."
            await bot.edit_message_text(txt, chat_id, message_id)
            await asyncio.sleep(1)
        await bot.edit_message_text(f"✅ Готово! {prefix} завершён.", chat_id, message_id)
    except Exception as e:
        logger.debug("countdown_edit error: %s", e)

# ======= ITEMS SELECTION (rotate without repeats) =======
def get_next_item(uid, list_items, key_name):
    user = get_user(uid)
    used = user.get(key_name, [])
    if len(used) >= len(list_items):
        used = []
    available = [i for i in range(len(list_items)) if i not in used]
    if not available:
        available = list(range(len(list_items)))
        used = []
    choice = random.choice(available)
    used.append(choice)
    # fire-and-forget save
    asyncio.create_task(save_user(uid, {key_name: used}))
    return list_items[choice]

def get_next_exercise(uid):
    return get_next_item(uid, HELP_TECHNIQUES, "used_tips")

def get_next_stage(uid):
    user = get_user(uid)
    idx = user.get("last_stage_index", 0)
    text = RECOVERY_STAGES[idx]
    next_idx = (idx + 1) % len(RECOVERY_STAGES)
    asyncio.create_task(save_user(uid, {"last_stage_index": next_idx}))
    return text

# ======= PUSH SCHEDULE (job_queue) =======
def schedule_jobs_for_user(chat_id, job_queue):
    # remove existing first
    for name in [f"morning_{chat_id}", f"afternoon_{chat_id}", f"evening_{chat_id}"]:
        for j in job_queue.get_jobs_by_name(name):
            j.schedule_removal()

    job_queue.run_daily(send_push, time(9, 0, tzinfo=MOSCOW_TZ), data={'chat_id': chat_id}, name=f"morning_{chat_id}")
    job_queue.run_daily(send_push, time(15, 0, tzinfo=MOSCOW_TZ), data={'chat_id': chat_id}, name=f"afternoon_{chat_id}")
    job_queue.run_daily(send_push, time(21, 0, tzinfo=MOSCOW_TZ), data={'chat_id': chat_id}, name=f"evening_{chat_id}")

async def send_push(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data['chat_id']
    user = get_user(chat_id)
    if not user.get("active", False):
        return
    # choose message depending on time of day
    now = get_current_time()
    hour = now.hour
    if 6 <= hour < 12:
        msg = random.choice(MORNING_MESSAGES)
    elif 12 <= hour < 18:
        msg = random.choice(EVENING_MESSAGES)
    else:
        msg = random.choice(NIGHT_MESSAGES)
    days = get_days_since_start(chat_id)
    if days in MILESTONES:
        msg += f"\n\n{MILESTONES[days]}"
    try:
        await context.bot.send_message(chat_id, msg, reply_markup=main_keyboard())
    except Exception as e:
        logger.warning("send_push error: %s", e)

# ======= COMMANDS & CALLBACKS =======
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    was_active = user.get("active", False)
    await save_user(chat_id, {"active": True, "start_date": get_current_date().isoformat()})
    # schedule jobs once when user activates
    if not was_active:
        schedule_jobs_for_user(chat_id, context.application.job_queue)
    days = get_days_since_start(chat_id)
    greet = f"Привет! Ты держишься {format_days(days)}. Я буду рядом — три пуша в день."
    await update.message.reply_text(greet, reply_markup=main_keyboard())

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await save_user(chat_id, {"active": False})
    # remove jobs
    removed = 0
    for name in [f"morning_{chat_id}", f"afternoon_{chat_id}", f"evening_{chat_id}"]:
        for j in context.application.job_queue.get_jobs_by_name(name):
            j.schedule_removal()
            removed += 1
    await update.message.reply_text("Оповещения остановлены. Нажми /start чтобы снова включить.", reply_markup=None)
    logger.info("Removed %d jobs for %s", removed, chat_id)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # сразу подтвердим
    uid = query.from_user.id
    data = query.data

    # --- START from inline (if we used start button message with inline) ---
    if data == "start_inline":
        await save_user(uid, {"active": True, "start_date": get_current_date().isoformat()})
        schedule_jobs_for_user(uid, context.application.job_queue)
        days = get_days_since_start(uid)
        await query.edit_message_text(f"Привет! Ты держишься {format_days(days)}.", reply_markup=main_keyboard())
        return

    # --- STOP inline ---
    if data == "stop":
        await save_user(uid, {"active": False})
        # remove jobs
        for name in [f"morning_{uid}", f"afternoon_{uid}", f"evening_{uid}"]:
            for j in context.application.job_queue.get_jobs_by_name(name):
                j.schedule_removal()
        await query.edit_message_text("Оповещения остановлены. Нажми /start чтобы снова включить.", reply_markup=None)
        return

    # --- HOLD (with timeout & limit) ---
    if data == "hold":
        user = get_user(uid)
        today = get_current_date().isoformat()
        if user.get("last_hold_date") != today:
            # reset daily counter
            user["hold_count_today"] = 0
        # check last_hold_time for 30-min timeout
        last_time = user.get("last_hold_time")
        if last_time:
            try:
                last_dt = datetime.fromisoformat(last_time)
                last_dt = MOSCOW_TZ.localize(last_dt.replace(tzinfo=None)) if last_dt.tzinfo is None else last_dt
                diff = (get_current_time() - last_dt).total_seconds()
                if diff < 1800:
                    mins = int((1800 - diff) // 60) + 1
                    await query.edit_message_text(f"Подожди ещё {mins} {'минуту' if mins==1 else 'минут'}, прежде чем нажимать снова.", reply_markup=main_keyboard())
                    return
            except Exception:
                pass
        if user.get("hold_count_today", 0) >= 5:
            await query.edit_message_text("Сегодня уже 5 раз. Завтра снова сможешь.", reply_markup=main_keyboard())
            return
        user["hold_count_today"] = user.get("hold_count_today", 0) + 1
        user["last_hold_date"] = today
        user["last_hold_time"] = get_current_time().isoformat()
        await save_user(uid, user)
        await query.edit_message_text(random.choice(HOLD_RESPONSES), reply_markup=main_keyboard())

        # Notify other active users with a short emoji (light fan-out)
        active = [int(u) for u, v in load_data().items() if v.get("active", False)]
        for other in active:
            if other == uid: continue
            try:
                await context.bot.send_message(other, "✊")
                await asyncio.sleep(0.02)
            except Exception as e:
                # deactivate if blocked
                err = str(e).lower()
                if "blocked" in err or "forbidden" in err or "chat not found" in err:
                    await save_user(other, {"active": False})
                    for name in [f"morning_{other}", f"afternoon_{other}", f"evening_{other}"]:
                        for j in context.application.job_queue.get_jobs_by_name(name):
                            j.schedule_removal()
        return

    # --- HEAVY / INFO / EXERCISE flow ---
    if data == "heavy":
        # increment heavy_count for personalization
        user = get_user(uid)
        user["heavy_count"] = user.get("heavy_count", 0) + 1
        await save_user(uid, user)
        await query.edit_message_text("Тяжело? Выбирай:", reply_markup=heavy_keyboard())
        return

    if data == "exercise":
        ex = get_next_exercise(uid)
        # simulate typing into the same message
        # first show placeholder
        msg = await query.edit_message_text("Готовлю технику...", reply_markup=heavy_keyboard())
        try:
            await simulate_typing_edit(context.bot, query.message.chat_id, query.message.message_id, f"💡 Техника:\n\n{ex}", steps=6, delay_total=0.9)
        except Exception:
            pass
        return

    if data == "info":
        await query.edit_message_text("Выбери раздел информации:", reply_markup=info_keyboard())
        return

    # Info submenu
    if data == "stages":
        stage = get_next_stage(uid)
        await query.edit_message_text(stage, reply_markup=info_keyboard())
        return

    if data == "triggers":
        t = get_next_item(uid, TRIGGERS_INFO, "used_triggers")
        await query.edit_message_text(t, reply_markup=info_keyboard())
        return

    if data == "distortions":
        d = get_next_item(uid, COGNITIVE_DISTORTIONS, "used_distortions")
        await query.edit_message_text(d, reply_markup=info_keyboard())
        return

    if data == "facts":
        f = get_next_item(uid, SCIENCE_FACTS, "used_facts")
        await query.edit_message_text(f, reply_markup=info_keyboard())
        return

    if data == "back":
        await query.edit_message_text("Окей, возвращаемся:", reply_markup=main_keyboard())
        return

    if data == "breakdown":
        prev = await reset_streak(uid)
        await query.edit_message_text(f"Счётчик сброшен. Ты продержался {format_days(prev)}.\nКогда будешь готов — нажми /start", reply_markup=None)
        return

    if data == "days":
        days = get_days_since_start(uid)
        best = get_user(uid).get("best_streak", 0)
        txt = f"Ты держишься {format_days(days)}."
        if best and best > days:
            txt += f"\n\nЛучший результат: {format_days(best)}"
        elif best and best == days:
            txt += f"\n\nЭто твой лучший результат прямо сейчас!"
        # if milestone exists:
        if days in MILESTONES:
            txt += f"\n\n{MILESTONES[days]}"
        await query.edit_message_text(txt, reply_markup=main_keyboard())
        return

    # realistic "You here?" with typing animation
    if data == "here":
        # first edit to '...'
        try:
            await query.edit_message_text("...", reply_markup=main_keyboard())
        except Exception:
            pass
        # variable human-like delay
        await asyncio.sleep(random.uniform(1.5, 3.5))
        first = random.choice(TU_TUT_FIRST)
        second = random.choice(TU_TUT_SECOND)
        # simulate a two-line typing (fast)
        try:
            await simulate_typing_edit(context.bot, query.message.chat_id, query.message.message_id, f"{first}\n{second}", steps=4, delay_total=0.8)
        except Exception:
            # fallback
            await query.edit_message_text(f"{first}\n{second}", reply_markup=main_keyboard())
        return

    if data == "thank":
        await query.edit_message_text("Спасибо тебе, что ты есть. ❤️", reply_markup=main_keyboard())
        return

    # Challenges (micro-games)
    if data and data.startswith("challenge_"):
        # format: challenge_30 or challenge_60
        try:
            seconds = int(data.split("_")[1])
        except Exception:
            seconds = 30
        user = get_user(uid)
        if user.get("challenge_in_progress"):
            await query.edit_message_text("У тебя уже идёт челлендж. Дождись окончания.", reply_markup=challenge_keyboard())
            return
        # mark in progress
        await save_user(uid, {"challenge_in_progress": True})
        # initial edit
        await query.edit_message_text(f"Челлендж: {seconds} сек. Начинаю...", reply_markup=None)
        # run countdown inside same message
        await countdown_edit(context.bot, query.message.chat_id, query.message.message_id, seconds, prefix="Челлендж")
        # finish: award message and clear flag
        await save_user(uid, {"challenge_in_progress": False})
        await context.bot.send_message(uid, "🔥 Отлично! Ты справился с челленджем.", reply_markup=main_keyboard())
        return

# ======= BOOT (restore jobs on start) =======
async def restore_jobs(application):
    data = load_data()
    logger.info("Восстанавливаем задачи для %d пользователей", len(data))
    for uid, user in data.items():
        if user.get("active", False):
            try:
                schedule_jobs_for_user(int(uid), application.job_queue)
            except Exception as e:
                logger.debug("restore_jobs: %s", e)

# ======= MAIN =======
def main():
    app = Application.builder().token(TOKEN).build()

    # commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))

    # single callback handler
    app.add_handler(CallbackQueryHandler(callback_handler))

    # restore scheduled jobs after application init
    app.post_init = restore_jobs

    logger.info("Бот запущен")
    app.run_polling(allowed_updates=None)

if __name__ == "__main__":
    main()
