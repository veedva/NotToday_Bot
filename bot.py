import logging
import random
import json
import os
import asyncio
from datetime import datetime, time, date, timedelta
from typing import Dict, List, Optional
from filelock import FileLock
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
import pytz

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не установлен! Установи переменную окружения.")

DATA_FILE = "user_data.json"
LOCK_FILE = DATA_FILE + ".lock"
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Состояния для ConversationHandler
class ConversationState:
    START = 0
    MAIN_MENU = 1
    HEAVY_MENU = 2
    INFO_MENU = 3

# Сообщения (оставляем твои, они отличные)
MORNING_MESSAGES = [
    "Привет. Давай сегодня не будем, хорошо?",
    "Доброе утро. Не сегодня.",
    "Привет. Держимся сегодня?",
    "Доброе утро. Сегодня много дел, наверное нет.",
    "Привет. Сегодня обойдёмся без этого.",
    "Утро. Давай сегодня пропустим.",
    "Привет. Сегодня пожалуй что не стоит.",
    "Доброе утро. Напишу ещё сегодня.",
    "Привет. Сегодня точно не надо.",
    "Доброе! Давай сегодня без этого."
]

EVENING_MESSAGES = [
    "Не сегодня. Держись.",
    "Я тут. Давай не сегодня.",
    "Привет. Сегодня держимся, помнишь?",
    "Держись. Сегодня нет.",
    "Ещё чуть-чуть. Не сегодня.",
    "Я с тобой. Сегодня точно нет.",
    "Привет. Давай обойдёмся.",
    "Мы же решили — не сегодня.",
    "Держись там. Сегодня мимо.",
    "Привет. Сегодня пропустим."
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
    "Держался весь день. Красава."
]

TU_TUT_FIRST = [
    "Тут.", "Привет.", "А куда я денусь?", "Здесь.", "Тут, как всегда.",
    "Да, да.", "Как дела?", "Ага.", "Здравствуй.", "Тут, не переживай."
]

TU_TUT_SECOND = [
    "Держимся.", "Я с тобой.", "Всё по плану.", "Не хочу сегодня.", "Сегодня не буду.",
    "Я рядом.", "Держись.", "Всё будет нормально.", "Я в деле.", "Под контролем."
]

HOLD_RESPONSES = ["Отправлено. ✊", "Молодец. ✊", "Понял. ✊", "Так держать. ✊"]

MILESTONES = {
    3: "✨ <b>Три дня уже.</b> Самое тяжёлое позади.",
    7: "✨ <b>Неделя.</b> Рецепторы начинают восстанавливаться.",
    14: "✨ <b>Две недели!</b> Сон налаживается, голова яснее.",
    21: "✨ <b>Три недели.</b> Ты уже почти не думаешь об этом.",
    30: "✨ <b>Месяц без этого.</b> Мозг работает по-новому.",
    60: "✨ <b>Два месяца</b> — ты другой человек.",
    90: "✨ <b>Три месяца.</b> Полное восстановление. Ты молодец.",
    180: "✨ <b>Полгода.</b> Легенда.",
    365: "✨ <b>ГОД ЧИСТЫМ.</b> Ты сделал это ❤️"
}

HELP_TECHNIQUES = [
    "🧊 <b>Лёд на запястья 30-60 сек.</b>\nХолод активирует блуждающий нерв — тяга падает за минуту.",
    "🫁 <b>Дыхание 4-7-8:</b>\nВдох на 4 → задержка на 7 → выдох на 8. 4 раза. Снижает кортизол.",
    "⏱ <b>Таймер на 5 минут:</b>\n«Просто подожди». Тяга как волна — пройдёт сама за 3-7 минут.",
    "🚪 <b>Смена контекста:</b>\nВстань и выйди в другую комнату. Разрывает нейронную связь.",
    "🍋 <b>Резкий вкус:</b>\nКусок лимона или имбиря в рот. Перебивает дофаминовый сигнал.",
    "✊ <b>Сжатие кулаков:</b>\nСожми кулаки 10 сек → отпусти. 5 раз. Физическое напряжение уходит.",
    "💧 <b>Ледяная вода:</b>\nУмой лицо ледяной водой 30 сек. Активирует рефлекс погружения.",
    "📝 <b>3 причины:</b>\nНапиши 3 причины, почему сейчас не надо. Помоги мозгу вспомнить логику.",
    "🫁 <b>10 глубоких вдохов:</b>\nМедленные вдохи. Кислород снижает адреналин.",
    "💪 <b>Планка 45-60 секунд:</b>\nПока мышцы горят — голова не думает о тяге.",
    "🚶 <b>Быстрая прогулка:</b>\n7-10 минут. Движение вырабатывает BDNF — природный антидепрессант.",
    "👀 <b>Техника 5-4-3-2-1:</b>\nНазови 5 вещей (вижу), 4 (трогаю), 3 (слышу), 2 (запах), 1 (вкус).",
    "🚿 <b>Контрастный душ:</b>\n30 сек холодной → 1 мин тёплой. Повтори 2 раза.",
    "🥜 <b>Белок и жиры:</b>\nСъешь горсть орехов или сыра. Стабилизирует сахар в крови.",
    "🎾 <b>Теннисный мячик:</b>\nСожми до боли. 10 раз. Физический выброс адреналина.",
    "💪 <b>Поза силы:</b>\n2 минуты: ноги широко, руки в боки, грудь вперёд.",
    "🤔 <b>HALT-проверка:</b>\nГолоден? Злой? Одинок? Устал? Исправь хотя бы одно.",
    "🌊 <b>Urge Surfing:</b>\nПредставь тягу как волну. Не борись — наблюдай со стороны.",
    "💬 <b>Позови на помощь:</b>\nНапиши любому: «Тяжко, брат». Стыдно? Именно поэтому работает.",
    "💪 <b>20 отжиманий:</b>\nДо отказа. Пока тело в шоке — мозг забывает про дофаминовый голод."
]

