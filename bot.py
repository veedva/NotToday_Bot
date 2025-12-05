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
    "Доброе утро. Только не сегодня.",
    "Привет. Может завтра, но сегодня нет.",
    "Утро. Сегодня спокойно обходимся.",
    "Чё как? Сегодня не стоит пожалуй"
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
    3: "✨ Три дня. Уже круто.",
    7: "✨ Неделя. Прошёл самый тяжёлый период.",
    14: "✨ Две недели. Привыкаешь жить по-другому.",
    21: "✨ 21 день — новые нейронные связи. Ты уже другой.",
    30: "✨ Месяц. Уважаю, брат.",
    60: "✨ Два месяца. Ты свободен.",
    90: "✨ 90 дней — точка невозврата. Ты победил.",
    180: "✨ Полгода. Легенда.",
    365: "✨ ГОД. Ты сделал невозможное, брат ❤️"
}

TU_TUT_FIRST = ["Тут.", "Привет.", "А куда я денусь?", "Здесь.", "Тут, как всегда.", "Да, да.", "Чё как?", "Ага.", "Здравствуй.", "Тут, не переживай."]
TU_TUT_SECOND = ["Держимся.", "Я с тобой.", "Всё по плану.", "Не хочу сегодня.", "Сегодня не буду.", "Я рядом.", "Держись.", "Всё будет нормально.", "Я в деле.", "Под контролем."]

HOLD_RESPONSES = ["Отправлено. ✊", "Молодец. ✊", "Понял. ✊", "Так держать. ✊"]

HELP_TECHNIQUES = [
    "Встань и сделай 25–30 приседаний или отжиманий. Пока мышцы горят — голова молчит. Ты справишься.",
    "30 секунд ледяного душа или лицо под холодную воду. Шок — и тяга отступает. Проверено.",
    "Выйди на улицу. Хоть на балкон, хоть на 3 минуты. Свежий воздух — твой лучший друг сейчас.",
    "Техника 5-4-3-2-1: 5 вещей вижу → 4 слышу → 3 могу потрогать → 2 запаха → 1 вкус. Делай сейчас.",
    "Поставь таймер на 15 минут и скажи себе: «Я просто подожду». В 98 % случаев — через 15 минут уже не хочется.",
    "Съешь что-то острое или кислое до жжения: лимон, горчица, имбирь. Жжёт — мозг переключается.",
    "Дыши 4-7-8: вдох на 4 → задержка на 7 → выдох на 8. Четыре раза. Это выключает тревогу.",
    "Открой заметки и напиши: «Я не вернусь к этому дерьму. Никогда». Прочитай вслух.",
    "Планка 60–90 секунд. Пока держишь — ни одна мысль не пролезет. Ты сильнее, чем думаешь.",
    "Позвони любому человеку и просто скажи: «Привет, просто хотел услышать голос». Это уже победа."
]

HELP_ADVICE_BY_DAY = [
    "Дни 1–3: бессонница, тревога, всё бесит. Это нормально — мозг перестраивается. Перетерпи.",
    "Дни 4–7: физически легче, но в голове «а может разок». Это ложь. Ты уже прошёл ад.",
    "Дни 8–14: появляются нормальные сны и настроение. Ты начинаешь жить по-настоящему.",
    "Дни 15–30: мозг учится радоваться без вещества. Самое опасное время — не расслабиться.",
    "Дни 31–60: ты уже не «бросающий». Радость от обычных вещей. Держи курс.",
    "Дни 61–90: новые привычки закрепились. Ты другой человек.",
    "90+ дней: ты прошёл. Никогда не проверя «а вдруг я теперь могу». Это конец."
]

def get_keyboard(layout):
    return ReplyKeyboardMarkup(layout, resize_keyboard=True)

MAIN_KEYBOARD = get_keyboard([
    [KeyboardButton("✊ Держусь"), KeyboardButton("😔 Тяжело")],
    [KeyboardButton("📊 Дни"), KeyboardButton("👋 Ты тут?")],
    [KeyboardButton("❤️ Спасибо"), KeyboardButton("⏸ Помолчи")]
])

START_KEYBOARD = get_keyboard([[KeyboardButton("▶ Начать")]])

HEAVY_KEYBOARD = get_keyboard([
    [KeyboardButton("💪 Упражнения"), KeyboardButton("🧠 Что происходит с телом")],
    [KeyboardButton("😞 Срыв"), KeyboardButton("↩ Назад")]
])

EXERCISE_KEYBOARD = get_keyboard([[KeyboardButton("🔄 Другое упражнение")], [KeyboardButton("↩ Назад")]])

ADVICE_KEYBOARD = get_keyboard([[KeyboardButton("↩ Назад")]])

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
            "exercise_index": 0,
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
    return [int(uid) for uid, u in load_data().items() if u.get("active")]

def get_next_exercise(user_data):
    index = user_data.get("exercise_index", 0)
    exercise = HELP_TECHNIQUES[index]
    user_data["exercise_index"] = (index + 1) % len(HELP_TECHNIQUES)
    return exercise

def get_advice_for_day(days):
    if days <= 3: return HELP_ADVICE_BY_DAY[0]
    if days <= 7: return HELP_ADVICE_BY_DAY[1]
    if days <= 14: return HELP_ADVICE_BY_DAY[2]
    if days <= 30: return HELP_ADVICE_BY_DAY[3]
    if days <= 60: return HELP_ADVICE_BY_DAY[4]
    if days <= 90: return HELP_ADVICE_BY_DAY[5]
    return HELP_ADVICE_BY_DAY[6]

