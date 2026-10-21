
import discord
from discord.ext import commands, tasks
import random
import datetime
import os
import asyncio
import json
from dotenv import load_dotenv

load_dotenv()

# ======================================================
# 1. НАСТРОЙКИ
# ======================================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Основной канал Сенкосан
CHANNEL_ID = 1492134822666174605

# Самостоятельная активность
FOX_COOLDOWN_MINUTES = 30
FOX_ACTION_CHANCE = 0.25

# Файл постоянной памяти
DATA_FILE = "data.json"

# ======================================================
# 2. ПРЕДМЕТЫ И МАГАЗИН
# ======================================================

ITEMS = {
    "Common": [
        "🌲 Шишка",
        "🍃 Листик",
        "🪨 Камушек",
        "🍄 Гриб"
    ],
    "Rare": [
        "🫐 Черника",
        "🥚 Яйцо птицы",
        "🗝️ Ключ",
        "🍀 Клевер"
    ],
    "Mythical": [
        "💎 Кристалл",
        "👑 Корона",
        "🌟 Пыль",
        "🦊 Золотая лиса"
    ]
}

SHOP_ITEMS = {
    "🍪 Печенье": 10,
    "🌸 Цветок": 25,
    "🎀 Лента": 50,
    "💎 Маленький кристалл": 100
}

FOOD_LIST = [
    "ягоды", "печенье", "молоко", "рыба",
    "тофу", "мясо", "хлеб", "грибы", "яблоко"
]

# ======================================================
# 3. ФРАЗЫ, ФАКТЫ И ДЕЙСТВИЯ
# ======================================================

MOODS = {
    "игривое": [
        "Я прыгаю вокруг хвоста!",
        "Где мячик?",
        "Тяв! Погнали бегать!"
    ],
    "сонное": [
        "Глаза закрываются...",
        "Хвост такой мягкий...",
        "Зеееев..."
    ],
    "задумчивое": [
        "Смотрю на облака...",
        "Почему люди не тявкают?",
        "Лес сегодня тихий..."
    ],
    "голодное": [
        "В животе урчит...",
        "Где ягоды?",
        "Миска пустая..."
    ],
    "одинокое": [
        "Так тихо... не с кем играть.",
        "Скучаю по общению.",
        "Сижу в уголке."
    ]
}

FOX_FACTS = [
    "Лисы обладают очень острым слухом.",
    "Фенек — самая маленькая разновидность лис.",
    "У лис вертикальные зрачки.",
    "Лисы используют хвост для баланса.",
    "В японском фольклоре кицунэ — магические лисы."
]

TRUTH_OR_DARE_FACTS = [
    ("Лисы обладают острым слухом", True),
    ("Фенек — самая крупная лиса в мире", False),
    ("Лисы используют хвост для баланса", True),
    ("У всех лис зрачки круглые", False)
]

FOX_ACTIONS = [
    "🦊 *Лиса свернулась клубочком.*",
    "✨ *Лиса чистит свою шубку.*",
    "🐾 *Лиса оставила отпечаток лапки.*",
    "📦 *Лиса залезла в коробку.*",
    "👂 *Ушки лисы дернулись.*",
    "🌿 *Лиса выглянула из кустов.*",
    "💤 *Лиса сладко зевнула.*",
    "🍃 *Лиса гоняется за упавшим листиком.*"
]

# ======================================================
# 4. ПЕРЕМЕННЫЕ ПАМЯТИ
# ======================================================

inventories = {}
balances = {}
hunger = {}

# Последнее обычное сообщение пользователя
user_memory = {}

# Дата первого знакомства и количество замеченных сообщений
first_seen = {}
message_counts = {}

# Время последних сообщений
last_messages = {}

# Состояния игр в текущей сессии
truth_game = {}
mood_game = {}
searching_users = set()

# Время последнего факта дня
last_fact_date = None

# Время последнего самостоятельного сообщения
last_fox_action = None

# ======================================================
# 5. ЗАГРУЗКА И СОХРАНЕНИЕ ПАМЯТИ
# ======================================================

def load_memory():
    """Загружает память из JSON-файла."""

    if not os.path.exists(DATA_FILE):
        print("🦊 Файл памяти пока отсутствует. Создаём новую память.")
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Корневые данные должны быть объектом JSON.")

        print("🧠 Память Сенкосан успешно загружена!")
        return data

    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"⚠️ Не удалось загрузить память: {error}")
        print("⚠️ Файл не перезаписывается автоматически при ошибке.")
        return {}