RECOVERY_STAGES = [
    """📅 <b>ДНИ 1-3: ОСТРАЯ ФАЗА</b>

Пик физических симптомов. Рецепторы требуют привычный дофамин.

<u>Что происходит:</u>
• Температура, потливость
• Тревога 8-10/10
• Раздражительность
• Бессонница
• Сильная тяга каждые 1-2 часа

<code>Это самое тяжёлое время. Держись.</code>""",
    
    """📅 <b>ДНИ 4-7: ПОДОСТРАЯ ФАЗА</b>

Симптомы снижаются на 40%. Настроение скачет — это нормально.

<u>Что происходит:</u>
• Физические симптомы слабеют
• Появляются окна ясности
• Энергия всё ещё низкая
• Тяга приходит реже
• Эмоции нестабильны

<code>Мозг учится жить по-новому.</code>""",
    
    """📅 <b>ДНИ 8-14: АДАПТАЦИЯ</b>

Рецепторы оживают. CB1-рецепторы начинают восстанавливаться.

<u>Что происходит:</u>
• Сон налаживается
• Аппетит возвращается
• Тяга слабеет
• Появляется естественная радость
• Голова становится яснее

<code>Ты уже чувствуешь разницу.</code>""",
    
    """📅 <b>ДНИ 15-28: ВОССТАНОВЛЕНИЕ</b>

Мозг работает чище. Дофаминовая система приходит в норму.

<u>Что происходит:</u>
• Энергия стабильная
• Эмоции под контролем
• Радость от простых вещей
• Когнитивные функции +25%
• Тяга редкая и слабая

<code>Ты другой человек.</code>""",
    
    """📅 <b>ДНИ 29-90: СТАБИЛИЗАЦИЯ</b>

Полная перезагрузка нейронных связей. Новая норма жизни.

<u>Что происходит:</u>
• CB1-рецепторы восстановлены
• Дофамин производится естественно
• Жизнь без зависимости
• Тяга почти не появляется
• Ты свободен

<code>Это твоя новая реальность.</code>"""
]

