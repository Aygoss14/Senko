import discord
from discord.ext import commands, tasks
import random
import datetime
import os
import asyncio

# =====================
# INTENTS
# =====================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =====================
# ПАМЯТЬ
# =====================
user_memory = {}

# =====================
# 🦊 ЛИСЫ
# =====================
fox_facts = [
    "Лисы относятся к семейству псовых",
    "Самый распространённый вид — рыжая лиса",
    "Лисы встречаются почти по всему миру",
    "Лисы умеют адаптироваться к городским условиям",
    "У лис очень острый слух",
    "Лиса может слышать мышь под снегом",
    "Лисы охотятся в основном ночью",
    "Лисы являются всеядными животными",
    "Лисы могут прыгать высоко вверх для охоты",
    "Рыжая лиса — символ хитрости",
    "Фенек — самая маленькая лиса в мире",
    "Фенек живёт в пустыне Сахара",
    "У фенека огромные уши для охлаждения",
    "Арктическая лиса меняет цвет шерсти по сезонам",
    "Лисы могут запоминать места с едой",
    "Лисы иногда притворяются мёртвыми",
    "Лисы способны слышать под снегом",
    "Лисы могут издавать более 20 разных звуков",
    "Лисы могут жить рядом с людьми",
    "Лисы иногда ведут себя как кошки",
]
# =====================
# 🎉 ПРАЗДНИКИ
# =====================
holiday_facts = {
    "01-01": "Новый год 🎆 — лисы становятся осторожнее зимой.",
    "14-02": "День любви 💕 — лисы часто создают пары на жизнь.",
    "08-03": "Весна 🌸 — лисы становятся активнее.",
    "01-05": "Весенний день 🌿 — природа просыпается.",
    "31-10": "Хэллоуин 👻 — лис считали духами леса.",
    "25-12": "Зима ❄️ — арктические лисы почти исчезают в снегу.",
    "01-11": "🦊 ДЕНЬ ЛИС — праздник хитрости и свободы лис!",
}

CHANNEL_ID = 1492134822666174605

# =====================
# ИГРОВЫЕ ДАННЫЕ
# =====================
emotion_game = {}
truth_game = {}
hunger = {}

last_messages = {}

# =====================
# ГОЛОД СТАТУС
# =====================
def hunger_state(value: int):
    if value <= 0:
        return "full"
    elif value >= 85:
        return "critical"
    elif value >= 70:
        return "hungry"
    return "ok"

# =====================
# ТИК
# =====================
bot_started = False

@bot.event
async def on_ready():
    global bot_started

    print(f"Бот запущен как {bot.user}")

    if bot_started:
        return
    bot_started = True

    hunger_tick.start()
    send_daily_fact.start()
        
food_list = ["ягоды", "печенье", "молоко", "рыба", "тофу"]

# =====================
# 📉 АВТО-ГОЛОД
# =====================
@tasks.loop(minutes=60)
async def hunger_tick():
    for uid in list(hunger.keys()):
        hunger[uid] += random.randint(2, 8)
        hunger[uid] = min(100, hunger[uid])


# =====================
# ⏰ ФАКТЫ
# =====================
@tasks.loop(minutes=1)
async def send_daily_fact():
    now = datetime.datetime.now()

    if now.hour == 9 and now.minute == 0:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            channel = await bot.fetch_channel(CHANNEL_ID)

        key = now.strftime("%d-%m")

        msg = holiday_facts.get(key, "🦊 Факт: " + random.choice(fox_facts))
        await channel.send(msg)


# =====================
# 🟢 ON READY (ИСПРАВЛЕННЫЙ)
# =====================
@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")

    # защита от двойного запуска
    if not hunger_tick.is_running():
        hunger_tick.start()

    if not send_daily_fact.is_running():
        send_daily_fact.start()

