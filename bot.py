# bot.py
import logging
import random
import json
import os
import asyncio
from datetime import datetime, date, time, timedelta
from filelock import FileLock
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
import pytz

# ---------------- CONFIG ----------------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

DATA_FILE = "user_data.json"
LOCK_FILE = DATA_FILE + ".lock"
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ---------------- CONTENT (kept rich) ----------------
MORNING_MESSAGES = [
    "Привет. Давай сегодня не будем, хорошо?",
    "Доброе утро. Не сегодня.",
    "Привет. Держимся сегодня?",
    "Доброе утро. Сегодня много дел, наверное нет.",
    "Привет. Сегодня обойдёмся без этого.",
]

EVENING_MESSAGES = [
    "Не сегодня. Держись.",
    "Я тут. Давай не сегодня.",
    "Привет. Сегодня держимся, помнишь?",
    "Держись. Сегодня нет.",
]

NIGHT_MESSAGES = [
    "Ты молодец. До завтра.",
    "Красавчик. Спокойной.",
    "Держался сегодня. Уважаю.",
    "Сегодня справились. До завтра.",
]

HOLD_RESPONSES = ["Отправлено. ✊", "Молодец. ✊", "Понял. ✊", "Так держать. ✊"]

MILESTONES = {
    3: "✨ Три дня уже. Самое тяжёлое позади.",
    7: "✨ Неделя. Рецепторы начинают восстанавливаться.",
    14: "✨ Две недели! Сон налаживается, голова яснее.",
    30: "✨ Месяц без этого. Мозг работает по-новому.",
    90: "✨ Три месяца. Полное восстановление. Ты молодец.",
}

HELP_TECHNIQUES = [
    "🧊 Лёд на запястья 30–60 с — резкая холодная стимуляция снижает тягу.",
    "🫁 Дыхание 4-7-8: вдох 4 → задержка 7 → выдох 8. Повтори 4 раза.",
    "⏱ Таймер 5 минут: подожди — волна тяги уйдёт сама.",
    "🚪 Смена окружения: встань и выйди из комнаты — разрушается ассоциация.",
    "🍋 Резкий вкус (лимон/имбирь) перебивает навязчивую мысль.",
    "✊ Сожми кулак 10 с ×5 — переключение через тело.",
    "💧 Умой лицо холодной водой 30 с — шоковый рефлекс снимает напряжение.",
    "📝 Напиши 3 причины, почему сейчас не стоит.",
    "💪 20 быстрых отжиманий — отвлечение и выброс энергии.",
]

RECOVERY_STAGES = [
    "📅 ДНИ 1–3: ОСТРАЯ ФАЗА\nПик симптомов: тревога, бессонница, сильная тяга.",
    "📅 ДНИ 4–7: ПОДОСТРАЯ ФАЗА\nСимптомы уменьшаются, настроение скачет.",
    "📅 ДНИ 8–14: АДАПТАЦИЯ\nСон и память улучшаются, тяга реже.",
    "📅 ДНИ 15–28: ВОССТАНОВЛЕНИЕ\nЭнергия восстанавливается, радость возвращается.",
    "📅 ДНИ 29–90: СТАБИЛИЗАЦИЯ\nНовая норма — меньше рецидивов, лучшее самочувствие.",
]

TRIGGERS_INFO = [
    "⚠️ Мысль «хочу» — просто наблюдай, подожди 3–7 минут.",
    "⚠️ Эмоции (злость, грусть) — назови эмоцию вслух, дыши.",
    "⚠️ Скука — займись 10 минут активностью (прогулка, звонок).",
    "⚠️ Окружение — избегай триггерной компании первые 30 дней.",
]

COGNITIVE_DISTORTIONS = [
    "🤯 «Я всё испортил» — катастрофизация. Один срыв ≠ провал на все времена.",
    "🤯 «Ничего не помогает» — чёрно-белое мышление. Маленькие изменения — тоже прогресс.",
    "🤯 «Я слабый» — персонализация. Это болезнь/состояние, не характеристика.",
]