COGNITIVE_DISTORTIONS = [
    """🤯 <b>«Я ВСЁ ИСПОРТИЛ»</b>

<u>Ошибка мышления:</u> катастрофизация.

<u>Факт:</u> Один срыв ≠ конец пути.
Мозг учится методом проб и ошибок. Каждая попытка укрепляет нейронные пути.

<code>Среднее число попыток до ремиссии — 3-5 раз.</code>

Ты не испортил. Ты учишься.""",
    
    """🤯 <b>«НИЧЕГО НЕ РАБОТАЕТ»</b>

<u>Ошибка мышления:</u> чёрно-белое мышление.

<u>Факт:</u> Работает, но медленно.
Нейропластичность требует времени. CB1-рецепторы восстанавливаются 4-6 недель.

<code>Мозг меняется каждый день, но ты не видишь этого.</code>

Отсутствие мгновенного результата ≠ отсутствие результата.""",
    
    """🤯 <b>«Я СЛАБЫЙ»</b>

<u>Ошибка мышления:</u> персонализация.

<u>Факт:</u> Зависимость — болезнь, не слабость.
Ты борешься с нейрохимическим дисбалансом. Это сложнее, чем кажется со стороны.

<code>85% людей срываются в первые 30 дней.</code>

Ты не слабый. Ты борешься с химией мозга.""",
    
    """🤯 <b>«ВСЁ БЕССМЫСЛЕННО»</b>

<u>Ошибка мышления:</u> эмоциональное обоснование.

<u>Факт:</u> Смысл появится через 2-3 недели.
Сейчас мозг в режиме выживания. Дофамина мало — всё кажется серым.

<code>Это временное состояние, а не реальность.</code>

Чувство бессмысленности — симптом ломки, а не правда о жизни.""",
    
    """🤯 <b>«У ДРУГИХ ПОЛУЧАЕТСЯ»</b>

<u>Ошибка мышления:</u> сравнение.

<u>Факт:</u> У всех свои сроки.
Ты видишь только результат, а не 5 попыток до него. Не 6 месяцев ломки. Не срывы.

<code>Каждый путь уникален.</code>

Сравнивай себя только с собой вчерашним.""",
    
    """🤯 <b>«ОДИН РАЗ НЕ СЧИТАЕТСЯ»</b>

<u>Ошибка мышления:</u> минимизация.

<u>Факт:</u> Каждый «один раз» считается.
Мозг не делит на «разы». Дофаминовый всплеск = укрепление старой нейронной связи.

<code>Один раз = откат назад на неделю.</code>

Если «не считается» — зачем тогда хочется?"""
]

TRIGGERS_INFO = [
    """⚠️ <b>МЫСЛЬ «ХОЧУ»</b>

<u>Мысль ≠ команда к действию.</u>

<u>Что делать:</u>
• Наблюдай за мыслью как за облаком
• Не спорь с ней, не убеждай себя
• Просто заметь: «О, это снова мысль»
• Через 3-7 минут она пройдёт сама

<code>Ты не обязан слушаться каждой мысли.</code>""",
    
    """⚠️ <b>СИЛЬНАЯ ЭМОЦИЯ</b>

<u>Злость, грусть, тревога</u> — маскируются под желание употребить.

<u>Что делать:</u>
• Назови эмоцию вслух: «Это злость»
• Эмоции как волны — поднимаются и спадают
• Не надо убегать от эмоции в вещество
• Прожить эмоцию = стать сильнее

<code>Это пройдёт. Всегда проходит.</code>""",
    
    """⚠️ <b>СКУКА / БЕЗДЕЛЬЕ</b>

<u>Мозг путает скуку с желанием употребить.</u> Ему просто нужна стимуляция.

<u>Что делать:</u>
• Скука — это не тяга, это сигнал «займись чем-то»
• 10 минут любой активности
• Прогулка, уборка, звонок другу
• Новый дофамин без вещества

<code>Скука лечится действием, а не веществом.</code>""",
    
    """⚠️ <b>СТРЕСС / ТРЕВОГА</b>

<u>Тревога говорит: «Убеги!»</u> Зависимость отвечает: «Знаю как».

<u>Что делать:</u>
• Тревога пройдёт через 15-20 минут
• Дыхание 4-7-8: вдох 4, задержка 7, выдох 8
• Холодная вода на лицо
• Скажи вслух: «Я в безопасности сейчас»

<code>Тревога временная. Срыв — постоянный.</code>""",
    
    """⚠️ <b>КОМПАНИЯ / ОКРУЖЕНИЕ</b>

<u>Самый сильный триггер.</u> Социальное давление + привычная обстановка.

<u>Что делать:</u>
• Избегай первые 30 дней
• Если нельзя избежать — заранее репетируй отказ
• «Завязал», «Не хочу», «Мне нельзя»
• Выходи из ситуации физически

<code>Твоя трезвость важнее чужого мнения.</code>"""
]

