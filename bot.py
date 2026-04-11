import discord
from discord.ext import commands, tasks
import random
import datetime
import os
import asyncio

# ======================================================
# 1. НАСТРОЙКИ, ИНТЕНТЫ И ГЛОБАЛЬНЫЕ ДАННЫЕ
# ======================================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ID канала для автоматических сообщений (ОБЯЗАТЕЛЬНО ЗАМЕНИ НА СВОЙ)
CHANNEL_ID = 1492134822666174605 

# Память бота в рамках одной сессии
user_memory = {}
last_fact_date = None 
truth_game = {}
mood_game = {}
hunger = {}
last_messages = {}

# Константы
FOOD_LIST = ["ягоды", "печенье", "молоко", "рыба", "тофу", "мясо", "хлеб", "грибы", "яблоко"]

# ======================================================
# 2. БАЗА ДАННЫХ (ФРАЗЫ, ФАКТЫ, НАСТРОЕНИЯ)
# ======================================================

MOODS = {
    "игривое": [
        "Я прыгаю вокруг своего хвоста!", 
        "Где мой любимый мячик?", 
        "Тяв! Давай побегаем по лесу!"
    ],
    "сонное": [
        "Глаза сами закрываются...", 
        "Хвост такой мягкий, как подушка...", 
        "Зеееев... Кажется, пора в нору."
    ],
    "задумчивое": [
        "Смотрю на облака и думаю о вечном...", 
        "Почему люди не умеют тявкать так же красиво?", 
        "Лес сегодня какой-то по-особенному тихий..."
    ],
    "голодное": [
        "В животе урчит, как у маленького трактора...", 
        "Где-то здесь точно прятались вкусные ягоды...", 
        "Моя миска выглядит очень одиноко и пусто."
    ],
    "одинокое": [
        "В чате так тихо... мне совсем не с кем поиграть.", 
        "Скучаю по чьим-то добрым словам и поглаживаниям.", 
        "Тихо сижу в уголке и жду друзей."
    ]
}

FOX_FACTS = [
    "Лисы относятся к семейству псовых.",
    "У лис очень острый слух: они слышат мышь под метром снега.",
    "Фенек — самая маленькая лиса в мире весом всего 1.5 кг.",
    "Зрачки лисы вертикальные, как у кошек.",
    "Лиса может прыгать на высоту до 2 метров.",
    "Лисы используют магнитное поле Земли, чтобы находить добычу.",
    "В Японии лиса (Кицунэ) считается символом мудрости и удачи.",
    "Лисы — всеядные: едят и жуков, и фрукты, и мелких грызунов.",
    "Хвост лисы помогает ей балансировать при беге и согревает зимой.",
    "Лиса может бегать со скоростью до 50 км/ч."
]

TRUTH_OR_DARE_FACTS = [
    ("Лисы могут слышать мышей под снегом на расстоянии 30 метров", True),
    ("Фенек живёт в лесах Сибири", False),
    ("Лисы могут прыгать почти на 2 метра в высоту", True),
    ("У лисиц вертикальные зрачки, как у кошек", True),
    ("Лисы всегда охотятся стаями", False),
    ("Лисы могут бегать со скоростью до 50 км/ч", True),
    ("Лисы умеют имитировать голоса других животных", False),
    ("Самая маленькая лиса в мире весит меньше 2 килограмм", True),
    ("Лисы прячут еду про запас в небольшие ямки", True),
    ("Лисы живут в среднем 30 лет в дикой природе", False)
]