SCIENCE_FACTS = [
    "🔬 CB1-рецепторы и дофамин: частичное восстановление начинается в первые 2–4 недели.",
    "🔬 Сон и память: REM-фаза восстанавливается за 2–3 недели после отказа.",
    "🔬 Нейропластичность: новые привычки формируются 21–90 дней.",
]

TU_TUT_FIRST = ["Тут.", "Привет.", "Здесь.", "Тут, как всегда."]
TU_TUT_SECOND = ["Держимся.", "Я с тобой.", "Всё по плану.", "Сегодня не буду."]

# ---------------- STORAGE ----------------
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
        except Exception:
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
            "last_hold_date": None,
            "last_stage_index": 0,
            "used_tips": [],
            "used_triggers": [],
            "used_distortions": [],
            "used_facts": [],
            "heavy_count": 0,
            "challenge_in_progress": False,
            "last_push_index": 0
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
    u = get_user(uid)
    if not u.get("start_date"):
        return 0
    try:
        start = date.fromisoformat(u["start_date"])
        return max((get_current_date() - start).days, 0)
    except Exception:
        return 0

def format_days(n):
    if 11 <= n % 100 <= 19:
        return f"{n} дней"
    if n % 10 == 1:
        return f"{n} день"
    if n % 10 in (2,3,4):
        return f"{n} дня"
    return f"{n} дней"

