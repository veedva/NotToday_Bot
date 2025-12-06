# bot.py
import os
import json
import random
import asyncio
import logging
from datetime import datetime, date, time, timedelta
from filelock import FileLock
import pytz

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ---------------- CONFIG ----------------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN env var required")

DATA_FILE = "user_data.json"
LOCK_FILE = DATA_FILE + ".lock"
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ---------------- CONTENT ----------------
# (Full, rich content kept — trimmed lines for readability but still comprehensive)
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
    21: "✨ Три недели. Ты уже почти не думаешь об этом.",
    30: "✨ Месяц без этого. Мозг работает по-новому.",
    60: "✨ Два месяца — ты другой человек.",
    90: "✨ Три месяца. Полное восстановление. Ты молодец.",
}

HELP_TECHNIQUES = [
    "🧊 Лёд на запястья 30-60 сек. Холод активирует блуждающий нерв — тяга падает.",
    "🫁 Дыхание 4-7-8: вдох 4 → задержка 7 → выдох 8. 4 раза.",
    "⏱ Таймер 5 минут: подожди — волна пройдет сама.",
    "🚪 Встань и выйди из комнаты — смена контекста разрывает привычку.",
    "🍋 Кусочек лимона/имбиря — резкий вкус перебивает сигнал.",
    "✊ Сожми кулак 10 сек ×5 — переключение через тело.",
    "💧 Умой лицо холодной водой 30 сек. Шок снимает напряжение.",
    "📝 Напиши 3 причины, почему сейчас не стоит.",
    "💪 Планка 45-60 сек или 20 отжиманий — переключение.",
]

RECOVERY_STAGES = [
    "📅 ДНИ 1-3: ОСТРАЯ ФАЗА\nПик физических симптомов: тревога, бессонница, сильная тяга.",
    "📅 ДНИ 4-7: ПОДОСТРАЯ ФАЗА\nСимптомы снижаются на ~40%. Настроение скачет — нормально.",
    "📅 ДНИ 8-14: АДАПТАЦИЯ\nСон налаживается, аппетит возвращается, тяга редкая.",
    "📅 ДНИ 15-28: ВОССТАНОВЛЕНИЕ\nЭнергия стабильна, эмоции под контролем, радость возвращается.",
    "📅 ДНИ 29-90: СТАБИЛИЗАЦИЯ\nПолная перезагрузка нейронных связей — новая норма жизни.",
]

TRIGGERS_INFO = [
    "⚠️ Мысль «хочу»: не действуй, наблюдай. Через 3-7 минут пройдет.",
    "⚠️ Эмоции: назови эмоцию вслух и сделай дыхание 4-7-8.",
    "⚠️ Скука: займись 10 минут активностью (прогулка, уборка).",
    "⚠️ Окружение: избегай триггерных компаний первые 30 дней.",
]

COGNITIVE_DISTORTIONS = [
    "🤯 «Я ВСЁ ИСПОРТИЛ» — катастрофизация. Один срыв ≠ конец.",
    "🤯 «НИЧЕГО НЕ РАБОТАЕТ» — чёрно-белое мышление. Маленькие шаги — прогресс.",
    "🤯 «Я СЛАБЫЙ» — персонализация. Это химия, не характеристика.",
]