SCIENCE_FACTS = [
    """🔬 <b>CB1-РЕЦЕПТОРЫ</b>

<u>Каннабиноидные рецепторы в мозге.</u> ТГК их блокирует.

<u>Восстановление:</u>
• Первая неделя: +28% плотности
• Две недели: +50%
• 4 недели: почти полное восстановление
• 6 недели: 100% восстановлены

<code>Каждый день без вещества — рецепторы восстанавливаются.</code>""",
    
    """🔬 <b>ДОФАМИНОВАЯ СИСТЕМА</b>

<u>ТГК искусственно повышает дофамин в 2-3 раза.</u> Мозг снижает собственное производство.

<u>Восстановление:</u>
• Неделя: производство всё ещё низкое
• Две недели: начинает расти естественное производство
• Месяц: дофамин почти в норме
• 2-4 месяца: полное восстановление

<code>Мозг учится радоваться сам.</code>""",
    
    """🔬 <b>СОН И МЕЛАТОНИН</b>

<u>ТГК нарушает REM-фазу сна.</u> Мелатонин подавляется.

<u>Восстановление:</u>
• Первая неделя: бессонница, кошмары
• 10-14 дней: сон становится глубже
• 21 день: REM-фаза восстанавливается
• Месяц: сон качественный

<code>Глубокий сон = восстановление мозга.</code>""",
    
    """🔬 <b>ПАМЯТЬ И ГИППОКАМП</b>

<u>ТГК повреждает гиппокамп</u> — центр памяти и обучения.

<u>Восстановление:</u>
• Две недели: краткосрочная память улучшается
• Месяц: когнитивные функции +25%
• Три месяца: почти полное восстановление
• 6-12 месяцев: мозг работает как новый

<code>Ты станешь умнее. Буквально.</code>""",
    
    """🔬 <b>СТАТИСТИКА СРЫВОВ</b>

<u>Реальные цифры:</u>
• 85% срываются в первые 30 дней
• 60% — в первую неделю
• Среднее число попыток: 3-5 раз
• После 90 дней вероятность срыва падает до 15%

<code>Если сорвался — ты в большинстве. Главное — вернуться.</code>"""
]

# Кэш данных
_user_data_cache = None
_data_lock = asyncio.Lock()

