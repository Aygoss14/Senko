import discord
from discord.ext import commands, tasks
import random
import datetime
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

# ======================================================
# 1. НАСТРОЙКИ, ИНТЕНТЫ И ГЛОБАЛЬНЫЕ ДАННЫЕ
# ======================================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ID канала (ЗАМЕНИ НА СВОЙ)
CHANNEL_ID = 1492134822666174605 

# Память
user_memory = {}
last_fact_date = None 
truth_game = {}
mood_game = {}
hunger = {}
last_messages = {}

# Система коллекций
inventories = {} # {user_id: [items]}
balances = {}    # {user_id: leaves}
is_searching = False # Глобальный статус для цикла

# Данные предметов
ITEMS = {
    "Common": ["🌲 Шишка", "🍃 Листик", "🪨 Камушек", "🍄 Гриб"],
    "Rare": ["🫐 Черника", "🥚 Яйцо птицы", "🗝️ Ключ", "🍀 Клевер"],
    "Mythical": ["💎 Кристалл", "👑 Корона", "🌟 Пыль", "🦊 Золотая лиса"]
}

FOOD_LIST = ["ягоды", "печенье", "молоко", "рыба", "тофу", "мясо", "хлеб", "грибы", "яблоко"]

# ======================================================
# 2. БАЗА ФРАЗ
# ======================================================