# =====================
# 🟡 КОРМЛЕНИЕ
# =====================
@bot.command()
async def покормить(ctx, *, food=""):
    if ctx.author.id not in hunger:
        hunger[ctx.author.id] = 50

    food = food.lower().strip()

    if food in food_list:
        hunger[ctx.author.id] -= 25
        msg = "🦊 Мм... вкусно... спасибо 🌸"
    else:
        hunger[ctx.author.id] += 10
        msg = "…я не уверена, что это еда"

    hunger[ctx.author.id] = max(0, min(100, hunger[ctx.author.id]))
    state = hunger_state(hunger[ctx.author.id])

    extra = ""
    if state == "full":
        extra = "\n✨ Спасибо... я сытая"
    elif state == "hungry":
        extra = "\n…я немного голодна"
    elif state == "critical":
        extra = "\n🦊 мне правда нужно поесть..."

    await ctx.send(f"{msg}{extra}\n🍽️ Голод: {hunger[ctx.author.id]}")

# =====================
# 🔵 ПРАВДА / ЛОЖЬ (РАСШИРЕНО)
# =====================
@bot.command()
async def правда(ctx):

    facts = [
        ("Лисы могут слышать мышей под снегом", True),
        ("Фенек живёт в пустыне", True),
        ("Лисы живут только в России", False),
        ("Лисы могут прыгать почти на 2 метра", True),
        ("Лисы — кошачьи животные", False),
        ("Арктическая лиса меняет цвет зимой", True),
        ("Лисы не издают звуков", False),
        ("Лисы умеют лазить по деревьям", True),
        ("Лисы живут 200 лет", False),
        ("Лисы могут жить в городах", True),
    ]

    fact, answer = random.choice(facts)
    truth_game[ctx.author.id] = answer

    await ctx.send(f"🦊 Правда или ложь?\n{fact}\n\n!ответ правда / !ответ ложь")

@bot.command()
async def ответ(ctx, guess):
    correct = truth_game.get(ctx.author.id)

    if correct is None:
        await ctx.send("Сначала напиши !правда")
        return

    user_answer = guess.lower() == "правда"

    if user_answer == correct:
        await ctx.send(random.choice(["✨ Верно", "🦊 Да", "🌸 Правильно"]))
    else:
        await ctx.send(random.choice(["❌ Неверно", "🦊 Нет", "🌸 Ошибка"]))

    truth_game.pop(ctx.author.id, None)

# =====================
# 🧠 ON_MESSAGE (ИСПРАВЛЕН ДУБЛЬ)
# =====================
@bot.event
async def on_message(message):

    if message.author.bot:
        return

    now = datetime.datetime.now()

    # ❗ защита от дублей (ВАЖНО)
    last = last_messages.get(message.author.id)
    if last and (now - last).total_seconds() < 2:
        return
    last_messages[message.author.id] = now

    text = message.content.lower()
    user_memory[message.author.id] = text

    if message.author.id not in hunger:
        hunger[message.author.id] = 50

    hunger[message.author.id] = min(100, hunger[message.author.id] + random.randint(0, 1))
    state = hunger_state(hunger[message.author.id])

    response = None

    if "привет" in text:
        response = "Привет... я рада что ты здесь"
    elif "как дела" in text:
        response = "Я спокойна... а ты?"

    elif "грустно" in text:
        response = "Я рядом..."

    elif "кто ты" in text:
        response = "Я Сенко..."

    # реакция голода
    if response:
        if state == "hungry":
            response += "\n…я немного голодна"
        elif state == "critical":
            response += "\n🦊 мне нужно поесть..."
        elif state == "full":
            response += "\n✨ я сытая"

        await message.channel.send(response)

    await bot.process_commands(message)

# =====================
# КОМАНДЫ
# =====================
@bot.command()
async def память(ctx):
    await ctx.send(user_memory.get(ctx.author.id, "Пусто"))

@bot.command()
async def время(ctx):
    await ctx.send(datetime.datetime.now().strftime("%H:%M:%S"))

@bot.command()
async def помощь(ctx):
    await ctx.send("!правда !покормить !время !память !эмоция")

# =====================
# ЗАПУСК
# =====================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(DISCORD_TOKEN)
