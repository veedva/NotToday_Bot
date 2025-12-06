import logging
import random
import json
import os
import asyncio
from datetime import datetime, time
from filelock import FileLock
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)
import pytz

logging.basicConfig(format='%(asctime)s — %(levelname)s — %(message)s', level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен!")

DATA_FILE = "user_data.json"
LOCK_FILE = DATA_FILE + ".lock"
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

def NOW():
    return datetime.now(MOSCOW_TZ).replace(microsecond=0)

MORNING_MESSAGES = [
    "Привет. Давай сегодня не будем, хорошо?",
    "Доброе утро, брат. Не сегодня.",
    "Привет. Держимся сегодня, да?",
    "Доброе. Сегодня дел много, нет наверное.",
    "Привет. Сегодня обойдёмся и так.",
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

def load_data():
    """Загрузка всех данных"""
    with FileLock(LOCK_FILE):
        if not os.path.exists(DATA_FILE):
            return {}
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            logging.error("Файл данных повреждён, создаём новый")
            return {}

def save_data(data):
    """Сохранение всех данных"""
    with FileLock(LOCK_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(user_id):
    """Получение данных пользователя"""
    data = load_data()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "start_date": None,
            "active": False,
            "best_streak": 0,
            "hold_count_today": 0,
            "last_hold_date": None,
            "last_hold_time": None
        }
        save_data(data)
    return data[uid]

def update_user(user_id, updates):
    """Обновление данных пользователя"""
    data = load_data()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "start_date": None,
            "active": False,
            "best_streak": 0,
            "hold_count_today": 0,
            "last_hold_date": None,
            "last_hold_time": None
        }
    data[uid].update(updates)
    save_data(data)
    return data[uid]

def get_days(user_id):
    """Подсчёт дней"""
    user = get_user(user_id)
    if not user["start_date"]:
        return 0
    try:
        start = datetime.fromisoformat(user["start_date"]).date()
        return (NOW().date() - start).days
    except (ValueError, TypeError):
        return 0

def get_advice_for_day(days):
    if days <= 3:
        return HELP_ADVICE_BY_DAY[0]
    elif days <= 7:
        return HELP_ADVICE_BY_DAY[1]
    elif days <= 14:
        return HELP_ADVICE_BY_DAY[2]
    elif days <= 28:
        return HELP_ADVICE_BY_DAY[3]
    elif days <= 42:
        return HELP_ADVICE_BY_DAY[4]
    elif days <= 90:
        return HELP_ADVICE_BY_DAY[5]
    else:
        return HELP_ADVICE_BY_DAY[6]

async def morning_message(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    user = get_user(chat_id)
    if not user.get("active"):
        return
    
    days = get_days(chat_id)
    if days in MILESTONES:
        await context.bot.send_message(chat_id, MILESTONES[days])
    else:
        await context.bot.send_message(chat_id, random.choice(MORNING_MESSAGES))

async def evening_message(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    user = get_user(chat_id)
    if user.get("active"):
        await context.bot.send_message(chat_id, random.choice(EVENING_MESSAGES))

async def night_message(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    user = get_user(chat_id)
    if user.get("active"):
        await context.bot.send_message(chat_id, random.choice(NIGHT_MESSAGES))

def schedule_messages(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Планирование сообщений"""
    for job in context.job_queue.get_jobs_by_name(str(chat_id)):
        job.schedule_removal()
    
    context.job_queue.run_daily(
        morning_message,
        time(9, 0, tzinfo=MOSCOW_TZ),
        chat_id=chat_id,
        name=f"morning_{chat_id}"
    )
    
    context.job_queue.run_daily(
        evening_message,
        time(18, 0, tzinfo=MOSCOW_TZ),
        chat_id=chat_id,
        name=f"evening_{chat_id}"
    )
    
    context.job_queue.run_daily(
        night_message,
        time(23, 0, tzinfo=MOSCOW_TZ),
        chat_id=chat_id,
        name=f"night_{chat_id}"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_user(update.effective_user.id, {
        "start_date": NOW().isoformat(),
        "active": True,
        "hold_count_today": 0,
        "last_hold_date": None,
        "last_hold_time": None
    })
    
    await update.message.reply_text(
        "Привет, брат.\n\n"
        "Я буду писать три раза в день — просто напомню: сегодня не надо.\n\n"
        "Когда тяжело — жми ✊ Держусь\n"
        "Все получат пуш и узнают, что ты ещё здесь.\n"
        "Можешь жать до 5 раз в сутки.\n\n"
        "Держись. Я рядом.",
        reply_markup=get_main_keyboard()
    )
    
    schedule_messages(context, update.effective_chat.id)

async def hold_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    
    if not user.get("active"):
        await update.message.reply_text("Сначала нажми ▶ Начать")
        return
    
    last_time = user.get("last_hold_time")
    if last_time:
        try:
            last_dt = datetime.fromisoformat(last_time)
            if (NOW() - last_dt).seconds < 1800:
                mins = 30 - (NOW() - last_dt).seconds // 60
                if mins == 1:
                    await update.message.reply_text("Погоди ещё 1 минуту, брат.")
                elif mins in [2, 3, 4]:
                    await update.message.reply_text(f"Погоди ещё {mins} минуты, брат.")
                else:
                    await update.message.reply_text(f"Погоди ещё {mins} минут, брат.")
                return
        except (ValueError, TypeError):
            pass
    
    today = NOW().date()
    last_date = user.get("last_hold_date")
    
    if last_date != str(today):
        user["hold_count_today"] = 0
    
    if user.get("hold_count_today", 0) >= 5:
        await update.message.reply_text("Сегодня уже 5 раз, брат.\nЗавтра снова сможешь.")
        return
    
    update_user(update.effective_user.id, {
        "last_hold_time": NOW().isoformat(),
        "last_hold_date": str(today),
        "hold_count_today": user.get("hold_count_today", 0) + 1
    })
    
    await update.message.reply_text(random.choice(HOLD_RESPONSES))
    
    data = load_data()
    for uid, u in data.items():
        if u.get("active") and int(uid) != update.effective_user.id:
            try:
                await context.bot.send_message(int(uid), "✊")
            except:
                pass

async def days_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user.get("start_date"):
        await update.message.reply_text("Сначала нажми ▶ Начать")
        return
    
    days = get_days(update.effective_user.id)
    best = user.get("best_streak", 0)
    
    if days == 0:
        msg = "Только начал. Первый день — самый тяжёлый.\nТы уже герой, что решился."
    elif days == 1:
        msg = "Ты держишься 1 день"
    elif days in [2, 3, 4]:
        msg = f"Ты держишься {days} дня"
    else:
        msg = f"Ты держишься {days} дней"
    
    if best > days:
        msg += f"\n\nЛучший стрик был: {best} дней"
    elif best > 0 and best == days:
        msg += f"\n\nЭто твой лучший стрик прямо сейчас"
    
    await update.message.reply_text(msg)
    
    if days in MILESTONES:
        await update.message.reply_text(MILESTONES[days])

async def are_you_there(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(TU_TUT_FIRST))
    
    async def send_second():
        await asyncio.sleep(random.randint(2, 5))
        await update.message.reply_text(random.choice(TU_TUT_SECOND))
    
    asyncio.create_task(send_second())

async def thank_you(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Спасибо тебе, брат, что ты есть. ❤️\n\n"
        "Если хочешь поддержать того, кто это всё написал:\n"
        "Сбер 2202 2084 3481 5313\n\n"
        "Любая сумма = ещё одному человеку поможем.\n\n"
        "Главное — держись."
    )

async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_user(update.effective_user.id, {"active": False})
    
    for job in context.job_queue.get_jobs_by_name(str(update.effective_chat.id)):
        job.schedule_removal()
    
    await update.message.reply_text("Уведомления остановлены.", reply_markup=get_start_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    exercise = random.choice(HELP_TECHNIQUES)
    await update.message.reply_text(exercise)

async def handle_heavy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user.get("start_date"):
        await update.message.reply_text("Сначала нажми ▶ Начать")
        return
    
    days = get_days(update.effective_user.id)
    advice = get_advice_for_day(days)
    exercise = random.choice(HELP_TECHNIQUES)
    await update.message.reply_text(f"{advice}\n\nПопробуй это:\n{exercise}")

async def handle_breakdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    days = get_days(update.effective_user.id)
    
    updates = {
        "start_date": NOW().isoformat(),
        "hold_count_today": 0,
        "last_hold_date": None,
        "last_hold_time": None
    }
    
    if days > user.get("best_streak", 0):
        updates["best_streak"] = days
    
    update_user(update.effective_user.id, updates)
    
    await update.message.reply_text(
        "Срыв — не конец. Это данные.\n"
        "Начинаем с чистого листа. Я с тобой."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    text = update.message.text
    
    if text == "✊ Держусь":
        await hold_command(update, context)
    elif text == "😔 Тяжело":
        await handle_heavy(update, context)
    elif text == "📊 Дни":
        await days_command(update, context)
    elif text == "👋 Ты тут?":
        await are_you_there(update, context)
    elif text == "❤️ Спасибо":
        await thank_you(update, context)
    elif text == "⏸ Помолчи":
        await pause(update, context)
    elif text == "💔 Срыв":
        await handle_breakdown(update, context)
    elif text.lower() in ["упражнение", "упражнения", "help"]:
        await help_command(update, context)

async def restore_jobs(application: Application):
    """Восстановление задач при перезапуске"""
    data = load_data()
    for uid, user in data.items():
        if user.get("active"):
            chat_id = int(uid)
            for job in application.job_queue.get_jobs_by_name(str(chat_id)):
                job.schedule_removal()
            
            application.job_queue.run_daily(
                morning_message,
                time(9, 0, tzinfo=MOSCOW_TZ),
                chat_id=chat_id,
                name=f"morning_{chat_id}"
            )
            
            application.job_queue.run_daily(
                evening_message,
                time(18, 0, tzinfo=MOSCOW_TZ),
                chat_id=chat_id,
                name=f"evening_{chat_id}"
            )
            
            application.job_queue.run_daily(
                night_message,
                time(23, 0, tzinfo=MOSCOW_TZ),
                chat_id=chat_id,
                name=f"night_{chat_id}"
            )

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("days", days_command))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.run_polling(
        post_init=restore_jobs,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