# ---------------- UI (fixed look) ----------------
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
        [InlineKeyboardButton("▶ 30 с", callback_data="challenge_30"),
         InlineKeyboardButton("▶ 60 с", callback_data="challenge_60")],
        [InlineKeyboardButton("↩ Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(kb)

# ---------------- Helpers: typing simulation & countdown ----------------
async def simulate_typing_edit(bot, chat_id, message_id, full_text, steps=6, delay_total=0.9):
    if steps < 2:
        try:
            await bot.edit_message_text(full_text, chat_id, message_id, parse_mode=ParseMode.HTML)
        except Exception:
            pass
        return
    per = max(1, len(full_text) // steps)
    t_sleep = delay_total / steps
    for i in range(1, steps + 1):
        chunk = full_text[: min(len(full_text), i * per)]
        try:
            await bot.edit_message_text(chunk, chat_id, message_id, parse_mode=ParseMode.HTML)
        except Exception:
            pass
        await asyncio.sleep(t_sleep)
    try:
        await bot.edit_message_text(full_text, chat_id, message_id, parse_mode=ParseMode.HTML)
    except Exception:
        pass

async def countdown_edit(bot, chat_id, message_id, seconds, prefix="Отсчёт"):
    try:
        for rem in range(seconds, 0, -1):
            txt = f"{prefix}: {rem} сек."
            await bot.edit_message_text(txt, chat_id, message_id)
            await asyncio.sleep(1)
        await bot.edit_message_text(f"✅ Готово! {prefix} завершён.", chat_id, message_id)
    except Exception as e:
        logger.debug("countdown_edit err: %s", e)

# ---------------- Item rotation (no immediate repeats) ----------------
def get_next_item(uid, items, key):
    user = get_user(uid)
    used = user.get(key, [])
    if len(used) >= len(items):
        used = []
    available = [i for i in range(len(items)) if i not in used]
    if not available:
        available = list(range(len(items)))
        used = []
    choice = random.choice(available)
    used.append(choice)
    asyncio.create_task(save_user(uid, {key: used}))
    return items[choice]

def get_next_exercise(uid):
    return get_next_item(uid, HELP_TECHNIQUES, "used_tips")

def get_next_stage(uid):
    user = get_user(uid)
    idx = user.get("last_stage_index", 0)
    text = RECOVERY_STAGES[idx]
    next_idx = (idx + 1) % len(RECOVERY_STAGES)
    asyncio.create_task(save_user(uid, {"last_stage_index": next_idx}))
    return text

# ---------------- Jobs: push notifications ----------------
def schedule_jobs_for_user(chat_id, job_queue):
    # remove existing if any
    for name in [f"morning_{chat_id}", f"afternoon_{chat_id}", f"evening_{chat_id}"]:
        for j in job_queue.get_jobs_by_name(name):
            j.schedule_removal()
    # schedule three pushes
    job_queue.run_daily(send_push, time(9, 0, tzinfo=MOSCOW_TZ), data={"chat_id": chat_id}, name=f"morning_{chat_id}")
    job_queue.run_daily(send_push, time(15, 0, tzinfo=MOSCOW_TZ), data={"chat_id": chat_id}, name=f"afternoon_{chat_id}")
    job_queue.run_daily(send_push, time(21, 0, tzinfo=MOSCOW_TZ), data={"chat_id": chat_id}, name=f"evening_{chat_id}")

async def send_push(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    user = get_user(chat_id)
    if not user.get("active", False):
        return
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
        logger.debug("send_push error: %s", e)

# ---------------- Commands & Callbacks ----------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    was_active = user.get("active", False)
    await save_user(chat_id, {"active": True, "start_date": get_current_date().isoformat()})
    if not was_active:
        schedule_jobs_for_user(chat_id, context.application.job_queue)
    days = get_days_since_start(chat_id)
    txt = f"Привет! Ты держишься {format_days(days)}. Я буду рядом — три пуша в день."
    await update.message.reply_text(txt, reply_markup=main_keyboard())

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await save_user(chat_id, {"active": False})
    # remove jobs
    removed = 0
    for name in [f"morning_{chat_id}", f"afternoon_{chat_id}", f"evening_{chat_id}"]:
        for j in context.application.job_queue.get_jobs_by_name(name):
            j.schedule_removal()
            removed += 1
    await update.message.reply_text("Оповещения остановлены. Нажми /start чтобы включить снова.", reply_markup=None)
    logger.info("Removed %d jobs for %s", removed, chat_id)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    # START inline (if used)
    if data == "start_inline":
        await save_user(uid, {"active": True, "start_date": get_current_date().isoformat()})
        schedule_jobs_for_user(uid, context.application.job_queue)
        await query.edit_message_text("Хорошо, я включил пуши.", reply_markup=main_keyboard())
        return

    # STOP inline
    if data == "stop":
        await save_user(uid, {"active": False})
        for name in [f"morning_{uid}", f"afternoon_{uid}", f"evening_{uid}"]:
            for j in context.application.job_queue.get_jobs_by_name(name):
                j.schedule_removal()
        await query.edit_message_text("Оповещения остановлены. Нажми /start чтобы снова включить.", reply_markup=None)
        return

    # HOLD: timeout + daily limit
    if data == "hold":
        user = get_user(uid)
        today = get_current_date().isoformat()
        if user.get("last_hold_date") != today:
            user["hold_count_today"] = 0
        last_time = user.get("last_hold_time")
        if last_time:
            try:
                last_dt = datetime.fromisoformat(last_time)
                if last_dt.tzinfo is None:
                    last_dt = MOSCOW_TZ.localize(last_dt)
                diff = (get_current_time() - last_dt).total_seconds()
                if diff < 1800:
                    mins = int((1800 - diff) // 60) + 1
                    await query.edit_message_text(f"Подожди ещё {mins} {'минуту' if mins==1 else 'минут'}.", reply_markup=main_keyboard())
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

        # fan-out small emoji to other active users
        for other_str, other in load_data().items():
            try:
                other_id = int(other_str)
            except Exception:
                continue
            if other_id == uid:
                continue
            if other.get("active", False):
                try:
                    await context.bot.send_message(other_id, "✊")
                    await asyncio.sleep(0.02)
                except Exception as e:
                    err = str(e).lower()
                    if "forbidden" in err or "blocked" in err or "chat not found" in err:
                        await save_user(other_id, {"active": False})
        return

    # HEAVY -> submenu
    if data == "heavy":
        u = get_user(uid)
        u["heavy_count"] = u.get("heavy_count", 0) + 1
        await save_user(uid, u)
        await query.edit_message_text("Тяжело? Выбирай:", reply_markup=heavy_keyboard())
        return

    # EXERCISE -> simulated typing
    if data == "exercise":
        ex = get_next_exercise(uid)
        # initial placeholder
        try:
            await query.edit_message_text("Готовлю упражнение...", reply_markup=heavy_keyboard())
        except Exception:
            pass
        # simulate typing into same message
        try:
            await simulate_typing_edit(context.bot, query.message.chat_id, query.message.message_id, f"💡 Упражнение:\n\n{ex}", steps=6, delay_total=1.0)
        except Exception:
            try:
                await query.edit_message_text(f"💡 Упражнение:\n\n{ex}", reply_markup=heavy_keyboard())
            except Exception:
                pass
        return

    # INFO submenu
    if data == "info":
        await query.edit_message_text("Выберите раздел:", reply_markup=info_keyboard())
        return

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
        await query.edit_message_text("Возвращаемся в главное меню:", reply_markup=main_keyboard())
        return

    if data == "breakdown":
        prev = get_days_since_start(uid)
        # save best streak if any
        u = get_user(uid)
        if prev > u.get("best_streak", 0):
            await save_user(uid, {"best_streak": prev})
        await save_user(uid, {
            "start_date": get_current_date().isoformat(),
            "last_stage_index": 0,
            "hold_count_today": 0,
            "last_hold_time": None,
            "last_hold_date": None,
            "used_tips": [], "used_triggers": [], "used_distortions": [], "used_facts": []
        })
        await query.edit_message_text(f"Счётчик сброшен. Ты продержался {format_days(prev)}.\nКогда будешь готов — нажми /start", reply_markup=None)
        return

    if data == "days":
        days = get_days_since_start(uid)
        u = get_user(uid)
        best = u.get("best_streak", 0)
        txt = f"Ты держишься {format_days(days)}."
        if best and best > days:
            txt += f"\n\nЛучший результат: {format_days(best)}"
        elif best and best == days:
            txt += f"\n\nЭто твой лучший результат прямо сейчас!"
        if days in MILESTONES:
            txt += f"\n\n{MILESTONES[days]}"
        await query.edit_message_text(txt, reply_markup=main_keyboard())
        return

    # realistic "You here?" with animation
    if data == "here":
        try:
            await query.edit_message_text("...", reply_markup=main_keyboard())
        except Exception:
            pass
        await asyncio.sleep(random.uniform(1.5, 3.2))
        first = random.choice(TU_TUT_FIRST)
        second = random.choice(TU_TUT_SECOND)
        try:
            await simulate_typing_edit(context.bot, query.message.chat_id, query.message.message_id, f"{first}\n{second}", steps=4, delay_total=0.9)
        except Exception:
            try:
                await query.edit_message_text(f"{first}\n{second}", reply_markup=main_keyboard())
            except Exception:
                pass
        return

    if data == "thank":
        await query.edit_message_text("Спасибо тебе, что ты есть. ❤️", reply_markup=main_keyboard())
        return

    # challenge micro-games
    if data and data.startswith("challenge_"):
        try:
            seconds = int(data.split("_")[1])
        except Exception:
            seconds = 30
        u = get_user(uid)
        if u.get("challenge_in_progress"):
            await query.edit_message_text("У тебя уже идёт челлендж. Дождись окончания.", reply_markup=challenge_keyboard())
            return
        await save_user(uid, {"challenge_in_progress": True})
        await query.edit_message_text(f"Челлендж {seconds} сек. Начинаю...", reply_markup=None)
        await countdown_edit(context.bot, query.message.chat_id, query.message.message_id, seconds, prefix="Челлендж")
        await save_user(uid, {"challenge_in_progress": False})
        await context.bot.send_message(uid, "🔥 Отлично! Ты справился с челленджем.", reply_markup=main_keyboard())
        return

# ---------------- Restore scheduled jobs after start ----------------
async def restore_jobs(application):
    data = load_data()
    logger.info("Восстанавливаем задачи для %d пользователей", len(data))
    for uid_str, u in data.items():
        try:
            uid = int(uid_str)
        except Exception:
            continue
        if u.get("active", False):
            try:
                schedule_jobs_for_user(uid, application.job_queue)
            except Exception as e:
                logger.debug("restore_jobs: %s", e)

# ---------------- Main ----------------
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CallbackQueryHandler(callback_handler))

    app.post_init = restore_jobs

    logger.info("Запускаю бота")
    app.run_polling(allowed_updates=None)

if __name__ == "__main__":
    main()