def save_memory():
    """Сохраняет текущее состояние на диск."""

    data = {
        "inventories": inventories,
        "balances": balances,
        "hunger": hunger,
        "user_memory": user_memory,
        "first_seen": first_seen,
        "message_counts": message_counts,
        "last_messages": {
            str(uid): date.isoformat()
            for uid, date in last_messages.items()
        },
        "last_fact_date": last_fact_date,
        "last_fox_action": (
            last_fox_action.isoformat()
            if last_fox_action else None
        )
    }

    temp_file = DATA_FILE + ".tmp"

    try:
        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2
            )
            file.flush()
            os.fsync(file.fileno())

        # Атомарная замена старого файла новым
        os.replace(temp_file, DATA_FILE)

    except (OSError, TypeError, ValueError) as error:
        print(f"⚠️ Ошибка сохранения памяти: {error}")

        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except OSError:
            pass


def restore_memory():
    """Восстанавливает данные из файла."""

    global inventories
    global balances
    global hunger
    global user_memory
    global first_seen
    global message_counts
    global last_messages
    global last_fact_date
    global last_fox_action

    data = load_memory()

    inventories = {
        int(uid): items
        for uid, items in data.get("inventories", {}).items()
        if isinstance(items, list)
    }

    balances = {
        int(uid): amount
        for uid, amount in data.get("balances", {}).items()
        if isinstance(amount, (int, float)) and amount >= 0
    }

    hunger = {
        int(uid): max(0, min(100, amount))
        for uid, amount in data.get("hunger", {}).items()
        if isinstance(amount, (int, float))
    }

    user_memory = {
        int(uid): message
        for uid, message in data.get("user_memory", {}).items()
        if isinstance(message, str)
    }

    first_seen = {
        int(uid): date
        for uid, date in data.get("first_seen", {}).items()
        if isinstance(date, str)
    }

    message_counts = {
        int(uid): count
        for uid, count in data.get("message_counts", {}).items()
        if isinstance(count, int) and count >= 0
    }

    last_messages = {}

    for uid, date in data.get("last_messages", {}).items():
        try:
            last_messages[int(uid)] = (
                datetime.datetime.fromisoformat(date)
            )
        except (ValueError, TypeError):
            continue

    last_fact_date = data.get("last_fact_date")

    saved_action = data.get("last_fox_action")

    try:
        last_fox_action = (
            datetime.datetime.fromisoformat(saved_action)
            if saved_action else None
        )
    except (ValueError, TypeError):
        last_fox_action = None


restore_memory()


# ======================================================
# 6. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ======================================================

def get_balance(uid):
    return balances.get(uid, 0)


def get_inventory(uid):
    return inventories.setdefault(uid, [])


def get_hunger_state(value):
    if value <= 15:
        return "сытая ✨"
    elif value >= 85:
        return "очень голодная 🆘"

    return "в норме 👍"


# ======================================================
# 7. САМОСТОЯТЕЛЬНАЯ АКТИВНОСТЬ
# ======================================================

@tasks.loop(minutes=5)
async def fox_lifecycle():
    """Сенкосан иногда самостоятельно проявляет активность."""

    global last_fox_action

    channel = bot.get_channel(CHANNEL_ID)

    if channel is None:
        try:
            channel = await bot.fetch_channel(CHANNEL_ID)
        except (discord.HTTPException, discord.NotFound):
            print("⚠️ Не удалось найти канал Сенкосан.")
            return

    now = datetime.datetime.now()

    if last_fox_action is not None:
        elapsed = (now - last_fox_action).total_seconds() / 60

        if elapsed < FOX_COOLDOWN_MINUTES:
            return

    if random.random() > FOX_ACTION_CHANCE:
        return

    previous_action = last_fox_action
    last_fox_action = now

    # Запоминаем действие перед отправкой сообщения
    save_memory()

    try:
        await channel.send(random.choice(FOX_ACTIONS))

    except discord.HTTPException as error:
        print(f"⚠️ Не удалось отправить сообщение: {error}")

        # Если сообщение не отправлено, восстанавливаем cooldown
        last_fox_action = previous_action
        save_memory()


@fox_lifecycle.before_loop
async def before_fox_lifecycle():
    await bot.wait_until_ready()


