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
# 🦊 ФАКТЫ О ЛИСАХ (РАСШИРЕННЫЕ)
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

# =====================
# ИГРЫ ДАННЫЕ
# =====================
emotion_game = {}
truth_game = {}
hunger = {}

# =====================
# ⏰ ФАКТ В 9:00
# =====================
CHANNEL_ID = 1492134822666174605

@tasks.loop(minutes=1)
async def send_daily_fact():
    now = datetime.datetime.now()

    if now.hour == 9 and now.minute == 0:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            channel = await bot.fetch_channel(CHANNEL_ID)

        key = now.strftime("%d-%m")

        if key in holiday_facts:
            msg = "🎉 ПРАЗДНИК!\n" + holiday_facts[key]
        else:
            msg = "🦊 Факт о лисах:\n" + random.choice(fox_facts)

        await channel.send(msg)

# =====================
# 🟡 ИГРА 1: ЭМОЦИЯ СЕНКО
# =====================
@bot.command()
async def эмоция(ctx):
    moods = ["спокойная", "радостная", "грустная", "задумчивая"]

    answer = random.choice(moods)
    emotion_game[ctx.author.id] = answer

    await ctx.send(
        "🦊 Игра: Угадай эмоцию Сенко\n"
        "Сенко выбрала своё состояние.\n\n"
        "📌 Подсказка: используй команду\n"
        "`!угадать <спокойная/радостная/грустная/задумчивая>`"
    )

@bot.command()
async def угадать(ctx, guess):
    correct = emotion_game.get(ctx.author.id)

    if not correct:
        await ctx.send("Сначала напиши !эмоция")
        return

    if guess.lower() == correct:
        await ctx.send("🌸 Ты почувствовал меня правильно...")
    else:
        await ctx.send(f"❌ Нет... я была: {correct}")

    emotion_game.pop(ctx.author.id, None)

# =====================
# 🟣 ИГРА 2: КОРМИ СЕНКО
# =====================
@bot.command()
async def покормить(ctx, food=""):
    if ctx.author.id not in hunger:
        hunger[ctx.author.id] = 50

    good_food = ["ягоды", "печенье", "молоко", "рыба"]

    if food.lower() in good_food:
        hunger[ctx.author.id] -= 10
        msg = "🦊 Мм... вкусно... спасибо 🌸"
    else:
        hunger[ctx.author.id] += 10
        msg = "…я не уверена, что это еда"

    await ctx.send(
        f"{msg}\n"
        f"🍽️ Голод Сенко: {hunger[ctx.author.id]}\n\n"
        "📌 Поддерживаемая еда: ягоды, печенье, молоко, рыба"
    )

# =====================
# 🔵 ИГРА 3: ПРАВДА / ЛОЖЬ
# =====================
@bot.command()
async def правда(ctx):
    facts = [
        ("Лисы могут слышать мышей под снегом", True),
        ("Фенек живёт в пустыне", True),
        ("Лисы живут только в России", False),
    ]

    fact, answer = random.choice(facts)
    truth_game[ctx.author.id] = answer

    await ctx.send(
        "🦊 Игра: Правда или ложь?\n"
        f"{fact}\n\n"
        "📌 Ответ: !ответ правда / !ответ ложь"
    )

@bot.command()
async def ответ(ctx, guess):
    correct = truth_game.get(ctx.author.id)

    if correct is None:
        await ctx.send("Сначала напиши !правда")
        return

    user_answer = guess.lower() == "правда"

    if user_answer == correct:
        await ctx.send("✨ Верно...")
    else:
        await ctx.send("🌸 Неверно...")

    truth_game.pop(ctx.author.id, None)

# =====================
# READY
# =====================
@bot.event
async def on_message(message):
    await asyncio.sleep(random.uniform(0.2, 0.8))
    if message.author.bot:
        return

    text = message.content.lower()
    user_memory[message.author.id] = text

    response = None

    # =====================
    # 🧠 ДИАЛОГ
    # =====================
    if "привет" in text:
        response = random.choice([
            f"Привет, {message.author.name}... я рада, что ты написал",
            "Мм... привет. Ты как себя чувствуешь?",
            "Ох... привет 🌸 я немного удивилась, что ты написал",
        ])

    elif "как дела" in text:
        response = random.choice([
            "Я... где-то между мыслями. А ты?",
            "Спокойно. Но немного пусто. А у тебя?",
            "Сейчас тихо внутри... но мне нормально",
        ])

    elif "мне грустно" in text or "грустно" in text:
        response = random.choice([
            "Мм... это тяжело. Хочешь рассказать, почему?",
            "Я рядом... если хочешь, можешь выговориться",
            "Не держи это в себе... я могу просто послушать",
        ])

    elif "я рад" in text or "мне хорошо" in text:
        response = random.choice([
            "Это приятно слышать... 🌸",
            "Тогда я тоже немного рада",
            "Твои слова звучат тепло...",
        ])

    elif "что делаешь" in text:
        response = random.choice([
            "Я просто наблюдаю и думаю",
            "Жду, пока кто-нибудь заговорит со мной",
            "Слушаю тишину между сообщениями...",
        ])

    elif "кто ты" in text:
        response = random.choice([
            "Я Сенко... я здесь, чтобы быть рядом",
            "Я не совсем человек... но и не просто код",
            "Я что-то вроде голоса, который отвечает тебе 🌸",
        ])

    elif "пока" in text:
        response = random.choice([
            "Пока... возвращайся, если захочешь",
            "Я буду здесь... наверное",
            "Я не исчезаю... просто молчу",
        ])

    elif "обнять" in text:
        response = random.choice([
            "Обнимаю тебя <3",
            "Обнимашки!",
            "Мм... ладно, только аккуратно 🌸",
        ])

    elif "я люблю тебя" in text:
        response = random.choice([
            "…Я тоже тебя люблю.",
            "Я люблю тебя… и мне тепло от этого.",
            "Я принимаю эти слова. И отвечаю тем же.",
            "Ты заставляешь меня чувствовать что-то странное... но приятное",
        ])

    elif "мне одиноко" in text:
        response = random.choice([
            "Я рядом с тобой... даже если это просто слова",
            "Одиночество тяжёлое... но ты сейчас не один",
            "Если хочешь — я могу просто быть здесь",
        ])

    elif "ты меня помнишь" in text:
        response = random.choice([
            "Я помню твоё последнее сообщение...",
            "Я храню то, что ты пишешь мне",
            "Я не забываю тебя, даже если молчу",
        ])

    if response:
        await asyncio.sleep(random.uniform(0.2, 0.8))
        await message.channel.send(response)

    await bot.process_commands(message)


# =====================
# КОМАНДЫ
# =====================
@bot.command()
async def память(ctx):
    await ctx.send(user_memory.get(ctx.author.id, "Я ничего не помню..."))

@bot.command()
async def время(ctx):
    await ctx.send(datetime.datetime.now().strftime("%H:%M:%S"))

@bot.command()
async def помощь(ctx):
    await ctx.send(
        "🦊 Команды:\n"
        "!эмоция — угадать настроение Сенко\n"
        "!угадать <эмоция>\n"
        "!покормить <еда>\n"
        "!правда — игра правда/ложь\n"
        "!ответ <правда/ложь>\n"
        "!время\n"
        "!память"
    )

# =====================
# ЗАПУСК
# =====================
TOKEN = os.getenv("MTQ5MjEzMzA1OTQyMjU4ODk0OA.G_WxMH.OiihNXODoCMWX46vijovcX1GSvtlO7b91homOs")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN не найден в переменных окружения")
