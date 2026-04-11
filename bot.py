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
    "14-02": "День любви 💕 — лисы создают пары на жизнь.",
    "08-03": "Весна 🌸 — лисы активнее.",
    "31-10": "Хэллоуин 👻 — духи леса.",
    "01-11": "🦊 ДЕНЬ ЛИС — праздник лис!",
}

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
# 🔵 ПРАВДА / ЛОЖЬ
# =====================
@bot.command()
async def правда(ctx):

    facts = [
        ("Лисы могут слышать мышей под снегом", True),
        ("Фенек живёт в пустыне Сахара", True),
        ("Лисы живут только в России", False),
        ("Лисы могут прыгать почти на 2 метра вверх", True),
        ("Лисы — это кошачьи животные", False),
        ("Арктическая лиса меняет цвет шерсти зимой", True),
        ("Лисы не умеют издавать звуки", False),
        ("Лисы могут запоминать места с едой", True),
        ("Все лисы живут в лесах", False),
        ("Фенек имеет очень большие уши для охлаждения", True),
        ("Лисы — полностью ночные животные", False),
        ("Лисы иногда притворяются мёртвыми", True),
        ("Лисы питаются только мясом", False),
        ("Лисы умеют лазить по деревьям", True),
        ("Лисы живут до 30 лет в дикой природе", False),
        ("Лисы могут узнавать человеческие лица", True),
        ("Лисы используют более 20 звуков для общения", True),
        ("Лисы — родственники медведей", False),
        ("Лисы могут выживать в городах", True),
        ("Лисы всегда охотятся в одиночку", True),
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

    user_answer = guess.lower().strip() == "правда"

    if user_answer == correct:
        responses = [
            "✨ Верно...",
            "🦊 Да, это правда...",
            "🌸 Ты хорошо чувствуешь лисий мир...",
        ]
    else:
        responses = [
            "🌸 Неверно...",
            "🦊 Нет, это было иначе...",
            "…ты почти угадал(а)",
        ]

    await ctx.send(random.choice(responses))

    truth_game.pop(ctx.author.id, None)
# =====================
# 🟡 ЭМОЦИЯ СЕНКО
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
# 🧠 ОТВЕТЫ В ЧАТЕ
# =====================
last_messages = {}  # защита от дублей

@bot.event
async def on_message(message):
    await asyncio.sleep(random.uniform(0.2, 0.6))

    # ❗ игнорируем ботов сразу
    if message.author.bot:
        return

    # 💣 защита от двойных срабатываний
    now = datetime.datetime.now()
    last = last_messages.get(message.author.id)

    if last and (now - last).total_seconds() < 1.5:
        return

    last_messages[message.author.id] = now

    text = message.content.lower()
    user_memory[message.author.id] = text

    # =====================
    # 🍽️ ГОЛОД (мягкий рост)
    # =====================
    if message.author.id not in hunger:
        hunger[message.author.id] = 50

    hunger[message.author.id] += random.randint(0, 2)
    hunger[message.author.id] = min(100, hunger[message.author.id])

    h = hunger[message.author.id]
    state = hunger_state(h)

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

    # =====================
    # 🦊 РЕАКЦИЯ НА ГОЛОД
    # =====================
    if response:
        if state == "hungry":
            response += "\n…я немного голодна"
        elif state == "critical":
            response += "\n🦊 мне правда нужно поесть..."
        elif state == "full":
            response += "\n✨ я сытая..."

        await asyncio.sleep(random.uniform(0.2, 0.6))
        await message.channel.send(response)

    # ❗ ВАЖНО: команды должны работать всегда
    await bot.process_commands(message)

# =====================
# 📊 КОМАНДЫ
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
# 🔥 ЗАПУСК
# =====================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(DISCORD_TOKEN)