# ======================================================
# 8. ГОЛОД
# ======================================================

@tasks.loop(hours=1)
async def hunger_tick():
    for uid in list(hunger.keys()):
        hunger[uid] = min(100, hunger[uid] + 8)

    save_memory()


@hunger_tick.before_loop
async def before_hunger_tick():
    await bot.wait_until_ready()


# ======================================================
# 9. ФАКТ ДНЯ
# ======================================================

@tasks.loop(minutes=1)
async def daily_fact_task():
    global last_fact_date

    now = datetime.datetime.now()
    today = now.strftime("%d-%m")

    if now.hour != 9 or now.minute != 0:
        return

    if last_fact_date == today:
        return

    channel = bot.get_channel(CHANNEL_ID)

    if channel is None:
        try:
            channel = await bot.fetch_channel(CHANNEL_ID)
        except discord.HTTPException:
            return

    try:
        await channel.send(
            f"☀️ **Лисий факт дня:** "
            f"{random.choice(FOX_FACTS)}"
        )

        last_fact_date = today
        save_memory()

    except discord.HTTPException as error:
        print(f"⚠️ Ошибка отправки факта дня: {error}")


@daily_fact_task.before_loop
async def before_daily_fact_task():
    await bot.wait_until_ready()


# ======================================================
# 10. ПОИСК ПРЕДМЕТОВ
# ======================================================

@bot.command(name="поиск")
@commands.cooldown(1, 10, commands.BucketType.user)
async def поиск(ctx):
    uid = ctx.author.id

    if uid in searching_users:
        return await ctx.send(
            "🦊 Ты уже отправил меня на поиск! Подожди немного."
        )

    searching_users.add(uid)

    try:
        msg = await ctx.send(
            "🦊 *Лиса внимательно принюхивается "
            "и убегает в заросли...*"
        )

        await asyncio.sleep(5)

        roll = random.random()

        if roll < 0.1:
            rarity = "Mythical"
            reward = 50
        elif roll < 0.4:
            rarity = "Rare"
            reward = 20
        else:
            rarity = "Common"
            reward = 5

        item = random.choice(ITEMS[rarity])

        get_inventory(uid).append(item)
        balances[uid] = get_balance(uid) + reward

        save_memory()

        await msg.edit(
            content=(
                f"🦊 **Нашла!**\n"
                f"Предмет: {item} (`{rarity}`)\n"
                f"Награда: `+{reward} 🍃`"
            )
        )

    finally:
        searching_users.discard(uid)


@поиск.error
async def поиск_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        seconds = max(1, int(error.retry_after))

        await ctx.send(
            f"🦊 *Лиса отдыхает.* "
            f"Попробуй снова через {seconds} сек."
        )
    else:
        raise error


# ======================================================
# 11. РЮКЗАК
# ======================================================

@bot.command(name="рюкзак")
async def рюкзак(ctx):
    uid = ctx.author.id
    items = inventories.get(uid, [])
    balance = get_balance(uid)

    if items:
        display = "\n".join(
            f"• {item}" for item in items[-15:]
        )

        if len(items) > 15:
            display += f"\n...и ещё {len(items) - 15} предметов"
    else:
        display = "Пусто"

    embed = discord.Embed(
        title="🎒 Рюкзак",
        description=display,
        color=0xff8c00
    )

    embed.add_field(
        name="🍃 Баланс",
        value=f"**{balance}** листиков",
        inline=False
    )

    await ctx.send(embed=embed)


# ======================================================
# 12. МАГАЗИН
# ======================================================

@bot.command(name="магазин")
async def магазин(ctx):
    embed = discord.Embed(
        title="🏪 Лавка Сенкосан",
        description=(
            "Добро пожаловать в мою лавку!\n"
            "Выбирай, что тебе приглянулось 🦊"
        ),
        color=0xff8c00
    )

    for item, price in SHOP_ITEMS.items():
        embed.add_field(
            name=item,
            value=(
                f"Цена: **{price} 🍃**\n"
                f"Купить: `!купить {item}`"
            ),
            inline=True
        )

    embed.set_footer(
        text="Зарабатывай листики с помощью !поиск и игр."
    )

    await ctx.send(embed=embed)


# ======================================================
# 13. ПОКУПКА ПРЕДМЕТОВ
# ======================================================