FOX_ACTIONS = [
    "🦊 *Лиса свернулась клубочком и внимательно наблюдает за чатом.*",
    "✨ *Лиса поправляет свой пушистый хвост и довольно щурится.*",
    "🐾 *Лиса оставила на ковре невидимый отпечаток лапки и скрылась в тени.*",
    "📦 *Лиса нашла пустую коробку и теперь пытается в ней поместиться.*",
    "🦊 *Лисица потянулась, выгнув спинку, и сладко зевнула.*",
    "🧶 *Лиса нашла чей-то потерянный клубок ниток и задумчиво его катит.*",
    "🌬️ *Лиса принюхивается, чувствуя легкий весенний сквозняк.*",
    "👂 *Ушки лисы забавно дернулись в сторону входящего уведомления.*"
]

# ======================================================
# 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ======================================================

def get_hunger_state(value: int):
    if value <= 15: return "сытая ✨"
    elif value >= 85: return "очень голодная 🆘"
    elif value >= 60: return "проголодалась 🍽️"
    return "в норме 👍"

# ======================================================
# 4. ТАСКИ (АВТОМАТИЧЕСКИЕ ЗАДАЧИ)
# ======================================================

@tasks.loop(minutes=12)
async def fox_activity():
    """Отправляет случайное действие каждые 12 минут (нужно для Render)"""
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        try: channel = await bot.fetch_channel(CHANNEL_ID)
        except: return
    
    # Добавляем шанс того, что лиса напомнит о голоде
    if hunger and any(v > 75 for v in hunger.values()):
        await channel.send("🦊 *Лиса тихонько вздыхает и поглядывает на пустую миску...*")
    else:
        await channel.send(random.choice(FOX_ACTIONS))

@tasks.loop(hours=1)
async def hunger_tick():
    """Каждый час пользователи 'забывают' покормить лису"""
    for uid in hunger:
        hunger[uid] = min(100, hunger[uid] + 8)

@tasks.loop(minutes=1)
async def daily_fact_task():
    """Ежедневный факт в 9:00"""
    global last_fact_date
    now = datetime.datetime.now()
    today = now.strftime("%d-%m")

    if now.hour == 9 and now.minute == 0 and last_fact_date != today:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            fact = random.choice(FOX_FACTS)
            await channel.send(f"☀️ **Доброе утро! Лисий факт дня:**\n> {fact}")
            last_fact_date = today

# ======================================================
# 5. КОМАНДЫ БОТА
# ======================================================

@bot.event
async def on_ready():
    print(f"--- Бот {bot.user} запущен и готов к работе! ---")
    # Запуск фоновых задач
    if not fox_activity.is_running(): fox_activity.start()
    if not hunger_tick.is_running(): hunger_tick.start()
    if not daily_fact_task.is_running(): daily_fact_task.start()

@bot.command()
async def помощь(ctx):
    embed = discord.Embed(title="🦊 Меню команд лисички Сенко", color=0xff8c00)
    embed.add_field(name="!эмоция", value="Начать игру 'Угадай настроение'", inline=True)
    embed.add_field(name="!угадай [слово]", value="Ваш ответ на настроение", inline=True)
    embed.add_field(name="!покормить [еда]", value="Дать мне вкусняшку", inline=False)
    embed.add_field(name="!правда", value="Игра 'Правда или Ложь'", inline=True)
    embed.add_field(name="!ответ [правда/ложь]", value="Ваш ответ на факт", inline=True)
    embed.add_field(name="!память", value="Что я запомнила о тебе", inline=False)
    embed.add_field(name="!время", value="Часы в лесу", inline=True)
    embed.set_footer(text="Я также сама пишу в чат каждые 12 минут!")
    await ctx.send(embed=embed)

@bot.command()
async def эмоция(ctx):
    """Игра: Лиса загадывает настроение"""
    mood = random.choice(list(MOODS.keys()))
    hint = random.choice(MOODS[mood])
    mood_game[ctx.author.id] = mood
    
    await ctx.send(
        f"🦊 **Угадай моё настроение!**\nПодсказка: *«{hint}»*\n\n"
        f"Напиши: `!угадай [вариант]`\n"
        f"*(Варианты: игривое, сонное, задумчивое, голодное, одинокое)*"
    )