async def send(bot, chat_id, text, keyboard=None, save=True):
    kb = keyboard or MAIN_KEYBOARD
    msg = await bot.send_message(chat_id, text, reply_markup=kb)
    if save:
        data, _ = get_user(chat_id)
        data[str(chat_id)].setdefault("message_ids", []).append(msg.message_id)
        if len(data[str(chat_id)]["message_ids"]) > 300:
            data[str(chat_id)]["message_ids"] = data[str(chat_id)]["message_ids"][-300:]
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
    if not user.get("active"): return
    days = get_days(chat_id)
    text = MILESTONES.get(days, random.choice(MORNING_MESSAGES))
    await send(context.bot, chat_id, text)
    if days in MILESTONES:
        await send(context.bot, chat_id, MILESTONES[days])

async def evening_job(context, chat_id):
    _, user = get_user(chat_id)
    if not user.get("active"): return
    await send(context.bot, chat_id, random.choice(EVENING_MESSAGES))

async def night_job(context, chat_id):
    _, user = get_user(chat_id)
    if not user.get("active"): return
    await send(context.bot, chat_id, random.choice(NIGHT_MESSAGES))

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
            mins = int((1800 - delta) // 60) + 1
            if mins % 10 == 1 and mins % 100 != 11:
                word = "минуту"
            elif 2 <= mins % 10 <= 4 and mins % 100 not in [12,13,14]:
                word = "минуты"
            else:
                word = "минут"
            await send(context.bot, chat_id, f"Погоди ещё {mins} {word}, брат.", save=False)
            return

    if count_today >= 5:
        await send(context.bot, chat_id, "Сегодня уже 5 раз, брат\nЗавтра снова сможешь.", save=False)
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data, user = get_user(chat_id)
    user.update({
        "active": True,
        "start_date": NOW().isoformat(),
        "exercise_index": 0,
        "hold_count_today": 0,
        "last_hold_date": None,
        "last_hold_time": None
    })
    save_data(data)
    await send(context.bot, chat_id,
        "Привет, брат.\n\nЯ буду писать три раза в день, просто напомню: сегодня не надо.\n\nКогда тяжело — жми ✊ Держусь\nВсе получат пуш и узнают, что ты ещё здесь.\nМожешь жать до 5 раз в сутки.\n\nДержись. Я рядом.", save=False)
    schedule_jobs(chat_id, context.job_queue)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data, user = get_user(chat_id)
    user["active"] = False
    save_data(data)
    for prefix in ["m", "e", "n", "c"]:
        for job in context.job_queue.get_jobs_by_name(f"{prefix}_{chat_id}"):
            job.schedule_removal()
    await send(context.bot, chat_id, "Уведомления остановлены.\nКогда будешь готов — жми ▶ Начать", START_KEYBOARD, False)

def reset_streak(user_id):
    data, user = get_user(user_id)
    current = get_days(user_id)
    if current > user.get("best_streak", 0):
        user["best_streak"] = current
    user.update({
        "start_date": NOW().isoformat(),
        "exercise_index": 0,
        "hold_count_today": 0,
        "last_hold_date": None,
        "last_hold_time": None
    })
    save_data(data)

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
        await send(context.bot, chat_id, "Держись, брат. Что будем делать?", HEAVY_KEYBOARD, False)
        return

    if text == "📊 Дни":
        best = user.get("best_streak", 0)

        if days == 0:
            days_text = "Это твой первый день."
        elif days == 1:
            days_text = "Прошёл 1 день."
        elif days % 10 == 1 and days % 100 != 11:
            days_text = f"Прошёл {days} день."
        elif 2 <= days % 10 <= 4 and days % 100 not in [12,13,14]:
            days_text = f"Прошло {days} дня."
        else:
            days_text = f"Прошло {days} дней."

        msg = f"Ты держишься. {days_text}"

        if best > days:
            msg += f"\n\nЛучший стрик был: {best} дней."
        elif best > 0:
            msg += f"\n\nЭто твой лучший стрик прямо сейчас."

        await send(context.bot, chat_id, msg, save=False)

        if days in MILESTONES:
            await send(context.bot, chat_id, MILESTONES[days], save=False)
        return

    if text == "👋 Ты тут?":
        await asyncio.sleep(random.randint(2,6))
        await send(context.bot, chat_id, random.choice(TU_TUT_FIRST), save=False)
        await asyncio.sleep(random.randint(2,5))
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

    if text == "💪 Упражнения":
        await send(context.bot, chat_id, get_next_exercise(user), EXERCISE_KEYBOARD, False)
        return

    if text == "🧠 Что происходит с телом":
        await send(context.bot, chat_id, get_advice_for_day(days), ADVICE_KEYBOARD, False)
        return

    if text == "🔄 Другое упражнение":
        await send(context.bot, chat_id, get_next_exercise(user), EXERCISE_KEYBOARD, False)
        return

    if text == "😞 Срыв":
        reset_streak(chat_id)
        await send(context.bot, chat_id,
            "Ничего страшного, брат.\nГлавное — ты сказал честно.\nЭто уже победа.\n"
            "Начинаем с чистого листа. Я с тобой.", save=False)
        return

    if text == "↩ Назад":
        await send(context.bot, chat_id, "Возвращаемся.", MAIN_KEYBOARD, False)
        return

    if len(text) > 8:
        await send(context.bot, chat_id,
            "Понимаю, брат. Тяжко.\n"
            "Жми ✊ Держусь — всем разошлю.\n"
            "Или 😔 Тяжело — подберём приём прямо сейчас.", save=False)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен — держись, брат ✊")
    app.run_polling()

if __name__ == "__main__":
    main()