@bot.command(name="купить")
async def купить(ctx, *, item_name=""):
    uid = ctx.author.id

    selected_item = next(
        (
            item for item in SHOP_ITEMS
            if item.lower() == item_name.strip().lower()
        ),
        None
    )

    if selected_item is None:
        return await ctx.send(
            "🦊 Не знаю такого товара!\n"
            "Посмотри ассортимент: `!магазин`"
        )

    price = SHOP_ITEMS[selected_item]
    balance = get_balance(uid)

    if balance < price:
        missing = price - balance

        return await ctx.send(
            "🦊 *Лиса заглянула в твой кошелёк...*\n"
            f"Не хватает **{missing} 🍃**.\n"
            "Попробуй поискать что-нибудь: `!поиск`"
        )

    balances[uid] = balance - price
    get_inventory(uid).append(selected_item)

    save_memory()

    await ctx.send(
        f"🛍️ **Покупка совершена!**\n"
        f"Ты приобрёл: {selected_item}\n"
        f"Потрачено: **{price} 🍃**\n"
        f"Осталось: **{balances[uid]} 🍃**"
    )


# ======================================================
# 14. УГАДАЙ НАСТРОЕНИЕ
# ======================================================

@bot.command(name="эмоция")
async def эмоция(ctx):
    mood = random.choice(list(MOODS.keys()))
    hint = random.choice(MOODS[mood])

    mood_game[ctx.author.id] = mood

    await ctx.send(
        f"🦊 **Угадай настроение!**\n"
        f"Подсказка: *«{hint}»*\n"
        f"Ответь командой `!угадай настроение`."
    )


@bot.command(name="угадай")
async def угадай(ctx, *, guess=""):
    uid = ctx.author.id
    correct = mood_game.get(uid)

    if correct is None:
        return await ctx.send("Сначала начни игру: `!эмоция`")

    if guess.lower().strip() == correct:
        balances[uid] = get_balance(uid) + 10
        mood_game.pop(uid, None)

        save_memory()

        await ctx.send(
            f"✨ Верно! Мне {correct}.\n"
            f"Награда: **+10 🍃**"
        )
    else:
        await ctx.send("❌ Не-а! Попробуй ещё раз.")


# ======================================================
# 15. КОРМЛЕНИЕ
# ======================================================

@bot.command(name="покормить")
async def покормить(ctx, *, food=""):
    uid = ctx.author.id

    if uid not in hunger:
        hunger[uid] = 50

    food = food.lower().strip()

    if any(item in food for item in FOOD_LIST):
        hunger[uid] = max(0, hunger[uid] - 35)

        save_memory()

        await ctx.send(
            f"🦊 *Ням!* Теперь я "
            f"{get_hunger_state(hunger[uid])}"
        )
    else:
        await ctx.send("🦊 Я это не ем...")


# ======================================================
# 16. ПРАВДА ИЛИ ЛОЖЬ
# ======================================================

@bot.command(name="правда")
async def правда(ctx):
    fact, answer = random.choice(TRUTH_OR_DARE_FACTS)

    truth_game[ctx.author.id] = answer

    await ctx.send(
        f"🦊 **Правда или ложь?**\n"
        f"> {fact}\n\n"
        f"Ответь: `!ответ правда` или `!ответ ложь`"
    )


@bot.command(name="ответ")
async def ответ(ctx, *, guess=""):
    uid = ctx.author.id
    correct = truth_game.get(uid)

    if correct is None:
        return await ctx.send(
            "🦊 Сначала начни игру: `!правда`"
        )

    guess = guess.lower().strip()

    if guess in ["правда", "да", "true"]:
        user_answer = True
    elif guess in ["ложь", "нет", "false"]:
        user_answer = False
    else:
        return await ctx.send(
            "Ответь `правда` или `ложь`."
        )

    if user_answer == correct:
        balances[uid] = get_balance(uid) + 5

        await ctx.send("✨ Верно! Ты получаешь **+5 🍃**")
    else:
        await ctx.send("❌ Неверный ответ!")

    truth_game.pop(uid, None)
    save_memory()

# ======================================================
# 🦊 КАРТИНКИ И GIF СЕНКОСАН
# ======================================================

FOX_MEDIA = {
    "обычная": [
        # Вставь прямые ссылки на картинки Сенкосан
    ],
    "радость": ["https://klipy.com/gifs/senko-the-helpful-fox-senko-san-2",
               "https://klipy.com/gifs/senko-3"
    ],
    "смущение": [],
    "сонная": [],
    "удивление": [],
    "обида": [],
    "танец": [],
    "gif": []
}


