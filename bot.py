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
]

# =====================
# 🎉 ПРАЗДНИКИ
# =====================
holiday_facts = {
    "01-01": "Новый год 🎆 — лисы становятся осторожнее зимой.",
    "14-02": "День любви 💕 — лисы создают пары на жизнь.",
    "08-03": "Весна 🌸 — лисы активнее.",
    "31-10": "Хэллоуин 👻 — духи леса.",
    "01-11": "🦊 ДЕНЬ ЛИС — праздник лис!",
}

# =====================
# ИГРОВЫЕ ДАННЫЕ
# =====================
emotion_game = {}
truth_game = {}

hunger = {}
last_hunger_tick = datetime.datetime.now()

food_list = ["ягоды", "печенье", "молоко", "рыба", "тофу"]

CHANNEL_ID = 1492134822666174605


# =====================
# 🧠 СОСТОЯНИЕ ГОЛОДА
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
# ⏳ АВТО-ГОЛОД
# =====================
@tasks.loop(minutes=30)
async def hunger_tick():
    global last_hunger_tick

    now = datetime.datetime.now()

    if (now - last_hunger_tick).total_seconds() > random.randint(3600, 7200):

        for uid in hunger:
            hunger[uid] += random.randint(5, 15)
            hunger[uid] = min(100, hunger[uid])

        last_hunger_tick = now


# =====================
# 🟡 КОРМЛЕНИЕ
# =====================
@bot.command()
async def покормить(ctx, *, food=""):
    if ctx.author.id not in hunger:
        hunger[ctx.author.id] = 50

    food = food.lower().strip()

    if food in food_list:
        hunger[ctx.author.id] -= 20
        msg = "🦊 Мм... вкусно... спасибо 🌸"
    else:
        hunger[ctx.author.id] += 10
        msg = "…я не уверена, что это еда"

    hunger[ctx.author.id] = max(0, min(100, hunger[ctx.author.id]))

    state = hunger_state(hunger[ctx.author.id])

    extra = ""
    if state == "full":
        extra = "\n✨ Спасибо... я сытая."
    elif state == "hungry":
        extra = "\n…я немного голодна"
    elif state == "critical":
        extra = "\n🦊 мне правда нужно поесть..."

    await ctx.send(
        f"{msg}{extra}\n"
        f"🍽️ Голод: {hunger[ctx.author.id]}\n"
        f"📌 Еда: {', '.join(food_list)}"
    )


# =====================
# 🧠 ОТВЕТЫ В ЧАТЕ
# =====================
@bot.event
async def on_message(message):
    await asyncio.sleep(random.uniform(0.2, 0.6))

    if message.author.bot:
        return

    text = message.content.lower()
    user_memory[message.author.id] = text

    global last_hunger_tick

    # авто-рост голода (мягкий)
    if message.author.id in hunger:
        hunger[message.author.id] += random.randint(0, 2)
        hunger[message.author.id] = min(100, hunger[message.author.id])

    response = None
    h = hunger.get(message.author.id, 50)
    state = hunger_state(h)

    # =====================
    # 🧠 ДИАЛОГ + ВЛИЯНИЕ ГОЛОДА
    # =====================
    if "привет" in text:
        response = "Привет..."

    elif "грустно" in text:
        response = "Я рядом..."

    elif "что делаешь" in text:
        response = "Жду..."

    # 💥 голод влияет на настроение
    if state == "hungry":
        response = "…я немного голодна"
    elif state == "critical":
        response = "🦊 мне правда нужно поесть..."

    if response:
        await message.channel.send(response)

    await bot.process_commands(message)


# =====================
# 📊 КОМАНДЫ
# =====================
@bot.command()
async def память(ctx):
    await ctx.send(user_memory.get(ctx.author.id, "Пусто..."))

@bot.command()
async def время(ctx):
    await ctx.send(datetime.datetime.now().strftime("%H:%M:%S"))


# =====================
# 🚀 READY
# =====================
@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")
    hunger_tick.start()


# =====================
# 🔥 ЗАПУСК
# =====================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(DISCORD_TOKEN)