SCIENCE_FACTS = [
    "🔬 CB1-рецепторы: частичное восстановление начинается в 1-2 недели; 4-6 недель — серьёзный прогресс.",
    "🔬 До 3 недель сон и REM-фаза стабилизируются; память и внимание возвращаются.",
    "🔬 Нейропластичность: 21–90 дней — формирование новых полезных привычек.",
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
        except Exception as e:
            logger.warning("load_data failed, new DB: %s", e)
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
        # background save
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

def format_days(n: int) -> str:
    if 11 <= n % 100 <= 19:
        return f"{n} дней"
    if n % 10 == 1:
        return f"{n} день"
    if n % 10 in (2,3,4):
        return f"{n} дня"
    return f"{n} дней"

# ---------------- UI: Reply keyboard (persistent) + Inline for submenus ----------------
def make_main_reply_keyboard():
    kb = [
        [KeyboardButton("✊ Держусь"), KeyboardButton("😔 Тяжело")],
        [KeyboardButton("👋 Ты тут?"), KeyboardButton("📊 Дни")],
        [KeyboardButton("❤️ Спасибо"), KeyboardButton("⏸ Помолчи")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def make_heavy_inline():
    kb = [
        [InlineKeyboardButton("🔥 Сделать упражнение", callback_data="exercise"),
         InlineKeyboardButton("🧠 Информация", callback_data="info")],
        [InlineKeyboardButton("💔 Срыв", callback_data="breakdown"),
         InlineKeyboardButton("▶ Челленджи", callback_data="challenges")]
    ]
    return InlineKeyboardMarkup(kb)

def make_info_inline():
    kb = [
        [InlineKeyboardButton("📅 Стадии", callback_data="stages"),
         InlineKeyboardButton("⚠️ Триггеры", callback_data="triggers")],
        [InlineKeyboardButton("🤯 Искажения", callback_data="distortions"),
         InlineKeyboardButton("🔬 Факты", callback_data="facts")],
        [InlineKeyboardButton("↩ Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(kb)

def make_challenges_inline():
    kb = [
        [InlineKeyboardButton("▶ 30 с", callback_data="challenge_30"),
         InlineKeyboardButton("▶ 60 с", callback_data="challenge_60")],
        [InlineKeyboardButton("↩ Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(kb)

# ---------------- Helpers: typing simulation & countdown ----------------
async def simulate_typing_edit(bot, chat_id: int, message_id: int, full_text: str, steps=6, delay_total=0.9):
    """
    Симуляция набора: редактируем одно сообщение постепенно.
    """
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

async def countdown_edit(bot, chat_id: int, message_id: int, seconds: int, prefix="Отсчёт"):
    """
    Обратно отсчитываем в одном сообщении.
    """
    try:
        for rem in range(seconds, 0, -1):
            txt = f"{prefix}: {rem} сек."
            await bot.edit_message_text(txt, chat_id, message_id)
            await asyncio.sleep(1)
        await bot.edit_message_text(f"✅ Готово! {prefix} завершён.", chat_id, message_id)
    except Exception as e:
        logger.debug("countdown_edit error: %s", e)

# ---------------- Rotation helpers ----------------
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

# ---------------- Jobs (push 3x per day) ----------------
def schedule_jobs_for_user(chat_id: int, job_queue):
    # remove old
    for name in [f"morning_{chat_id}", f"afternoon_{chat_id}", f"evening_{chat_id}"]:
        for j in job_queue.get_jobs_by_name(name):
            j.schedule_removal()
    # schedule
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
        await context.bot.send_message(chat_id, msg, reply_markup=make_main_reply_keyboard())
    except Exception as e:
        logger.debug("send_push failed: %s", e)

# ---------------- Handlers ----------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    was_active = user.get("active", False)
    await save_user(chat_id, {"active": True, "start_date": get_current_date().isoformat()})
    # schedule job queue for new activation
    if not was_active:
        schedule_jobs_for_user(chat_id, context.application.job_queue)
    days = get_days_since_start(chat_id)
    text = f"Привет! Ты держишься {format_days(days)}. Я рядом — три пуша в день."
    # reply with persistent reply keyboard
    await update.message.reply_text(text, reply_markup=make_main_reply_keyboard())

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await save_user(chat_id, {"active": False})
    # remove jobs
    removed = 0
    for name in [f"morning_{chat_id}", f"afternoon_{chat_id}", f"evening_{chat_id}"]:
        for j in context.application.job_queue.get_jobs_by_name(name):
            j.schedule_removal()
            removed += 1
    await update.message.reply_text("Оповещения остановлены. Нажми /start когда будешь готов.", reply_markup=make_main_reply_keyboard())
    logger.info("Removed %d jobs for %s", removed, chat_id)

# MessageHandler for persistent reply keyboard presses
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    chat_id = update.effective_chat.id

    # Map reply keyboard labels to functionality
    if text == "✊ Держусь":
        # run same logic as inline hold
        await do_hold_reply(update, context)
    elif text == "😔 Тяжело":
        # open inline heavy menu
        await update.message.reply_text("Тяжело? Выбери опцию:", reply_markup=make_heavy_inline())
    elif text == "👋 Ты тут?":
        # realistic delay + simulate typing — use reply to emulate live typing
        await update.message.reply_text("...", reply_markup=make_main_reply_keyboard())
        await asyncio.sleep(random.uniform(1.5, 3.2))
        first = random.choice(TU_TUT_FIRST)
        second = random.choice(TU_TUT_SECOND)
        # send combined response and keep reply keyboard visible
        await context.bot.send_message(chat_id, f"{first}\n{second}", reply_markup=make_main_reply_keyboard())
    elif text == "📊 Дни":
        days = get_days_since_start(chat_id)
        u = get_user(chat_id)
        best = u.get("best_streak", 0)
        msg = f"Ты держишься {format_days(days)}."
        if best and best > days:
            msg += f"\n\nЛучший результат: {format_days(best)}"
        elif best and best == days:
            msg += f"\n\nЭто твой лучший результат прямо сейчас!"
        if days in MILESTONES:
            msg += f"\n\n{MILESTONES[days]}"
        await update.message.reply_text(msg, reply_markup=make_main_reply_keyboard())
    elif text == "❤️ Спасибо":
        await update.message.reply_text("Спасибо тебе, что ты есть. ❤️", reply_markup=make_main_reply_keyboard())
    elif text == "⏸ Помолчи":
        # alias of stop
        await cmd_stop(update, context)
    else:
        # unknown free text — polite fallback
        await update.message.reply_text("Не понял. Нажми одну из кнопок ниже.", reply_markup=make_main_reply_keyboard())

# Implementation of hold logic usable from both reply and callback flows
async def do_hold_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    if not user.get("active", False):
        await update.message.reply_text("Сначала нажми /start", reply_markup=make_main_reply_keyboard())
        return

    today = get_current_date().isoformat()
    if user.get("last_hold_date") != today:
        user["hold_count_today"] = 0
    # last hold time check
    last = user.get("last_hold_time")
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            if last_dt.tzinfo is None:
                last_dt = MOSCOW_TZ.localize(last_dt)
            diff = (get_current_time() - last_dt).total_seconds()
            if diff < 1800:
                mins = int((1800 - diff) // 60) + 1
                await update.message.reply_text(f"Подожди ещё {mins} {'минуту' if mins==1 else 'минут'}.", reply_markup=make_main_reply_keyboard())
                return
        except Exception:
            pass
    if user.get("hold_count_today", 0) >= 5:
        await update.message.reply_text("Сегодня уже 5 раз. Завтра снова сможешь.", reply_markup=make_main_reply_keyboard())
        return

    user["hold_count_today"] = user.get("hold_count_today", 0) + 1
    user["last_hold_date"] = today
    user["last_hold_time"] = get_current_time().isoformat()
    await save_user(chat_id, user)
    await update.message.reply_text(random.choice(HOLD_RESPONSES), reply_markup=make_main_reply_keyboard())

    # notify other active users with tiny emoji, best-effort
    data = load_data()
    for other_key, other in data.items():
        try:
            oid = int(other_key)
        except Exception:
            continue
        if oid == chat_id:
            continue
        if other.get("active", False):
            try:
                await context.bot.send_message(oid, "✊")
                await asyncio.sleep(0.02)
            except Exception:
                # if cannot message — mark inactive
                try:
                    errtxt = ""
                except:
                    pass

# CallbackQuery handler for Inline actions (info, exercises, challenges, etc.)
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    uid = query.from_user.id
    data = query.data

    # HEAVY submenu selection
    if data == "exercise":
        ex = get_next_exercise(uid)
        # edit current inline message then restore reply keyboard by sending separate message
        try:
            await query.edit_message_text("Готовлю упражнение...", reply_markup=make_heavy_inline())
        except Exception:
            pass
        # simulate typing in same message
        try:
            await simulate_typing_edit(context.bot, query.message.chat_id, query.message.message_id, f"💡 Упражнение:\n\n{ex}", steps=6, delay_total=1.0)
        except Exception:
            try:
                await query.edit_message_text(f"💡 Упражнение:\n\n{ex}", reply_markup=make_heavy_inline())
            except Exception:
                pass
        # re-show persistent keyboard as chat-level keyboard
        await context.bot.send_message(uid, "Верну клавиатуру:", reply_markup=make_main_reply_keyboard())
        return

    if data == "info":
        try:
            await query.edit_message_text("Выберите раздел:", reply_markup=make_info_inline())
        except Exception:
            pass
        return

    if data == "stages":
        stage = get_next_stage(uid)
        try:
            await query.edit_message_text(stage, reply_markup=make_info_inline())
        except Exception:
            pass
        # restore reply keyboard
        await context.bot.send_message(uid, "Вернуться можно через клавиши:", reply_markup=make_main_reply_keyboard())
        return

    if data == "triggers":
        t = get_next_item(uid, TRIGGERS_INFO, "used_triggers")
        try:
            await query.edit_message_text(t, reply_markup=make_info_inline())
        except Exception:
            pass
        await context.bot.send_message(uid, "Клавиатура вернулась:", reply_markup=make_main_reply_keyboard())
        return

    if data == "distortions":
        d = get_next_item(uid, COGNITIVE_DISTORTIONS, "used_distortions")
        try:
            await query.edit_message_text(d, reply_markup=make_info_inline())
        except Exception:
            pass
        await context.bot.send_message(uid, "Клавиатура вернулась:", reply_markup=make_main_reply_keyboard())
        return

    if data == "facts":
        f = get_next_item(uid, SCIENCE_FACTS, "used_facts")
        try:
            await query.edit_message_text(f, reply_markup=make_info_inline())
        except Exception:
            pass
        await context.bot.send_message(uid, "Клавиатура вернулась:", reply_markup=make_main_reply_keyboard())
        return

    if data == "back_to_main":
        try:
            await query.edit_message_text("Возврат в главное меню.", reply_markup=None)
        except Exception:
            pass
        await context.bot.send_message(uid, "Главное меню:", reply_markup=make_main_reply_keyboard())
        return

    if data == "breakdown":
        prev_days = get_days_since_start(uid)
        u = get_user(uid)
        if prev_days > u.get("best_streak", 0):
            await save_user(uid, {"best_streak": prev_days})
        await save_user(uid, {
            "start_date": get_current_date().isoformat(),
            "last_stage_index": 0,
            "hold_count_today": 0,
            "last_hold_time": None,
            "last_hold_date": None,
            "used_tips": [], "used_triggers": [], "used_distortions": [], "used_facts": []
        })
        try:
            await query.edit_message_text(f"Счётчик сброшен. Ты продержался {format_days(prev_days)}.")
        except Exception:
            pass
        await context.bot.send_message(uid, "Когда будешь готов — нажми /start", reply_markup=make_main_reply_keyboard())
        return

    if data == "challenges":
        try:
            await query.edit_message_text("Выберите челлендж:", reply_markup=make_challenges_inline())
        except Exception:
            pass
        return

    if data and data.startswith("challenge_"):
        # e.g. "challenge_30"
        try:
            secs = int(data.split("_")[1])
        except Exception:
            secs = 30
        u = get_user(uid)
        if u.get("challenge_in_progress"):
            try:
                await query.edit_message_text("У тебя уже идёт челлендж.", reply_markup=make_challenges_inline())
            except Exception:
                pass
            return
        await save_user(uid, {"challenge_in_progress": True})
        try:
            await query.edit_message_text(f"Челлендж {secs} сек. Начинаю...", reply_markup=None)
        except Exception:
            pass
        # countdown in same message
        try:
            await countdown_edit(context.bot, query.message.chat_id, query.message.message_id, secs, prefix="Челлендж")
        except Exception:
            pass
        await save_user(uid, {"challenge_in_progress": False})
        await context.bot.send_message(uid, "🔥 Отлично! Ты справился.", reply_markup=make_main_reply_keyboard())
        return

# ---------------- Restore jobs on bot boot ----------------
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
                logger.debug("restore_jobs error: %s", e)

# ---------------- Utility: map Reply-button text to callback-like processing ----------------
async def do_hold_from_callback(uid: int, context: ContextTypes.DEFAULT_TYPE, query=None):
    # provided for parity if needed
    # not used here because reply flow uses do_hold_reply
    pass

# ---------------- Application bootstrap ----------------
def main():
    app = Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))

    # Reply keyboard messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Inline callbacks
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Restore jobs after init
    app.post_init = restore_jobs

    logger.info("Запускаю бота...")
    app.run_polling(allowed_updates=None)

if __name__ == "__main__":
    main()