@bot.command()
async def угадай(ctx, guess: str):
    """Ответ на игру с настроением"""
    correct = mood_game.get(ctx.author.id)
    if not correct:
        return await ctx.send("Сначала попроси меня загадать настроение командой `!эмоция`!")
    
    if guess.lower().strip() == correct:
        await ctx.send(f"✨ **Верно!** Мне сейчас действительно {correct}. Ты настоящий друг!")
        mood_game.pop(ctx.author.id)
    else:
        await ctx.send("❌ Хмм... нет, это не совсем то. Попробуешь ещё раз?")

@bot.command()
async def покормить(ctx, *, food=""):
    uid = ctx.author.id
    if uid not in hunger: hunger[uid] = 50
    
    food = food.lower().strip()
    if any(item in food for item in FOOD_LIST) and food != "":
        hunger[uid] = max(0, hunger[uid] - 35)
        res = "🦊 *Хрум-хрум...* Очень вкусно! Большое спасибо! 🌸"
    else:
        hunger[uid] = min(100, hunger[uid] + 5)
        res = "🦊 *Принюхивается...* Я такое не ем. Дай мне ягод, рыбку или печенье!"

    await ctx.send(f"{res}\n**Мой голод:** {hunger[uid]}% ({get_hunger_state(hunger[uid])})")

@bot.command()
async def правда(ctx):
    """Игра Правда или Ложь"""
    fact, answer = random.choice(TRUTH_OR_DARE_FACTS)
    truth_game[ctx.author.id] = answer
    await ctx.send(f"🦊 **Правда или Ложь?**\n> {fact}\n\nНапиши: `!ответ правда` или `!ответ ложь`")

@bot.command()
async def ответ(ctx, guess: str):
    correct = truth_game.get(ctx.author.id)
    if correct is None: return await ctx.send("Сначала используй `!правда`!")
    
    user_ans = guess.lower() in ["правда", "да", "true", "правд"]
    if user_ans == correct:
        await ctx.send("✨ **Правильно!** Лисье чутье тебя не подвело.")
    else:
        await ctx.send("❌ **Ошибочка!** На самом деле всё иначе.")
    truth_game.pop(ctx.author.id, None)

@bot.command()
async def память(ctx):
    msg = user_memory.get(ctx.author.id, "ты пока молчал...")
    await ctx.send(f"🦊 Последнее, что я от тебя слышала: *«{msg}»*")

@bot.command()
async def время(ctx):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    await ctx.send(f"⌚ Сейчас в моём лесу: **{now}**")

# ======================================================
# 6. ОБРАБОТКА ТЕКСТА И ОН-МЕССЕДЖ
# ======================================================

@bot.event
async def on_message(message):
    if message.author.bot: return

    # Если это команда - выполняем и выходим
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    uid = message.author.id
    now = datetime.datetime.now()
    
    # Защита от спама (2 секунды)
    if uid in last_messages and (now - last_messages[uid]).total_seconds() < 2: return
    last_messages[uid] = now

    text = message.content.lower()
    user_memory[uid] = message.content[:50] # Запоминаем 50 символов

    # Интерактив без команд
    if any(w in text for w in ["привет", "ку", "здравствуй", "хей", "здравия"]):
        await message.channel.send(random.choice(["Привет! 🦊", "Здравствуй! Я так рада тебя видеть.", "Тяв! Приветик!"]))
    elif "как дела" in text:
        msg = "У меня всё отлично! Сижу, жду вкусняшек..."
        if hunger.get(uid, 0) > 70: msg = "Я немного проголодалась, но в целом всё хорошо!"
        await message.channel.send(msg)

# ======================================================
# 7. ЗАПУСК
# ======================================================

# Обязательно добавь переменную DISCORD_TOKEN в настройки Render (Environment Variables)!
TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("!!! ОШИБКА: ТОКЕН НЕ НАЙДЕН !!!")
