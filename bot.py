
import discord
from discord.ext import commands, tasks
import random
import datetime
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

# ======================================================
# 1. НАСТРОЙКИ И ГЛОБАЛЬНЫЕ ДАННЫЕ
# ======================================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ID основного канала Сенкосан
CHANNEL_ID = 1492134822666174605

# Настройки самостоятельной активности
FOX_COOLDOWN_MINUTES = 30
FOX_ACTION_CHANCE = 0.25

# Память и игры
user_memory = {}
last_fact_date = None
truth_game = {}
mood_game = {}
hunger = {}
last_messages = {}

# Коллекции и экономика
inventories = {}       # {user_id: [items]}
balances = {}          # {user_id: leaves}
is_searching = False

# Защита от повторного поиска
searching_users = set()

# Время последнего самостоятельного сообщения
last_fox_action = None

# ======================================================
# 2. ПРЕДМЕТЫ ДЛЯ ПОИСКА
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

# ======================================================
# 3. МАГАЗИН
# ======================================================

SHOP_ITEMS = {
    "🍪 Печенье": 10,
    "🌸 Цветок": 25,
    "🎀 Лента": 50,
    "💎 Маленький кристалл": 100
}

FOOD_LIST = [
    "ягоды",
    "печенье",
    "молоко",
    "рыба",
    "тофу",
    "мясо",
    "хлеб",
    "грибы",
    "яблоко"
]

# ======================================================
# 4. ФРАЗЫ И ФАКТЫ
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
    "Лисы слышат мышь под метром снега.",
    "Фенек — самая маленькая лиса (1.5 кг).",
    "Зрачки лисы вертикальные, как у кошек.",
    "Лиса может прыгать на 2 метра вверх.",
    "В Японии лиса — символ мудрости."
]

TRUTH_OR_DARE_FACTS = [
    ("Лисы слышат мышей за 30 метров под снегом", True),
    ("Фенек живёт в Сибири", False),
    ("Лисы могут бегать 50 км/ч", True),
    ("Зрачки лисы круглые", False)
]

FOX_ACTIONS = [
    "🦊 *Лиса свернулась клубочком.*",
    "✨ *Лиса чистит свою шубку.*",
    "🐾 *Лиса оставила отпечаток лапки.*",
    "📦 *Лиса залезла в коробку.*",
    "👂 *Ушки лисы дернулись.*"
]

# ======================================================
# 5. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ======================================================

def get_hunger_state(value: int):
    if value <= 15:
        return "сытая ✨"
    elif value >= 85:
        return "очень голодная 🆘"
    return "в норме 👍"


def get_balance(uid: int):
    return balances.get(uid, 0)


def get_inventory(uid: int):
    return inventories.setdefault(uid, [])


# ======================================================
# 6. САМОСТОЯТЕЛЬНАЯ АКТИВНОСТЬ СЕНКОСАН
# ======================================================

@tasks.loop(minutes=5)
async def fox_lifecycle():
    """
    Проверяет возможность самостоятельного действия.
    Минимальный интервал между сообщениями — 30 минут.
    После окончания интервала шанс сообщения — 25%.
    """

    global last_fox_action

    channel = bot.get_channel(CHANNEL_ID)

    if channel is None:
        return

    now = datetime.datetime.now()

    if last_fox_action is not None:
        elapsed = (
            now - last_fox_action
        ).total_seconds() / 60

        if elapsed < FOX_COOLDOWN_MINUTES:
            return

    if random.random() > FOX_ACTION_CHANCE:
        return

    last_fox_action = now

    try:
        await channel.send(random.choice(FOX_ACTIONS))
    except discord.HTTPException as error:
        print(f"Не удалось отправить действие лисы: {error}")


@fox_lifecycle.before_loop
async def before_fox_lifecycle():
    await bot.wait_until_ready()


# ======================================================
# 7. ГОЛОД
# ======================================================

@tasks.loop(hours=1)
async def hunger_tick():
    for uid in list(hunger.keys()):
        hunger[uid] = min(100, hunger[uid] + 8)


@hunger_tick.before_loop
async def before_hunger_tick():
    await bot.wait_until_ready()


# ======================================================
# 8. ФАКТ ДНЯ
# ======================================================

@tasks.loop(minutes=1)
async def daily_fact_task():
    global last_fact_date

    now = datetime.datetime.now()
    today = now.strftime("%d-%m")

    if now.hour == 9 and now.minute == 0:
        if last_fact_date == today:
            return

        channel = bot.get_channel(CHANNEL_ID)

        if channel is not None:
            try:
                await channel.send(
                    f"☀️ **Лисий факт дня:** "
                    f"{random.choice(FOX_FACTS)}"
                )
                last_fact_date = today
            except discord.HTTPException as error:
                print(f"Ошибка отправки факта: {error}")


@daily_fact_task.before_loop
async def before_daily_fact_task():
    await bot.wait_until_ready()


# ======================================================
# 9. ПОИСК ПРЕДМЕТОВ
# ======================================================