@bot.command(name="лиса")
async def лиса(ctx, *, mood=""):
    mood = mood.lower().strip()

    # Без аргумента выбираем любую категорию
    if not mood:
        available = [
            name for name, urls in FOX_MEDIA.items()
            if urls
        ]

        if not available:
            return await ctx.send(
                "🦊 У меня пока нет картинок! "
                "Добавь ссылки в FOX_MEDIA."
            )

        mood = random.choice(available)

    if mood not in FOX_MEDIA:
        moods = ", ".join(
            name for name, urls in FOX_MEDIA.items()
            if urls
        ) or "пока нет"

        return await ctx.send(
            f"🦊 Не знаю такую эмоцию!\n"
            f"Доступные категории: {moods}"
        )

    urls = FOX_MEDIA[mood]

    if not urls:
        return await ctx.send(
            f"🦊 Для категории «{mood}» "
            f"пока нет изображений."
        )

    url = random.choice(urls)

    embed = discord.Embed(
        title=f"🦊 Сенкосан — {mood}",
        color=0xff8c00
    )
    embed.set_image(url=url)

    await ctx.send(embed=embed)


@bot.command(name="лиса_помощь")
async def лиса_помощь(ctx):
    embed = discord.Embed(
        title="🦊 Галерея Сенкосан",
        description=(
            "`!лиса` — случайная реакция\n"
            "`!лиса радость` — радость\n"
            "`!лиса смущение` — смущение\n"
            "`!лиса сонная` — сонное настроение\n"
            "`!лиса удивление` — удивление\n"
            "`!лиса обида` — обида\n"
            "`!лиса танец` — танец\n"
            "`!лиса gif` — случайная GIF"
        ),
        color=0xff8c00
    )

    await ctx.send(embed=embed)


# ======================================================
# 17. ПОМОЩЬ
# ======================================================

@bot.command(name="помощь")
async def помощь(ctx):
    embed = discord.Embed(
        title="🦊 Команды Сенкосан",
        description="Вот что я умею!",
        color=0xff8c00
    )

    embed.add_field(
        name="🎮 Игры и поиск",
        value=(
            "`!поиск` — поиск предметов\n"
            "`!эмоция` — угадай настроение\n"
            "`!угадай настроение` — ответить\n"
            "`!правда` — правда или ложь\n"
            "`!ответ правда/ложь` — ответить"
        ),
        inline=False
    )

    embed.add_field(
        name="🎒 Коллекция и магазин",
        value=(
            "`!рюкзак` — предметы и баланс\n"
            "`!магазин` — ассортимент\n"
            "`!купить название` — покупка"
        ),
        inline=False
    )

    embed.add_field(
        name="🍽️ Уход",
        value="`!покормить еда` — покормить лису",
        inline=False
    )

    await ctx.send(embed=embed)


# ======================================================
# 18. ПАМЯТЬ О ПОЛЬЗОВАТЕЛЯХ
# ======================================================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Не записываем команды как обычные сообщения
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    uid = message.author.id
    now = datetime.datetime.now()

    if uid not in first_seen:
        first_seen[uid] = now.isoformat()

    # Запоминаем последние 200 символов сообщения
    user_memory[uid] = message.content[:200]

    last_messages[uid] = now
    message_counts[uid] = message_counts.get(uid, 0) + 1

    save_memory()

    if "привет" in message.content.lower():
        await message.channel.send("Привет! 🦊")


# ======================================================
# 19. ЗАПУСК И ФОНОВЫЕ ЗАДАЧИ
# ======================================================

@bot.event
async def on_ready():
    print(f"🦊 Сенкосан онлайн: {bot.user}")
    print("🧠 Постоянная память активирована.")
    print(f"📁 Файл памяти: {os.path.abspath(DATA_FILE)}")

    if not fox_lifecycle.is_running():
        fox_lifecycle.start()

    if not hunger_tick.is_running():
        hunger_tick.start()

    if not daily_fact_task.is_running():
        daily_fact_task.start()


# ======================================================
# 20. ЗАПУСК БОТА
# ======================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN:
    print("🔑 Токен найден. Запускаем Сенкосан...")
    bot.run(TOKEN)
else:
    print("❌ Токен не найден! Проверь DISCORD_TOKEN.")