# Клавиатуры
def get_main_keyboard():
    """Главное меню"""
    keyboard = [
        [
            InlineKeyboardButton("✊ Держусь", callback_data="hold"),
            InlineKeyboardButton("😔 Тяжело", callback_data="heavy")
        ],
        [
            InlineKeyboardButton("👋 Ты тут?", callback_data="here"),
            InlineKeyboardButton("📊 Дни", callback_data="days")
        ],
        [
            InlineKeyboardButton("❤️ Спасибо", callback_data="thanks"),
            InlineKeyboardButton("⏸ Помолчи", callback_data="pause")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_start_keyboard():
    """Стартовая клавиатура"""
    keyboard = [
        [InlineKeyboardButton("▶️ НАЧАТЬ БОРЬБУ", callback_data="start")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_heavy_keyboard():
    """Меню 'Тяжело'"""
    keyboard = [
        [
            InlineKeyboardButton("💪 Упражнение", callback_data="exercise"),
            InlineKeyboardButton("🧠 Информация", callback_data="info")
        ],
        [
            InlineKeyboardButton("💔 Срыв", callback_data="breakdown"),
            InlineKeyboardButton("↩️ Назад", callback_data="back_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_info_keyboard():
    """Меню информации"""
    keyboard = [
        [
            InlineKeyboardButton("📅 Стадии", callback_data="stages"),
            InlineKeyboardButton("⚠️ Триггеры", callback_data="triggers")
        ],
        [
            InlineKeyboardButton("🤯 Искажения", callback_data="distortions"),
            InlineKeyboardButton("🔬 Факты", callback_data="facts")
        ],
        [InlineKeyboardButton("↩️ Назад", callback_data="back_heavy")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Функции работы с данными
def load_data() -> Dict:
    """Загрузка данных пользователей"""
    global _user_data_cache
    if _user_data_cache is not None:
        return _user_data_cache
    
    with FileLock(LOCK_FILE):
        if not os.path.exists(DATA_FILE):
            _user_data_cache = {}
            return {}
        
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                _user_data_cache = json.load(f)
                return _user_data_cache
        except json.JSONDecodeError:
            logger.warning("Файл данных повреждён, создаём новый")
            _user_data_cache = {}
            return {}
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
            _user_data_cache = {}
            return {}

async def save_data():
    """Сохранение данных пользователей"""
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

def get_user(user_id: int) -> Dict:
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
            "last_hold_time": None,
            "last_stage_index": 0,
            "used_tips": [],
            "used_triggers": [],
            "used_distortions": [],
            "used_facts": []
        }
        asyncio.create_task(save_data())
    
    return data[uid]

async def save_user(user_id: int, updates: Dict = None):
    """Сохранение данных пользователя"""
    data = load_data()
    uid = str(user_id)
    
    if updates:
        if uid not in data:
            data[uid] = {}
        data[uid].update(updates)
    
    await save_data()

def get_active_users() -> List[int]:
    """Получение списка активных пользователей"""
    data = load_data()
    return [int(uid) for uid, user in data.items() if user.get("active", False)]

def get_current_time() -> datetime:
    """Текущее время в Московской таймзоне"""
    return datetime.now(MOSCOW_TZ)

def get_current_date() -> date:
    """Текущая дата"""
    return get_current_time().date()

def get_days_since_start(user_id: int) -> int:
    """Количество дней с начала трезвости"""
    user = get_user(user_id)
    if not user["start_date"]:
        return 0
    
    try:
        start = date.fromisoformat(user["start_date"])
        current = get_current_date()
        days = (current - start).days
        return max(days, 0)
    except Exception as e:
        logger.error(f"Ошибка расчёта дней для {user_id}: {e}")
        return 0

def format_days(days: int) -> str:
    """Форматирование дней с правильным склонением"""
    if 11 <= days % 100 <= 19:
        return f"{days} дней"
    if days % 10 == 1:
        return f"{days} день"
    if days % 10 in [2, 3, 4]:
        return f"{days} дня"
    return f"{days} дней"

def get_next_exercise(user_id: int) -> str:
    """Получение следующего упражнения"""
    user = get_user(user_id)
    used = user.get("used_tips", [])
    
    if len(used) >= len(HELP_TECHNIQUES):
        used = []
    
    available = [i for i in range(len(HELP_TECHNIQUES)) if i not in used]
    if not available:
        available = list(range(len(HELP_TECHNIQUES)))
        used = []
    
    choice = random.choice(available)
    used.append(choice)
    
    asyncio.create_task(save_user(user_id, {"used_tips": used}))
    
    return HELP_TECHNIQUES[choice]

def get_next_stage(user_id: int) -> str:
    """Получение следующей стадии восстановления"""
    user = get_user(user_id)
    last_index = user.get("last_stage_index", 0)
    
    stage_text = RECOVERY_STAGES[last_index]
    next_index = (last_index + 1) % len(RECOVERY_STAGES)
    
    if next_index == 0:
        stage_text += "\n\n✨ <i>Это была последняя стадия. Нажми ещё раз, чтобы начать сначала.</i>"
    else:
        stage_num = next_index + 1
        stage_text += f"\n\n📌 <i>Стадия {stage_num}/{len(RECOVERY_STAGES)}. Нажми ещё раз для следующей.</i>"
    
    asyncio.create_task(save_user(user_id, {"last_stage_index": next_index}))
    
    return stage_text

def get_next_item(user_id: int, items_list: List[str], used_key: str) -> str:
    """Получение следующего элемента из списка"""
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

async def reset_streak(user_id: int) -> int:
    """Сброс счётчика дней"""
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

def remove_user_jobs(chat_id: int, job_queue):
    """Удаление задач пользователя"""
    removed = 0
    for name in [f"morning_{chat_id}", f"evening_{chat_id}", f"night_{chat_id}"]:
        jobs = job_queue.get_jobs_by_name(name)
        for job in jobs:
            job.schedule_removal()
            removed += 1
    return removed

def schedule_jobs(chat_id: int, job_queue):
    """Планирование задач для пользователя"""
    existing_jobs = []
    for name in [f"morning_{chat_id}", f"evening_{chat_id}", f"night_{chat_id}"]:
        if job_queue.get_jobs_by_name(name):
            existing_jobs.extend(job_queue.get_jobs_by_name(name))
    
    if existing_jobs:
        remove_user_jobs(chat_id, job_queue)
    
    job_queue.run_daily(
        send_morning,
        time(9, 0, tzinfo=MOSCOW_TZ),
        data={'chat_id': chat_id},
        name=f"morning_{chat_id}"
    )
    job_queue.run_daily(
        send_evening,
        time(18, 0, tzinfo=MOSCOW_TZ),
        data={'chat_id': chat_id},
        name=f"evening_{chat_id}"
    )
    job_queue.run_daily(
        send_night,
        time(23, 0, tzinfo=MOSCOW_TZ),
        data={'chat_id': chat_id},
        name=f"night_{chat_id}"
    )

# Ежедневные уведомления
async def send_morning(context: ContextTypes.DEFAULT_TYPE):
    """Утреннее уведомление"""
    chat_id = context.job.data['chat_id']
    user = get_user(chat_id)
    
    if not user.get("active"):
        return
    
    days = get_days_since_start(chat_id)
    msg = random.choice(MORNING_MESSAGES)
    
    if days in MILESTONES:
        msg += f"\n\n{MILESTONES[days]}"
    
    try:
        await context.bot.send_message(
            chat_id, 
            msg, 
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки утреннего сообщения {chat_id}: {e}")

async def send_evening(context: ContextTypes.DEFAULT_TYPE):
    """Вечернее уведомление"""
    chat_id = context.job.data['chat_id']
    user = get_user(chat_id)
    
    if not user.get("active"):
        return
    
    try:
        await context.bot.send_message(
            chat_id,
            random.choice(EVENING_MESSAGES),
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка отправки вечернего сообщения {chat_id}: {e}")

async def send_night(context: ContextTypes.DEFAULT_TYPE):
    """Ночное уведомление"""
    chat_id = context.job.data['chat_id']
    user = get_user(chat_id)
    
    if not user.get("active"):
        return
    
    try:
        await context.bot.send_message(
            chat_id,
            random.choice(NIGHT_MESSAGES),
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка отправки ночного сообщения {chat_id}: {e}")

# Обработчики команд
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    chat_id = update.effective_chat.id
    
    welcome_text = """
    <b>ПРИВЕТ, БРАТ! 👋</b>

    Я буду писать три раза в день — просто напомнить: <i>сегодня не стоит.</i>

    <u>Как это работает:</u>
    • Утро (9:00) — настрой на день
    • Вечер (18:00) — проверка сил
    • Ночь (23:00) — похвала за день

    <u>Когда тяжело:</u>
    • Жми «✊ Держусь» — поддержу тебя
    • Все активные получат пуш
    • Можно до 5 раз в день

    <code>Держись, я рядом. Ты сильнее, чем думаешь. 💪</code>
    """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_start_keyboard(),
        parse_mode="HTML"
    )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stop"""
    chat_id = update.effective_chat.id
    
    await save_user(chat_id, {"active": False})
    removed = remove_user_jobs(chat_id, context.application.job_queue)
    logger.info(f"Удалено {removed} джобов для {chat_id}")
    
    await update.message.reply_text(
        "⏸ <b>Уведомления остановлены.</b>\n\n"
        "Когда будешь готов продолжать — нажми кнопку ниже.",
        reply_markup=get_start_keyboard(),
        parse_mode="HTML"
    )

# Обработчики callback-запросов
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline-кнопки"""
    query = update.callback_query
    await query.answer()  # Убираем "часики"
    
    chat_id = update.effective_user.id
    data = query.data
    
    # Обработка разных кнопок
    handlers = {
        "start": handle_start_button,
        "hold": handle_hold,
        "heavy": handle_heavy,
        "here": handle_are_you_here,
        "days": handle_days,
        "thanks": handle_thank_you,
        "pause": stop_command,
        "exercise": handle_exercise,
        "info": handle_info_menu,
        "breakdown": handle_breakdown,
        "stages": handle_stages,
        "triggers": handle_triggers,
        "distortions": handle_distortions,
        "facts": handle_facts,
        "back_main": handle_back_to_main,
        "back_heavy": handle_back_to_heavy
    }
    
    if data in handlers:
        await handlers[data](update, context)

async def handle_start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Начать'"""
    query = update.callback_query
    chat_id = update.effective_user.id
    user = get_user(chat_id)
    
    was_active = user.get("active", False)
    
    await save_user(chat_id, {
        "active": True,
        "start_date": get_current_date().isoformat(),
        "last_stage_index": 0,
        "used_tips": [],
        "used_triggers": [],
        "used_distortions": [],
        "used_facts": [],
        "hold_count_today": 0,
        "last_hold_date": None,
        "last_hold_time": None
    })
    
    if not was_active:
        schedule_jobs(chat_id, context.application.job_queue)
        logger.info(f"Созданы новые задачи для пользователя {chat_id}")
    
    days = get_days_since_start(chat_id)
    
    if days == 0:
        msg = (
            "🎯 <b>ПОЕХАЛИ!</b>\n\n"
            "Ты начинаешь свой путь к свободе.\n\n"
            "<code>Первый день — самый важный. Ты справишься.</code>"
        )
    else:
        msg = (
            f"🔄 <b>ПРОДОЛЖАЕМ!</b>\n\n"
            f"Ты держишься <b>{format_days(days)}</b>.\n\n"
            f"<code>Каждый день делает тебя сильнее.</code>"
        )
    
    await query.edit_message_text(
        msg,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

async def handle_hold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик 'Держусь'"""
    query = update.callback_query
    chat_id = update.effective_user.id
    user = get_user(chat_id)
    
    if not user.get("active"):
        await query.edit_message_text(
            "⚠️ <b>Сначала начни борьбу!</b>\n\n"
            "Нажми кнопку ниже, чтобы начать.",
            reply_markup=get_start_keyboard(),
            parse_mode="HTML"
        )
        return
    
    current_time = get_current_time()
    today_str = current_time.date().isoformat()
    
    if user.get("last_hold_date") != today_str:
        await save_user(chat_id, {
            "hold_count_today": 0,
            "last_hold_date": today_str
        })
    
    # Проверка таймаута
    if user.get("last_hold_time"):
        try:
            last_time_str = user["last_hold_time"]
            
            try:
                if 'T' in last_time_str:
                    last_time = datetime.fromisoformat(last_time_str)
                else:
                    last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=MOSCOW_TZ)
            except ValueError:
                last_time = current_time - timedelta(minutes=31)
            
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=MOSCOW_TZ)
            
            diff = (current_time - last_time).total_seconds()
            if diff < 1800:
                mins = int((1800 - diff) / 60) + 1
                await query.edit_message_text(
                    f"⏳ <b>Подожди ещё {mins} {'минуту' if mins == 1 else 'минут'}.</b>\n\n"
                    f"Тяга пройдёт. Дай себе время.",
                    reply_markup=get_main_keyboard(),
                    parse_mode="HTML"
                )
                return
        except Exception as e:
            logger.error(f"Ошибка проверки таймаута: {e}")
    
    # Проверка лимита
    if user.get("hold_count_today", 0) >= 5:
        await query.edit_message_text(
            "🎯 <b>Сегодня уже 5 раз.</b>\n\n"
            "Ты молодец, что держишься.\n"
            "Завтра снова сможешь нажать.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return
    
    # Сохранение данных
    await save_user(chat_id, {
        "last_hold_time": current_time.isoformat(),
        "last_hold_date": today_str,
        "hold_count_today": user.get("hold_count_today", 0) + 1
    })
    
    # Ответ пользователю
    await query.edit_message_text(
        random.choice(HOLD_RESPONSES),
        reply_markup=get_main_keyboard()
    )
    
    # Рассылка активным пользователям
    active = get_active_users()
    success_count = 0
    
    for uid in active:
        if uid != chat_id:
            try:
                await context.bot.send_message(uid, "✊")
                success_count += 1
                await asyncio.sleep(0.05)  # Защита от лимитов
            except Exception as e:
                error_str = str(e).lower()
                if "blocked" in error_str or "chat not found" in error_str or "forbidden" in error_str:
                    await save_user(uid, {"active": False})
                    remove_user_jobs(uid, context.application.job_queue)
                    logger.info(f"Деактивирован {uid}: заблокировал бота")
    
    logger.info(f"Пуш отправлен {chat_id}. Получили: {success_count}/{len(active)-1}")

async def handle_heavy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик 'Тяжело'"""
    query = update.callback_query
    await query.edit_message_text(
        "😔 <b>Понимаю, бывает тяжело.</b>\n\n"
        "Выбери, что тебе сейчас нужно:",
        reply_markup=get_heavy_keyboard(),
        parse_mode="HTML"
    )

async def handle_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик упражнений"""
    query = update.callback_query
    chat_id = update.effective_user.id
    tip = get_next_exercise(chat_id)
    
    await query.edit_message_text(
        tip,
        reply_markup=get_heavy_keyboard(),
        parse_mode="HTML"
    )

async def handle_info_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик меню информации"""
    query = update.callback_query
    await query.edit_message_text(
        "🧠 <b>БАЗА ЗНАНИЙ</b>\n\n"
        "Выбери раздел, который хочешь изучить:",
        reply_markup=get_info_keyboard(),
        parse_mode="HTML"
    )

async def handle_stages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик стадий восстановления"""
    query = update.callback_query
    chat_id = update.effective_user.id
    stage_text = get_next_stage(chat_id)
    
    await query.edit_message_text(
        stage_text,
        reply_markup=get_info_keyboard(),
        parse_mode="HTML"
    )

async def handle_triggers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик триггеров"""
    query = update.callback_query
    chat_id = update.effective_user.id
    trigger = get_next_item(chat_id, TRIGGERS_INFO, "used_triggers")
    
    await query.edit_message_text(
        trigger,
        reply_markup=get_info_keyboard(),
        parse_mode="HTML"
    )

async def handle_distortions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик когнитивных искажений"""
    query = update.callback_query
    chat_id = update.effective_user.id
    distortion = get_next_item(chat_id, COGNITIVE_DISTORTIONS, "used_distortions")
    
    await query.edit_message_text(
        distortion,
        reply_markup=get_info_keyboard(),
        parse_mode="HTML"
    )

async def handle_facts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик научных фактов"""
    query = update.callback_query
    chat_id = update.effective_user.id
    fact = get_next_item(chat_id, SCIENCE_FACTS, "used_facts")
    
    await query.edit_message_text(
        fact,
        reply_markup=get_info_keyboard(),
        parse_mode="HTML"
    )

async def handle_breakdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик срыва"""
    query = update.callback_query
    chat_id = update.effective_user.id
    days_lost = await reset_streak(chat_id)
    
    msg = (
        f"🔄 <b>СЧЁТЧИК СБРОШЕН</b>\n\n"
        f"Ты продержался <b>{format_days(days_lost)}</b>.\n\n"
        f"<i>Это не провал. Это данные для следующей попытки.</i>\n\n"
        f"<code>85% людей срываются в первые 30 дней.\n"
        f"Главное — не сдаваться.</code>"
    )
    
    await query.edit_message_text(
        msg,
        reply_markup=get_start_keyboard(),
        parse_mode="HTML"
    )

async def handle_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик просмотра дней"""
    query = update.callback_query
    chat_id = update.effective_user.id
    user = get_user(chat_id)
    days = get_days_since_start(chat_id)
    best = user.get("best_streak", 0)
    
    if days == 0:
        msg = "📅 <b>Ты только начинаешь.</b>\n\nПервый день — самый важный шаг."
    else:
        msg = f"📅 <b>Ты держишься {format_days(days)}.</b>"
        if best > days:
            msg += f"\n\n🏆 <i>Лучший результат: {format_days(best)}</i>"
        elif best > 0 and best == days:
            msg += f"\n\n🔥 <i>Это твой лучший результат прямо сейчас!</i>"
    
    await query.edit_message_text(
        msg,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )
    
    # Показ вехи, если достигнута
    if days in MILESTONES:
        await query.message.reply_text(
            MILESTONES[days],
            parse_mode="HTML"
        )

async def handle_are_you_here(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик 'Ты тут?'"""
    query = update.callback_query
    chat_id = update.effective_user.id
    
    await query.edit_message_text(
        "👀 <i>Проверяю...</i>",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )
    
    await asyncio.sleep(random.randint(2, 4))
    
    first_msg = random.choice(TU_TUT_FIRST)
    await query.edit_message_text(
        first_msg,
        reply_markup=get_main_keyboard()
    )
    
    await asyncio.sleep(random.randint(2, 3))
    
    second_msg = random.choice(TU_TUT_SECOND)
    await query.edit_message_text(
        second_msg,
        reply_markup=get_main_keyboard()
    )

async def handle_thank_you(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик 'Спасибо'"""
    query = update.callback_query
    
    msg = (
        "❤️ <b>СПАСИБО ТЕБЕ, ЧТО ТЫ ЕСТЬ.</b>\n\n"
        "Твоя борьба вдохновляет.\n\n"
        "<u>Если хочешь поддержать проект:</u>\n"
        "<code>Сбер: 2202 2084 3481 5313</code>\n\n"
        "Любая сумма поможет развивать бота дальше.\n\n"
        "<i>Главное — держись. Ты не один.</i>"
    )
    
    await query.edit_message_text(
        msg,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

async def handle_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    query = update.callback_query
    await query.edit_message_text(
        "✅ <b>Возвращаемся в главное меню.</b>",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

async def handle_back_to_heavy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в меню 'Тяжело'"""
    query = update.callback_query
    await query.edit_message_text(
        "😔 <b>Понимаю, бывает тяжело.</b>\n\n"
        "Выбери, что тебе сейчас нужно:",
        reply_markup=get_heavy_keyboard(),
        parse_mode="HTML"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    
    if text.lower() in ["/start", "старт", "начать"]:
        await start_command(update, context)
    elif text.lower() in ["/stop", "стоп", "остановить"]:
        await stop_command(update, context)
    else:
        await update.message.reply_text(
            "🤖 <b>Используй кнопки для управления!</b>\n\n"
            "Все функции доступны через меню ниже.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )

async def restore_jobs(application):
    """Восстановление задач при перезапуске"""
    active = get_active_users()
    logger.info(f"🔄 Восстанавливаем задания для {len(active)} пользователей")
    
    existing_jobs = list(application.job_queue.jobs())
    
    for user_id in active:
        user_has_jobs = False
        for job in existing_jobs:
            if (hasattr(job, 'name') and str(user_id) in job.name) or \
               (job.data and job.data.get('chat_id') == user_id):
                user_has_jobs = True
                break
        
        if not user_has_jobs:
            schedule_jobs(user_id, application.job_queue)
            logger.info(f"✅ Восстановлены задачи для {user_id}")

def main():
    """Основная функция запуска бота"""
    # Создание приложения
    application = Application.builder().token(TOKEN).build()
    
    # Добавление обработчиков команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    
    # Добавление обработчика callback-запросов
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Добавление обработчика текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Восстановление задач при инициализации
    application.post_init = restore_jobs
    
    # Запуск бота
    logger.info("🚀 Бот запущен и готов к работе!")
    logger.info("📱 Используйте /start для начала")
    logger.info("⏸ Используйте /stop для остановки уведомлений")
    
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True  # Чистим старые апдейты при запуске
    )

if __name__ == "__main__":
    main()