@bot.command(name="поиск")
@commands.cooldown(1, 10, commands.BucketType.user)
async def поиск(ctx):
    """Отправляет Сенкосан на поиск."""

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

        rarity_roll = random.random()

        if rarity_roll < 0.1:
            rarity = "Mythical"
            reward = 50
        elif rarity_roll < 0.4:
            rarity = "Rare"
            reward = 20
        else:
            rarity = "Common"
            reward = 5

        item = random.choice(ITEMS[rarity])

        get_inventory(uid).append(item)
        balances[uid] = get_balance(uid) + reward

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
            f"🦊 *Лиса ещё отдыхает.* "
            f"Попробуй снова через {seconds} сек."
        )
    else:
        raise error


# ======================================================
# 10. РЮКЗАК
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
# 11. МАГАЗИН
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
            value=f"Цена: **{price} 🍃**\n"
                  f"Купить: `!купить {item}`",
            inline=True
        )

    embed.set_footer(
        text="Листики можно получить с помощью !поиск и игр."
    )

    await ctx.send(embed=embed)


# ======================================================
# 12. ПОКУПКА ПРЕДМЕТОВ
# ======================================================

@bot.command(name="купить")
async def купить(ctx, *, item_name: str = ""):
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

    # Списываем деньги и выдаём предмет
    balances[uid] = balance - price
    get_inventory(uid).append(selected_item)

    await ctx.send(
        f"🛍️ **Покупка совершена!**\n"
        f"Ты приобрёл: {selected_item}\n"
        f"Потрачено: **{price} 🍃**\n"
        f"Осталось: **{balances[uid]} 🍃**"
    )


# ======================================================
# 13. ИГРА: УГАДАЙ НАСТРОЕНИЕ
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
async def угадай(ctx, *, guess: str = ""):
    uid = ctx.author.id
    correct = mood_game.get(uid)

    if correct is None:
        return await ctx.send("Сначала начни игру: `!эмоция`")

    if guess.lower().strip() == correct:
        balances[uid] = get_balance(uid) + 10
        mood_game.pop(uid, None)

        await ctx.send(
            f"✨ Верно! Мне {correct}.\n"
            f"Награда: **+10 🍃**"
        )
    else:
        await ctx.send("❌ Не-а! Попробуй ещё раз.")


# ======================================================
# 14. КОРМЛЕНИЕ
# ======================================================

@bot.command(name="покормить")
async def покормить(ctx, *, food: str = ""):
    uid = ctx.author.id

    if uid not in hunger:
        hunger[uid] = 50

    food = food.lower().strip()

    if any(item in food for item in FOOD_LIST):
        hunger[uid] = max(0, hunger[uid] - 35)

        await ctx.send(
            f"🦊 *Ням!* Теперь я "
            f"{get_hunger_state(hunger[uid])}"
        )
    else:
        await ctx.send("🦊 Я это не ем...")


# ======================================================
# 15. ПРАВДА ИЛИ ЛОЖЬ
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
async def ответ(ctx, *, guess: str = ""):
    uid = ctx.author.id
    correct = truth_game.get(uid)

    if correct is None:
        return await ctx.send(
            "🦊 Сначала начни игру: `!правда`"
        )

    guess = guess.lower().strip()

    if guess in ["правда", "да", "true"]:
        user_ans = True
    elif guess in ["ложь", "нет", "false"]:
        user_ans = False
    else:
        return await ctx.send(
            "Ответь `правда` или `ложь`."
        )

    if user_ans == correct:
        balances[uid] = get_balance(uid) + 5

        await ctx.send(
            "✨ Верно! Ты получаешь **+5 🍃**"
        )
    else:
        await ctx.send("❌ Не-а! Неверный ответ.")

    truth_game.pop(uid, None)


# ======================================================
# 16. ПОМОЩЬ
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
            "`!рюкзак` — инвентарь и баланс\n"
            "`!магазин` — список товаров\n"
            "`!купить название` — покупка предмета"
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
# 17. СОБЫТИЯ DISCORD
# ======================================================

@bot.event
async def on_ready():
    print(f"Бот {bot.user} онлайн!")

    if not fox_lifecycle.is_running():
        fox_lifecycle.start()

    if not hunger_tick.is_running():
        hunger_tick.start()

    if not daily_fact_task.is_running():
        daily_fact_task.start()


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Команды обрабатываются отдельно
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    uid = message.author.id

    user_memory[uid] = message.content[:50]
    last_messages[uid] = datetime.datetime.now()

    if "привет" in message.content.lower():
        await message.channel.send("Привет! 🦊")


# ======================================================
# 18. ЗАПУСК БОТА
# ======================================================

TOKEN = os.getenv("DISCORD_TOKEN")

print("Переменная DISCORD_TOKEN найдена:", TOKEN is not None)
print("Токен непустой:", bool(TOKEN))

if TOKEN:
    bot.run(TOKEN)
else:
    print("Токен не найден! Проверь переменную DISCORD_TOKEN.")