MOODS = {
    "игривое": ["Я прыгаю вокруг хвоста!", "Где мячик?", "Тяв! Погнали бегать!"],
    "сонное": ["Глаза закрываются...", "Хвост такой мягкий...", "Зеееев..."],
    "задумчивое": ["Смотрю на облака...", "Почему люди не тявкают?", "Лес сегодня тихий..."],
    "голодное": ["В животе урчит...", "Где ягоды?", "Миска пустая..."],
    "одинокое": ["Так тихо... не с кем играть.", "Скучаю по общению.", "Сижу в уголке."]
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
# 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ======================================================

def get_hunger_state(value: int):
    if value <= 15: return "сытая ✨"
    elif value >= 85: return "очень голодная 🆘"
    return "в норме 👍"

# ======================================================
# 4. ТАСКИ (АКТИВНОСТЬ КАЖДЫЕ 10 МИНУТ)
# ======================================================

@tasks.loop(minutes=10)
async def fox_lifecycle():
    """Главный цикл жизни: либо действие, либо возвращение из поиска"""
    global is_searching
    channel = bot.get_channel(CHANNEL_ID)
    if not channel: return

    if is_searching:
        # Если в прошлом цикле она ушла искать, то сейчас возвращается
        is_searching = False
        await channel.send("🦊 *Лиса вернулась из глубины леса! Кажется, она что-то нашла...*")
    else:
        # Шанс 30% что она уйдет искать сама, иначе просто действие
        if random.random() < 0.3:
            is_searching = True
            await channel.send("🌿 *Лиса почуяла что-то интересное и убежала в густые кусты. Вернётся через 10 минут...*")
        else:
            await channel.send(random.choice(FOX_ACTIONS))

@tasks.loop(hours=1)
async def hunger_tick():
    for uid in hunger:
        hunger[uid] = min(100, hunger[uid] + 8)

@tasks.loop(minutes=1)
async def daily_fact_task():
    global last_fact_date
    now = datetime.datetime.now()
    if now.hour == 9 and now.minute == 0 and last_fact_date != now.strftime("%d-%m"):
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send(f"☀️ **Лисий факт дня:** {random.choice(FOX_FACTS)}")
            last_fact_date = now.strftime("%d-%m")

# ======================================================
# 5. КОМАНДЫ (КОЛЛЕКЦИИ И ИГРЫ)
# ======================================================

@bot.command()
async def поиск(ctx):
    """Пользователь отправляет лису на поиск"""
    uid = ctx.author.id
    
    # Имитация поиска
    msg = await ctx.send("🦊 *Лиса внимательно принюхивается и убегает в заросли...*")
    await asyncio.sleep(5) # Короткая пауза для эффекта
    
    rarity_roll = random.random()
    if rarity_roll < 0.1: rarity = "Mythical"; reward = 50
    elif rarity_roll < 0.4: rarity = "Rare"; reward = 20
    else: rarity = "Common"; reward = 5

    item = random.choice(ITEMS[rarity])
    
    if uid not in inventories: inventories[uid] = []
    inventories[uid].append(item)
    balances[uid] = balances.get(uid, 0) + reward
    
    await msg.edit(content=f"🦊 **Нашла!**\nПредмет: {item} (`{rarity}`)\nНаграда: `+{reward} 🍃`")

@bot.command()
async def рюкзак(ctx):
    uid = ctx.author.id
    items = inventories.get(uid, [])
    balance = balances.get(uid, 0)
    
    if not items: return await ctx.send("🦊 Твой рюкзак пуст. Используй `!поиск`!")
    
    display = ", ".join(items[-10:]) # Показываем последние 10
    await ctx.send(f"🎒 **Твой рюкзак:** {display}\n🍃 **Баланс:** {balance} листиков")

@bot.command()
async def эмоция(ctx):
    mood = random.choice(list(MOODS.keys()))
    hint = random.choice(MOODS[mood])
    mood_game[ctx.author.id] = mood
    await ctx.send(f"🦊 **Угадай настроение!**\nПодсказка: *«{hint}»*")

@bot.command()
async def угадай(ctx, guess: str):
    correct = mood_game.get(ctx.author.id)
    if not correct: return await ctx.send("Сначала `!эмоция`!")
    if guess.lower().strip() == correct:
        await ctx.send(f"✨ Верно! Мне {correct}. +10 🍃")
        balances[ctx.author.id] = balances.get(ctx.author.id, 0) + 10
        mood_game.pop(ctx.author.id)
    else: await ctx.send("❌ Не-а!")

@bot.command()
async def покормить(ctx, *, food=""):
    uid = ctx.author.id
    if uid not in hunger: hunger[uid] = 50
    if any(item in food.lower() for item in FOOD_LIST):
        hunger[uid] = max(0, hunger[uid] - 35)
        await ctx.send(f"🦊 *Ням!* Теперь я {get_hunger_state(hunger[uid])}")
    else: await ctx.send("🦊 Я это не ем...")

@bot.command()
async def помощь(ctx):
    embed = discord.Embed(title="🦊 Команды Сенко", color=0xff8c00)
    embed.add_field(name="🎮 Игры", value="`!поиск`, `!эмоция`, `!правда`")
    embed.add_field(name="🎒 Инфо", value="`!рюкзак`, `!время`, `!память`")
    embed.add_field(name="🍽️ Уход", value="`!покормить`")
    await ctx.send(embed=embed)

@bot.command()
async def правда(ctx):
    fact, answer = random.choice(TRUTH_OR_DARE_FACTS)
    truth_game[ctx.author.id] = answer
    await ctx.send(f"🦊 **Правда или Ложь?**\n> {fact}")

@bot.command()
async def ответ(ctx, guess: str):
    correct = truth_game.get(ctx.author.id)
    if correct is None: return
    user_ans = guess.lower() in ["правда", "да", "true"]
    if user_ans == correct:
        await ctx.send("✨ Верно! +5 🍃")
        balances[ctx.author.id] = balances.get(ctx.author.id, 0) + 5
    else: await ctx.send("❌ Ошибка!")
    truth_game.pop(ctx.author.id)

# ======================================================
# 6. СОБЫТИЯ
# ======================================================

@bot.event
async def on_ready():
    print(f"Бот {bot.user} онлайн!")
    if not fox_lifecycle.is_running(): fox_lifecycle.start()
    if not hunger_tick.is_running(): hunger_tick.start()
    if not daily_fact_task.is_running(): daily_fact_task.start()

@bot.event
async def on_message(message):
    if message.author.bot: return
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return
    
    uid = message.author.id
    user_memory[uid] = message.content[:50]
    if "привет" in message.content.lower():
        await message.channel.send("Привет! 🦊")

# ======================================================
# 7. ЗАПУСК
# ======================================================

TOKEN = os.getenv("DISCORD_TOKEN")

print("Переменная DISCORD_TOKEN найдена:", TOKEN is not None)
print("Токен непустой:", bool(TOKEN))

if TOKEN:
    bot.run(TOKEN)
else:
    print("Токен не найден!")
