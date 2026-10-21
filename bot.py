"""Senko 3.0: Discord slash commands, shop UI, relationships, chat and safe persistence.

Keeps data.json keys from Senko 2.0 and preserves legacy ! commands during transition.
Configure DISCORD_TOKEN; optionally configure SENKO_GUILD_ID, SENKO_BIND_ALLOWED_USER_ID,
OPENAI_API_KEY and OPENAI_MODEL in the hosting panel / .env file.
"""
from __future__ import annotations

import asyncio
import copy
import datetime as dt
import json
import logging
import os
import random
import re
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

CHANNEL_ID = int(os.getenv("SENKO_CHANNEL_ID", "1492134822666174605"))
CHAT_CHANNEL_ID = int(os.getenv("SENKO_CHAT_CHANNEL_ID", str(CHANNEL_ID)))
GUILD_ID_RAW = os.getenv("SENKO_GUILD_ID", "").strip()
BIND_ALLOWED_USER_ID = int(os.getenv("SENKO_BIND_ALLOWED_USER_ID", "0") or "0")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini").strip() or "gpt-5-mini"
CHAT_USER_COOLDOWN_SECONDS = 8
FOX_COOLDOWN_MINUTES = 30
FOX_ACTION_CHANCE = 0.25
DATA_FILE = Path(os.getenv("SENKO_DATA_FILE", "data.json"))
BACKUP_DIR = Path(os.getenv("SENKO_BACKUP_DIR", "backups"))
SCHEMA_VERSION = 3
MAX_CHAT_HISTORY = 10

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("senko")

# -----------------------------------------------------------------------------
# Game data / personality
# -----------------------------------------------------------------------------
ITEMS = {
    "Common": ["🌲 Шишка", "🍃 Листик", "🪨 Камушек", "🍄 Гриб"],
    "Rare": ["🫐 Черника", "🥚 Яйцо птицы", "🗝️ Ключ", "🍀 Клевер"],
    "Mythical": ["💎 Кристалл", "👑 Корона", "🌟 Пыль", "🦊 Золотая лиса"],
}
SHOP_ITEMS = {
    "🍪 Печенье": 10,
    "🌸 Цветок": 25,
    "🎀 Лента": 50,
    "💎 Маленький кристалл": 100,
}
FOOD_LIST = ["ягоды", "печенье", "молоко", "рыба", "тофу", "мясо", "хлеб", "грибы", "яблоко"]

MOODS = {
    "игривое": ["Я прыгаю вокруг хвоста!", "Где мячик?", "Тяв! Погнали бегать!"],
    "сонное": ["Глаза закрываются...", "Хвост такой мягкий...", "Зеееев..."],
    "задумчивое": ["Смотрю на облака...", "Почему люди не тявкают?", "Лес сегодня тихий..."],
    "голодное": ["В животе урчит...", "Где ягоды?", "Миска пустая..."],
    "одинокое": ["Так тихо... не с кем играть.", "Скучаю по общению.", "Сижу в уголке."],
}
SENKO_MOODS = {
    "заботливое": ["Я рядом. Давай немного передохнём. 🦊", "Не торопись — шаг за шагом всё получится. 🌸"],
    "радостное": ["У-ху! Вот это новости! ✨", "Хвостик так и подпрыгивает от радости! 🦊"],
    "сонное": ["М-м-м... ещё пять минут... 💤", "Зеееев... давай сегодня без спешки. 🌙"],
    "игривое": ["Хи-хи! А ну-ка, попробуй меня поймать! 🐾", "Ой, кажется, я придумала маленькую шалость! ✨"],
}
MOOD_CHOICES = [app_commands.Choice(name=x, value=x) for x in SENKO_MOODS] + [app_commands.Choice(name="Показать текущее", value="текущее")] 

FOX_FACTS = [
    "Лисы обладают очень острым слухом.",
    "Фенек — самая маленькая разновидность лис.",
    "У лис вертикальные зрачки.",
    "Лисы используют хвост для баланса.",
    "В японском фольклоре кицунэ — магические лисы.",
]
TRUTH_OR_DARE_FACTS = [
    ("Лисы обладают острым слухом", True),
    ("Фенек — самая крупная лиса в мире", False),
    ("Лисы используют хвост для баланса", True),
    ("У всех лис зрачки круглые", False),
]
FOX_ACTIONS = [
    "🦊 *Лиса свернулась клубочком.*", "✨ *Лиса чистит свою шубку.*", "🐾 *Лиса оставила отпечаток лапки.*",
    "📦 *Лиса залезла в коробку.*", "👂 *Ушки лисы дернулись.*", "🌿 *Лиса выглянула из кустов.*",
    "💤 *Лиса сладко зевнула.*", "🍃 *Лиса гоняется за упавшим листиком.*",
]
RANDOM_SCENES = [
    ("comfort", "🦊 *Сенко тихонько садится рядом и протягивает лапку.* Всё наладится — не обязательно справляться со всем сразу."),
    ("happy", "✨ *Сенко подпрыгивает на месте.* Кажется, самое время устроить маленький праздник!"),
    ("playful", "🐾 *Сенко выглядывает из-за уголка.* Ну что, сыграем во что-нибудь?"),
    ("sleepy", "💤 *Сенко сладко зевает и сворачивается клубочком.* Пожалуй, небольшой перерыв никому не повредит."),
]
FOX_MEDIA = {
    "обычная": [],
    "радость": [
        "https://media.tenor.com/AnGdBUdReMsAAAAM/senko-discord.gif",
        "https://i.pinimg.com/originals/5c/a5/41/5ca5416c427103f8c5a040ad142327d2.gif",
    ],
    "смущение": [], "сонная": [], "удивление": [], "обида": [], "танец": [],
    "грусть": [
        "https://media.tenor.com/HoSYZR66fsQAAAAM/senko-light.gif",
        "https://media.tenor.com/Lsxo6rTUoSYAAAAM/senko-sewayaki-kitsune-no-senko-san.gif",
    ],
    "gif": [],
}
MEDIA_FALLBACKS = {
    "смущение": ["радость", "обычная"], "сонная": ["грусть", "обычная"],
    "удивление": ["радость", "обычная"], "обида": ["грусть", "обычная"],
    "танец": ["радость", "обычная"], "грусть": ["радость", "обычная"],
    "обычная": ["радость", "грусть"],
}

# -----------------------------------------------------------------------------
# Persistent state. Legacy keys remain under their original names.
# -----------------------------------------------------------------------------
inventories: dict[int, list] = {}
balances: dict[int, int] = {}
hunger: dict[int, int] = {}
user_memory: dict[int, str] = {}
first_seen: dict[int, str] = {}
message_counts: dict[int, int] = {}
last_messages: dict[int, dt.datetime] = {}
personal_memories: dict[int, list[dict[str, Any]]] = {}
group_memories: dict[str, list[dict[str, Any]]] = {}
profiles: dict[str, dict[str, Any]] = {}
settings: dict[str, Any] = {
    "autonomous_enabled": True,
    "random_events_enabled": True,
    "daily_fact_enabled": True,
    "event_cooldown_minutes": 45,
}
current_mood = "заботливое"
current_mood_changed_at: Optional[str] = None
last_event_by_channel: dict[str, str] = {}
media_status: dict[str, dict[str, Any]] = {}
truth_game: dict[int, bool] = {}
mood_game: dict[int, str] = {}
number_games: dict[str, dict[str, Any]] = {}
quiz_games: dict[str, dict[str, Any]] = {}
searching_users: set[int] = set()
last_fact_date: Optional[str] = None
last_fox_action: Optional[dt.datetime] = None

_persisted_root: dict[str, Any] = {}
memory_write_allowed = True
memory_load_error: Optional[str] = None
backup_created = False
chat_history: dict[str, list[dict[str, str]]] = {}  # In-RAM only; chat transcripts aren't saved to data.json.
last_chat_reply: dict[int, dt.datetime] = {}
commands_synced = False

# -----------------------------------------------------------------------------
# Storage / safe upgrade from Senko 2.0 data.json
# -----------------------------------------------------------------------------
def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def parse_dt(value: Any) -> Optional[dt.datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
        if parsed.tzinfo:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
    except (ValueError, TypeError, OverflowError):
        return None


def load_memory() -> dict[str, Any]:
    global memory_write_allowed, memory_load_error, _persisted_root
    if not DATA_FILE.exists():
        memory_write_allowed, memory_load_error, _persisted_root = True, None, {}
        log.info("No data.json found; new data will be written after the first successful action.")
        return {}
    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("Корневое значение JSON должно быть объектом.")
        version = data.get("senko_schema_version", 1)
        if not isinstance(version, int):
            raise ValueError("senko_schema_version должен быть числом.")
        if version > SCHEMA_VERSION:
            memory_write_allowed = False
            memory_load_error = f"Схема данных ({version}) новее поддерживаемой ({SCHEMA_VERSION}); запись отключена."
        else:
            memory_write_allowed, memory_load_error = True, None
        _persisted_root = copy.deepcopy(data)
        return data
    except (OSError, json.JSONDecodeError, ValueError) as error:
        memory_write_allowed, memory_load_error, _persisted_root = False, str(error), {}
        log.exception("Не удалось безопасно загрузить %s; запись отключена.", DATA_FILE)
        return {}


def make_backup() -> None:
    global backup_created
    if backup_created or not DATA_FILE.exists() or memory_load_error:
        return
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(DATA_FILE, BACKUP_DIR / f"{DATA_FILE.stem}_{stamp}{DATA_FILE.suffix}.bak")
        backup_created = True
        log.info("Created data backup in %s", BACKUP_DIR)
    except OSError:
        log.exception("Не удалось создать резервную копию data.json")


def int_map(raw: Any, predicate) -> dict[int, Any]:
    result = {}
    if not isinstance(raw, dict):
        return result
    for key, value in raw.items():
        try:
            uid = int(key)
        except (ValueError, TypeError):
            continue
        if predicate(value):
            result[uid] = value
    return result


def ensure_profile(uid: int) -> dict[str, Any]:
    profile = profiles.get(str(uid))
    if not isinstance(profile, dict):
        profile = {}
        profiles[str(uid)] = profile
    try:
        profile["relationship_points"] = max(0, int(profile.get("relationship_points", 0) or 0))
    except (TypeError, ValueError):
        profile["relationship_points"] = 0
    if not isinstance(profile.get("achievements"), list): profile["achievements"] = []
    if not isinstance(profile.get("preferences"), dict): profile["preferences"] = {}
    if not isinstance(profile.get("last_awards"), dict): profile["last_awards"] = {}
    profile["memory_enabled"] = bool(profile.get("memory_enabled", True))
    profile["preferences"].setdefault("auto_reactions", True)
    profile["preferences"].setdefault("preferred_media", "")
    return profile


def restore_memory() -> None:
    global inventories, balances, hunger, user_memory, first_seen, message_counts, last_messages
    global personal_memories, group_memories, profiles, settings, current_mood, current_mood_changed_at
    global last_event_by_channel, media_status, truth_game, mood_game, number_games, quiz_games
    global last_fact_date, last_fox_action
    data = load_memory()
    inventories = int_map(data.get("inventories", {}), lambda v: isinstance(v, list))
    balances = {uid: int(value) for uid, value in int_map(data.get("balances", {}), lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0).items()}
    hunger = {uid: max(0, min(100, int(value))) for uid, value in int_map(data.get("hunger", {}), lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)).items()}
    user_memory = int_map(data.get("user_memory", {}), lambda v: isinstance(v, str))
    first_seen = int_map(data.get("first_seen", {}), lambda v: isinstance(v, str))
    message_counts = int_map(data.get("message_counts", {}), lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 0)
    last_messages = {}
    for key, value in (data.get("last_messages", {}) if isinstance(data.get("last_messages", {}), dict) else {}).items():
        try: uid = int(key)
        except (ValueError, TypeError): continue
        parsed = parse_dt(value)
        if parsed: last_messages[uid] = parsed
    personal_memories = {}
    raw_personal = data.get("personal_memories", {})
    if isinstance(raw_personal, dict):
        for key, entries in raw_personal.items():
            try: uid = int(key)
            except (ValueError, TypeError): continue
            if isinstance(entries, list):
                personal_memories[uid] = [x for x in entries if isinstance(x, dict) and isinstance(x.get("text"), str)][-100:]
    raw_groups = data.get("group_memories", {})
    group_memories = {str(k): [x for x in v if isinstance(x, dict) and isinstance(x.get("text"), str)][-100:]
                      for k, v in raw_groups.items() if isinstance(raw_groups, dict) and isinstance(v, list)} if isinstance(raw_groups, dict) else {}
    raw_profiles = data.get("profiles", {})
    profiles = raw_profiles if isinstance(raw_profiles, dict) else {}
    for key in list(profiles):
        try: int(key)
        except (ValueError, TypeError): profiles.pop(key, None)
    for key in list(profiles): ensure_profile(int(key))
    raw_settings = data.get("senko_settings", {})
    if isinstance(raw_settings, dict): settings.update(raw_settings)
    settings.setdefault("autonomous_enabled", True)
    settings.setdefault("random_events_enabled", True)
    settings.setdefault("daily_fact_enabled", True)
    settings.setdefault("event_cooldown_minutes", 45)
    saved_mood = data.get("current_mood", "заботливое")
    current_mood = saved_mood if saved_mood in SENKO_MOODS else "заботливое"
    current_mood_changed_at = data.get("current_mood_changed_at") if isinstance(data.get("current_mood_changed_at"), str) else None
    last_event_by_channel = data.get("last_event_by_channel", {}) if isinstance(data.get("last_event_by_channel", {}), dict) else {}
    media_status = data.get("media_status", {}) if isinstance(data.get("media_status", {}), dict) else {}
    truth_game, mood_game, number_games, quiz_games = {}, {}, {}, {}
    last_fact_date = data.get("last_fact_date") if isinstance(data.get("last_fact_date"), str) else None
    last_fox_action = parse_dt(data.get("last_fox_action"))
    if DATA_FILE.exists() and memory_load_error is None: make_backup()


def save_memory() -> bool:
    global _persisted_root
    if not memory_write_allowed:
        log.error("Save skipped to protect existing data: %s", memory_load_error or "write disabled")
        return False
    data = copy.deepcopy(_persisted_root) if isinstance(_persisted_root, dict) else {}
    # Update known keys while retaining any unknown legacy/plugin keys.
    data.update({
        "senko_schema_version": SCHEMA_VERSION,
        "inventories": inventories, "balances": balances, "hunger": hunger,
        "user_memory": user_memory, "first_seen": first_seen, "message_counts": message_counts,
        "last_messages": {str(uid): value.isoformat() for uid, value in last_messages.items()},
        "last_fact_date": last_fact_date, "last_fox_action": last_fox_action.isoformat() if last_fox_action else None,
        "personal_memories": {str(uid): entries for uid, entries in personal_memories.items()},
        "group_memories": group_memories, "profiles": profiles, "senko_settings": settings,
        "current_mood": current_mood, "current_mood_changed_at": current_mood_changed_at,
        "last_event_by_channel": last_event_by_channel, "media_status": media_status,
    })
    try:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f"{DATA_FILE.name}.", suffix=".tmp", dir=str(DATA_FILE.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, DATA_FILE)
            _persisted_root = copy.deepcopy(data)
            return True
        finally:
            if os.path.exists(temporary): os.remove(temporary)
    except (OSError, TypeError, ValueError):
        log.exception("Ошибка сохранения data.json")
        return False


restore_memory()

# -----------------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------------
def get_balance(uid: int) -> int: return int(balances.get(uid, 0))
def get_inventory(uid: int) -> list: return inventories.setdefault(uid, [])
def hunger_state(value: int) -> str:
    if value <= 15: return "сытая ✨"
    if value >= 85: return "очень голодная 🆘"
    return "в норме 👍"
def relationship_level(points: int) -> tuple[str, int]:
    if points >= 150: return "Особенный человек", 4
    if points >= 75: return "Близкий друг", 3
    if points >= 25: return "Друг", 2
    return "Знакомый", 1

def award_relationship(uid: int, points: int = 1, source: str = "interaction", daily_limit: int = 10) -> int:
    profile = ensure_profile(uid)
    today = dt.datetime.now().strftime("%Y-%m-%d")
    records = profile["last_awards"]
    record = records.get(source, {})
    if not isinstance(record, dict) or record.get("date") != today: record = {"date": today, "count": 0}
    count = max(0, int(record.get("count", 0) or 0))
    granted = min(max(0, int(points)), max(0, daily_limit - count))
    profile["relationship_points"] += granted
    record["count"] = count + granted
    records[source] = record
    return granted

def award_achievement(uid: int, name: str) -> bool:
    achievements = ensure_profile(uid)["achievements"]
    if name in achievements: return False
    achievements.append(name)
    return True

def set_mood(mood: str) -> None:
    global current_mood, current_mood_changed_at
    if mood in SENKO_MOODS and mood != current_mood:
        current_mood = mood
        current_mood_changed_at = now_iso()

def infer_mood(text: str) -> Optional[str]:
    text = text.lower()
    if any(x in text for x in ("грустно", "плохо", "тяжело", "устал", "устала", "поддержи", "грустный")): return "заботливое"
    if any(x in text for x in ("ура", "получилось", "победил", "победила", "спасибо", "классно", "ураа")): return "радостное"
    if any(x in text for x in ("поиграем", "игра", "шутка", "ахаха", "хаха")): return "игривое"
    if any(x in text for x in ("спокойной ночи", "спать", "сонный", "сонная")): return "сонное"
    return None

def is_admin_member(member: discord.abc.User) -> bool:
    return isinstance(member, discord.Member) and member.guild_permissions.manage_guild

def all_media_urls(category: Optional[str] = None) -> list[str]:
    if category == "gif":
        return list(dict.fromkeys(url for name, urls in FOX_MEDIA.items() if name != "gif" for url in urls
                                  if isinstance(url, str) and url.lower().split("?", 1)[0].endswith(".gif")))
    if category is None:
        return list(dict.fromkeys(url for urls in FOX_MEDIA.values() for url in urls if isinstance(url, str) and url))
    return [url for url in FOX_MEDIA.get(category, []) if isinstance(url, str) and url]

def media_candidates(category: str) -> list[str]:
    candidates = all_media_urls(category)
    for fallback in MEDIA_FALLBACKS.get(category, []): candidates.extend(all_media_urls(fallback))
    candidates = list(dict.fromkeys(candidates))
    healthy = [url for url in candidates if media_status.get(url, {}).get("ok") is not False]
    return healthy or candidates

def shop_embed(uid: int) -> discord.Embed:
    embed = discord.Embed(title="🏪 Лавка Сенкосан", description="Выбирай угощение или подарок — нажми кнопку под магазином! 🦊", color=0xFF8C00)
    embed.add_field(name="💰 Твой баланс", value=f"**{get_balance(uid)} 🍃**", inline=False)
    for item, price in SHOP_ITEMS.items(): embed.add_field(name=item, value=f"Цена: **{price} 🍃**", inline=True)
    embed.set_footer(text="Меню персональное; покупки списываются с твоего баланса.")
    return embed

def inventory_embed(uid: int) -> discord.Embed:
    items = get_inventory(uid)
    embed = discord.Embed(title=f"🎒 Рюкзак — {getattr(bot.get_user(uid), 'display_name', 'лисёнок')}", color=0xFF8C00)
    embed.description = "\n".join(f"• {x}" for x in items[-20:]) if items else "Пока пусто. Загляни в магазин или отправься на поиск!"
    if len(items) > 20: embed.description += f"\n…и ещё {len(items) - 20} предметов"
    embed.add_field(name="💰 Баланс", value=f"{get_balance(uid)} 🍃", inline=False)
    return embed

def profile_embed(uid: int, display_name: str) -> discord.Embed:
    profile = ensure_profile(uid)
    points = int(profile["relationship_points"])
    level_name, level_num = relationship_level(points)
    target = {1: 25, 2: 75, 3: 150}.get(level_num)
    progress = f"{points}/{target} очков до следующего уровня" if target else "Максимальный уровень доверия достигнут"
    first = first_seen.get(uid)
    first_parsed = parse_dt(first)
    since = first_parsed.strftime("%d.%m.%Y") if first_parsed else "ещё не записано"
    embed = discord.Embed(title=f"🦊 Ты и Сенко — {display_name}", description=f"**{level_name} · уровень {level_num}**\n{progress}", color=0xFF8C00)
    embed.add_field(name="🍃 Листики", value=str(get_balance(uid)), inline=True)
    embed.add_field(name="🎒 Предметов", value=str(len(inventories.get(uid, []))), inline=True)
    embed.add_field(name="🍡 Сытость Сенко", value=hunger_state(hunger.get(uid, 50)), inline=True)
    embed.add_field(name="💬 Сообщений замечено", value=str(message_counts.get(uid, 0)), inline=True)
    embed.add_field(name="🧠 Воспоминаний", value=str(len(personal_memories.get(uid, []))), inline=True)
    embed.add_field(name="🌸 Первое знакомство", value=since, inline=True)
    embed.add_field(name="🏅 Достижения", value="\n".join(f"• {x}" for x in profile["achievements"][-8:]) or "Пока нет", inline=False)
    embed.set_footer(text="Личные сведения видны только тебе в этом меню.")
    return embed

async def buy_item(uid: int, item: str) -> tuple[bool, str]:
    if item not in SHOP_ITEMS: return False, "Такого товара нет в магазине."
    price = SHOP_ITEMS[item]
    balance = get_balance(uid)
    if balance < price: return False, f"Не хватает {price - balance} 🍃. Отправься на поиск или сыграй в мини-игру."
    balances[uid] = balance - price
    get_inventory(uid).append(item)
    award_relationship(uid, 1, "shop", 3)
    save_memory()
    return True, f"Покупка успешна! Ты приобрёл **{item}** за **{price} 🍃**. Осталось: **{balances[uid]} 🍃**."

async def send_media_interaction(interaction: discord.Interaction, category: str) -> None:
    urls = media_candidates(category)
    if not urls:
        await interaction.response.send_message(f"🦊 Для категории «{category}» пока нет доступных медиа.", ephemeral=True)
        return
    embed = discord.Embed(title=f"🦊 Сенкосан — {category}", color=0xFF8C00)
    embed.set_image(url=random.choice(urls))
    await interaction.response.send_message(embed=embed)

async def check_media_url(session: aiohttp.ClientSession, url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        return {"ok": False, "status": None, "content_type": "invalid-url", "error": "invalid URL"}
    try:
        async with session.get(url, headers={"User-Agent": "SenkoBot/3.0 media-check"}, allow_redirects=True) as response:
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            prefix = await response.content.read(32)
            looks_image = content_type.startswith("image/") or prefix.startswith((b"GIF87a", b"GIF89a", b"\x89PNG", b"\xff\xd8\xff", b"RIFF"))
            ok = response.status < 400 and looks_image
            return {"ok": ok, "status": response.status, "content_type": content_type or "unknown",
                    "final_url": str(response.url), "checked_at": now_iso(),
                    "error": None if ok else "HTTP error or response is not a recognizable image"}
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as error:
        return {"ok": False, "status": None, "content_type": "unknown", "checked_at": now_iso(), "error": str(error)[:200]}

# -----------------------------------------------------------------------------
# Discord UI: shop buttons and help navigation
# -----------------------------------------------------------------------------
class ShopButton(discord.ui.Button):
    def __init__(self, item: str, row: int):
        self.item = item
        price = SHOP_ITEMS[item]
        label = f"Купить {item}" if len(item) < 40 else f"Купить за {price} 🍃"
        super().__init__(label=label[:80], style=discord.ButtonStyle.success, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: ShopView = self.view  # type: ignore[assignment]
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("Это персональный магазин. Открой `/магазин`, чтобы купить предметы со своего баланса.", ephemeral=True)
            return
        success, text = await buy_item(interaction.user.id, self.item)
        await interaction.response.send_message(("✅ " if success else "🦊 ") + text, ephemeral=True)
        if success and interaction.message:
            await interaction.message.edit(embed=shop_embed(view.owner_id), view=view)

class ShopView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        for index, item in enumerate(SHOP_ITEMS):
            self.add_item(ShopButton(item, index // 2))
        refresh = discord.ui.Button(label="Обновить баланс", emoji="🔄", style=discord.ButtonStyle.secondary, row=2)
        async def refresh_callback(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("Открой свой `/магазин`.", ephemeral=True)
                return
            await interaction.response.edit_message(embed=shop_embed(self.owner_id), view=self)
        refresh.callback = refresh_callback
        self.add_item(refresh)

class HelpView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        for label, emoji, key in [("Магазин", "🛍️", "shop"), ("Рюкзак", "🎒", "inventory"), ("Профиль", "💗", "profile"), ("Игры", "🎮", "games")]:
            button = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.primary)
            async def callback(interaction: discord.Interaction, destination: str = key) -> None:
                if interaction.user.id != self.owner_id:
                    await interaction.response.send_message("Открой своё меню через `/помощь`.", ephemeral=True)
                    return
                if destination == "shop": await interaction.response.edit_message(embed=shop_embed(self.owner_id), view=ShopView(self.owner_id))
                elif destination == "inventory": await interaction.response.edit_message(embed=inventory_embed(self.owner_id), view=NavigationView(self.owner_id))
                elif destination == "profile": await interaction.response.edit_message(embed=profile_embed(self.owner_id, interaction.user.display_name), view=NavigationView(self.owner_id))
                else:
                    embed = discord.Embed(title="🎮 Мини-игры", description="`/угадайчисло` — загадать число\n`/викторина` — вопрос дня\n`/эмоция` — угадать настроение\n`/правда` — правда или ложь", color=0xFF8C00)
                    await interaction.response.edit_message(embed=embed, view=NavigationView(self.owner_id))
            button.callback = callback
            self.add_item(button)

class NavigationView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        button = discord.ui.Button(label="Открыть магазин", emoji="🛍️", style=discord.ButtonStyle.success)
        async def shop_callback(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("Открой своё меню через `/помощь`.", ephemeral=True)
                return
            await interaction.response.edit_message(embed=shop_embed(self.owner_id), view=ShopView(self.owner_id))
        button.callback = shop_callback
        self.add_item(button)

class BindConfirmView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=45)
        self.owner_id = owner_id
        confirm = discord.ui.Button(label="Подтвердить сценку", style=discord.ButtonStyle.danger, emoji="🪢")
        cancel = discord.ui.Button(label="Отмена", style=discord.ButtonStyle.secondary)
        async def confirm_callback(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.owner_id or interaction.user.id != BIND_ALLOWED_USER_ID:
                await interaction.response.send_message("Это подтверждение не для тебя.", ephemeral=True)
                return
            points = ensure_profile(interaction.user.id)["relationship_points"]
            if relationship_level(points)[1] < 4:
                await interaction.response.send_message("Уровень доверия больше не достаточен для этой сценки.", ephemeral=True)
                return
            await interaction.response.send_message("🦊 Сценка подтверждена.", ephemeral=True)
            if interaction.channel:
                await interaction.channel.send("🦊 *В рамках вымышленной, добровольной сценки Сенко позволяет аккуратно закрепить декоративные ленты на своих рукавах, оставляя их свободными и легко снимаемыми.*\n*«Если захочу остановиться, сразу скажу. Договорились?»* 💛")
        async def cancel_callback(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("Это меню не для тебя.", ephemeral=True)
                return
            await interaction.response.edit_message(content="🦊 Хорошо, тогда оставим эту сценку на другой раз.", embed=None, view=None)
        confirm.callback = confirm_callback
        cancel.callback = cancel_callback
        self.add_item(confirm)
        self.add_item(cancel)

# -----------------------------------------------------------------------------
# Legacy prefix commands are retained during migration. Slash commands below are primary.
# -----------------------------------------------------------------------------
@bot.command(name="поиск")
@commands.cooldown(1, 10, commands.BucketType.user)
async def legacy_search(ctx: commands.Context):
    uid = ctx.author.id
    if uid in searching_users: return await ctx.send("🦊 Ты уже отправил меня на поиск! Подожди немного.")
    searching_users.add(uid)
    try:
        message = await ctx.send("🦊 *Лиса принюхивается и убегает в заросли...*")
        await asyncio.sleep(5)
        roll = random.random()
        rarity, reward = ("Mythical", 50) if roll < .1 else (("Rare", 20) if roll < .4 else ("Common", 5))
        item = random.choice(ITEMS[rarity])
        get_inventory(uid).append(item)
        balances[uid] = get_balance(uid) + reward
        award_relationship(uid, 2, "search", 8)
        unlocked = award_achievement(uid, "Первый поиск")
        save_memory()
        await message.edit(content=f"🦊 **Нашла!**\nПредмет: {item} (`{rarity}`)\nНаграда: `+{reward} 🍃`" + ("\n🏅 Достижение: Первый поиск!" if unlocked else ""))
    finally:
        searching_users.discard(uid)

@bot.command(name="рюкзак")
async def legacy_inventory(ctx: commands.Context): await ctx.send(embed=inventory_embed(ctx.author.id))

@bot.command(name="магазин")
async def legacy_shop(ctx: commands.Context): await ctx.send(embed=shop_embed(ctx.author.id), view=ShopView(ctx.author.id))

@bot.command(name="купить")
async def legacy_buy(ctx: commands.Context, *, item_name: str = ""):
    item = next((item for item in SHOP_ITEMS if item.lower() == item_name.strip().lower()), None)
    if item is None: return await ctx.send("🦊 Не знаю такого товара! Используй `/магазин`.")
    success, text = await buy_item(ctx.author.id, item)
    await ctx.send(("✅ " if success else "🦊 ") + text)

@bot.command(name="эмоция")
async def legacy_mood_game(ctx: commands.Context):
    mood = random.choice(list(MOODS))
    mood_game[ctx.author.id] = mood
    await ctx.send(f"🦊 Угадай настроение: *«{random.choice(MOODS[mood])}»*. Ответ: `!угадай {mood}` или `/угадай`.")

@bot.command(name="угадай")
async def legacy_guess(ctx: commands.Context, *, guess: str = ""):
    correct = mood_game.get(ctx.author.id)
    if correct is None: return await ctx.send("Сначала начни игру: `!эмоция` или `/эмоция`.")
    if guess.lower().strip() == correct:
        balances[ctx.author.id] = get_balance(ctx.author.id) + 10
        mood_game.pop(ctx.author.id, None)
        award_relationship(ctx.author.id, 3, "game", 9)
        award_achievement(ctx.author.id, "Первая победа в игре")
        save_memory()
        await ctx.send(f"✨ Верно! Мне {correct}. Награда: **+10 🍃**")
    else: await ctx.send("❌ Не-а! Попробуй ещё раз.")

@bot.command(name="покормить")
async def legacy_feed(ctx: commands.Context, *, food: str = ""):
    uid = ctx.author.id
    if uid not in hunger: hunger[uid] = 50
    if any(item in food.lower().strip() for item in FOOD_LIST):
        hunger[uid] = max(0, hunger[uid] - 35)
        award_relationship(uid, 2, "feed", 6)
        save_memory()
        await ctx.send(f"🦊 *Ням!* Теперь я {hunger_state(hunger[uid])}")
    else: await ctx.send("🦊 Я это не ем... Попробуй еду из списка `/покормить`.")

@bot.command(name="правда")
async def legacy_truth(ctx: commands.Context):
    fact, answer = random.choice(TRUTH_OR_DARE_FACTS)
    truth_game[ctx.author.id] = answer
    await ctx.send(f"🦊 **Правда или ложь?**\n> {fact}\n\nОтветь: `!ответ правда` или `!ответ ложь`.")

@bot.command(name="ответ")
async def legacy_answer(ctx: commands.Context, *, guess: str = ""):
    correct = truth_game.get(ctx.author.id)
    if correct is None: return await ctx.send("Сначала начни игру: `!правда` или `/правда`.")
    parsed = True if guess.lower().strip() in ("правда", "да", "true") else False if guess.lower().strip() in ("ложь", "нет", "false") else None
    if parsed is None: return await ctx.send("Ответь «правда» или «ложь».")
    truth_game.pop(ctx.author.id, None)
    if parsed == correct:
        balances[ctx.author.id] = get_balance(ctx.author.id) + 5
        award_relationship(ctx.author.id, 2, "game", 9)
        award_achievement(ctx.author.id, "Участник викторины")
        save_memory()
        await ctx.send("✨ Верно! +5 🍃")
    else: await ctx.send("❌ Неверный ответ!")

@bot.command(name="помощь", aliases=["help"])
async def legacy_help(ctx: commands.Context):
    embed = discord.Embed(title="🦊 Сенкосан 3.0", description="Открой `/помощь` для интерактивного меню слеш-команд.", color=0xFF8C00)
    await ctx.send(embed=embed, view=HelpView(ctx.author.id))

# -----------------------------------------------------------------------------
# Slash commands: these are registered natively with Discord.
# -----------------------------------------------------------------------------
@bot.tree.command(name="помощь", description="Открыть интерактивное меню Сенко")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(title="🦊 Senko 3.0 — главное меню", description="Выбирай раздел кнопками ниже. Все основные команды также доступны через `/`.", color=0xFF8C00)
    embed.add_field(name="🛍️ Магазин", value="Каталог, цены и покупка кнопками", inline=True)
    embed.add_field(name="🎒 Рюкзак", value="Твои предметы и баланс", inline=True)
    embed.add_field(name="💗 Профиль", value="Отношения, достижения и воспоминания", inline=True)
    embed.add_field(name="🎮 Игры", value="Угадайка и викторина", inline=True)
    await interaction.response.send_message(embed=embed, view=HelpView(interaction.user.id), ephemeral=True)

@bot.tree.command(name="магазин", description="Открыть магазин с личным балансом и кнопками покупки")
async def slash_shop(interaction: discord.Interaction):
    await interaction.response.send_message(embed=shop_embed(interaction.user.id), view=ShopView(interaction.user.id), ephemeral=True)

@bot.tree.command(name="баланс", description="Посмотреть свой баланс листиков")
async def slash_balance(interaction: discord.Interaction):
    await interaction.response.send_message(f"🍃 **Твой баланс: {get_balance(interaction.user.id)} листиков.**", ephemeral=True)

@bot.tree.command(name="купить", description="Купить предмет из магазина")
@app_commands.describe(item="Выбери предмет")
@app_commands.rename(item="товар")
@app_commands.choices(item=[app_commands.Choice(name=item, value=item) for item in SHOP_ITEMS])
async def slash_buy(interaction: discord.Interaction, item: app_commands.Choice[str]):
    success, text = await buy_item(interaction.user.id, item.value)
    await interaction.response.send_message(("✅ " if success else "🦊 ") + text, ephemeral=True)

@bot.tree.command(name="рюкзак", description="Посмотреть свои предметы и баланс")
async def slash_inventory(interaction: discord.Interaction):
    await interaction.response.send_message(embed=inventory_embed(interaction.user.id), ephemeral=True)

@bot.tree.command(name="поиск", description="Отправить Сенко на поиск предметов и листиков")
async def slash_search(interaction: discord.Interaction):
    uid = interaction.user.id
    if uid in searching_users:
        return await interaction.response.send_message("🦊 Я уже на поиске! Подожди немного.", ephemeral=True)
    searching_users.add(uid)
    await interaction.response.defer(thinking=True)
    try:
        await asyncio.sleep(5)
        roll = random.random()
        rarity, reward = ("Mythical", 50) if roll < .1 else (("Rare", 20) if roll < .4 else ("Common", 5))
        item = random.choice(ITEMS[rarity])
        get_inventory(uid).append(item)
        balances[uid] = get_balance(uid) + reward
        award_relationship(uid, 2, "search", 8)
        unlocked = award_achievement(uid, "Первый поиск")
        save_memory()
        await interaction.followup.send(f"🦊 **Нашла!**\nПредмет: {item} (`{rarity}`)\nНаграда: `+{reward} 🍃`" + ("\n🏅 Достижение: Первый поиск!" if unlocked else ""))
    finally:
        searching_users.discard(uid)

@bot.tree.command(name="эмоция", description="Начать игру: угадай настроение Сенко")
async def slash_mood_game(interaction: discord.Interaction):
    mood = random.choice(list(MOODS))
    mood_game[interaction.user.id] = mood
    await interaction.response.send_message(f"🦊 **Угадай настроение!**\nПодсказка: *«{random.choice(MOODS[mood])}»*\nВведи `/угадай` и укажи свой ответ.")

@bot.tree.command(name="угадай", description="Ответить в игре на угадывание настроения")
@app_commands.describe(guess="Название настроения, например игривое")
@app_commands.rename(guess="ответ")
async def slash_guess(interaction: discord.Interaction, guess: str):
    uid = interaction.user.id
    correct = mood_game.get(uid)
    if correct is None: return await interaction.response.send_message("Сначала начни игру командой `/эмоция`.", ephemeral=True)
    if guess.lower().strip() == correct:
        balances[uid] = get_balance(uid) + 10
        mood_game.pop(uid, None)
        award_relationship(uid, 3, "game", 9)
        unlocked = award_achievement(uid, "Первая победа в игре")
        save_memory()
        await interaction.response.send_message(f"✨ Верно! Мне {correct}. Награда: **+10 🍃**" + ("\n🏅 Достижение открыто!" if unlocked else ""))
    else: await interaction.response.send_message("❌ Не-а! Попробуй ещё раз.", ephemeral=True)

FOOD_CHOICES = [app_commands.Choice(name=x, value=x) for x in FOOD_LIST]
@bot.tree.command(name="покормить", description="Покормить Сенко выбранной едой")
@app_commands.rename(food="еда")
@app_commands.choices(food=FOOD_CHOICES)
async def slash_feed(interaction: discord.Interaction, food: app_commands.Choice[str]):
    uid = interaction.user.id
    if uid not in hunger: hunger[uid] = 50
    hunger[uid] = max(0, hunger[uid] - 35)
    award_relationship(uid, 2, "feed", 6)
    save_memory()
    await interaction.response.send_message(f"🦊 *Ням!* Ты угостил(а) меня: {food.value}. Теперь я {hunger_state(hunger[uid])}")

@bot.tree.command(name="правда", description="Начать игру «Правда или ложь»")
async def slash_truth(interaction: discord.Interaction):
    fact, answer = random.choice(TRUTH_OR_DARE_FACTS)
    truth_game[interaction.user.id] = answer
    await interaction.response.send_message(f"🦊 **Правда или ложь?**\n> {fact}\n\nОтветь через `/ответ`.")

@bot.tree.command(name="ответ", description="Ответить в игре «Правда или ложь»")
@app_commands.rename(answer="ответ")
@app_commands.choices(answer=[app_commands.Choice(name="Правда", value="правда"), app_commands.Choice(name="Ложь", value="ложь")])
async def slash_truth_answer(interaction: discord.Interaction, answer: app_commands.Choice[str]):
    uid = interaction.user.id
    correct = truth_game.pop(uid, None)
    if correct is None: return await interaction.response.send_message("Сначала начни игру командой `/правда`.", ephemeral=True)
    chosen = answer.value == "правда"
    if chosen == correct:
        balances[uid] = get_balance(uid) + 5
        award_relationship(uid, 2, "game", 9)
        award_achievement(uid, "Участник викторины")
        save_memory()
        await interaction.response.send_message("✨ Верно! Награда: **+5 🍃**")
    else: await interaction.response.send_message("❌ Неверный ответ!")

MEDIA_CHOICES = [app_commands.Choice(name=name, value=name) for name in FOX_MEDIA if name != "gif"] + [app_commands.Choice(name="Случайная GIF", value="gif"), app_commands.Choice(name="Случайная реакция", value="случайно")]
@bot.tree.command(name="лиса", description="Показать картинку или GIF Сенко")
@app_commands.rename(category="категория")
@app_commands.choices(category=MEDIA_CHOICES)
async def slash_fox(interaction: discord.Interaction, category: app_commands.Choice[str]):
    selected = category.value
    if selected == "случайно":
        available = [name for name in FOX_MEDIA if name != "gif" and media_candidates(name)]
        if not available: return await interaction.response.send_message("🦊 В каталоге пока нет доступных изображений.", ephemeral=True)
        selected = random.choice(available)
    if not media_candidates(selected):
        return await interaction.response.send_message(f"🦊 Для категории «{selected}» пока нет медиа. Добавь URL в FOX_MEDIA.", ephemeral=True)
    await send_media_interaction(interaction, selected)
    award_relationship(interaction.user.id, 1, "media", 3)
    save_memory()

@bot.tree.command(name="лиса_помощь", description="Показать категории картинок и GIF Сенко")
async def slash_media_help(interaction: discord.Interaction):
    available = [name for name in FOX_MEDIA if name != "gif" and all_media_urls(name)]
    await interaction.response.send_message("🦊 **Галерея Сенко**\n`/лиса` — выбери категорию из списка.\nКатегории с добавленными медиа: " + (", ".join(available) or "пока нет") + ".", ephemeral=True)

@bot.tree.command(name="настроение", description="Посмотреть или изменить настроение Сенко")
@app_commands.rename(mood="состояние")
@app_commands.choices(mood=MOOD_CHOICES)
async def slash_mood(interaction: discord.Interaction, mood: app_commands.Choice[str]):
    if mood.value != "текущее":
        set_mood(mood.value)
        save_memory()
    await interaction.response.send_message(f"🦊 **Сейчас я {current_mood}.**\n{random.choice(SENKO_MOODS[current_mood])}")

@bot.tree.command(name="профиль", description="Показать профиль, отношения и достижения")
@app_commands.describe(member="Необязательно: посмотреть общую часть профиля участника")
@app_commands.rename(member="пользователь")
async def slash_profile(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    chosen = member or interaction.user
    await interaction.response.send_message(embed=profile_embed(chosen.id, chosen.display_name), ephemeral=True)

@bot.tree.command(name="отношения", description="Посмотреть общую информацию о тебе и Сенко")
async def slash_relationships(interaction: discord.Interaction):
    await interaction.response.send_message(embed=profile_embed(interaction.user.id, interaction.user.display_name), ephemeral=True)

@bot.tree.command(name="о_нас", description="Краткая сводка вашей истории с Сенко")
async def slash_about_us(interaction: discord.Interaction):
    await interaction.response.send_message(embed=profile_embed(interaction.user.id, interaction.user.display_name), ephemeral=True)

@bot.tree.command(name="достижения", description="Посмотреть открытые достижения")
async def slash_achievements(interaction: discord.Interaction):
    unlocked = ensure_profile(interaction.user.id)["achievements"]
    known = ["Первый поиск", "Первая победа в игре", "Первое воспоминание", "Участник викторины"]
    await interaction.response.send_message("🏅 **Достижения Сенко**\n" + "\n".join(("✅ " if x in unlocked else "▫️ ") + x for x in known), ephemeral=True)

@bot.tree.command(name="запомни", description="Сохранить личное воспоминание о тебе")
@app_commands.describe(text="Короткий факт, который Сенко должна помнить")
@app_commands.rename(text="текст")
async def slash_remember(interaction: discord.Interaction, text: str):
    uid = interaction.user.id
    profile = ensure_profile(uid)
    text = text.strip()
    if not profile["memory_enabled"]: return await interaction.response.send_message("Личная память выключена. Сначала используй `/память` и включи её.", ephemeral=True)
    if not text or len(text) > 300: return await interaction.response.send_message("Воспоминание должно быть длиной до 300 символов.", ephemeral=True)
    entries = personal_memories.setdefault(uid, [])
    if any(x.get("text", "").casefold() == text.casefold() for x in entries): return await interaction.response.send_message("🦊 Я уже помню это!", ephemeral=True)
    entries.append({"text": text, "created_at": now_iso(), "created_by": uid})
    del entries[:-100]
    award_relationship(uid, 2, "memory", 4)
    unlocked = award_achievement(uid, "Первое воспоминание")
    save_memory()
    await interaction.response.send_message(f"🧠 Хорошо, я запомню: «{text}»" + ("\n🏅 Достижение открыто!" if unlocked else ""), ephemeral=True)

@bot.tree.command(name="память", description="Посмотреть, включить, выключить или очистить личную память")
@app_commands.rename(action="действие")
@app_commands.choices(action=[app_commands.Choice(name="Показать", value="show"), app_commands.Choice(name="Включить", value="on"), app_commands.Choice(name="Выключить и удалить", value="off"), app_commands.Choice(name="Очистить", value="clear")])
async def slash_memory(interaction: discord.Interaction, action: app_commands.Choice[str]):
    uid = interaction.user.id
    profile = ensure_profile(uid)
    if action.value == "off":
        profile["memory_enabled"] = False
        personal_memories.pop(uid, None)
        user_memory.pop(uid, None)
        save_memory()
        return await interaction.response.send_message("🦊 Личная память выключена и очищена. Групповая память не затронута.", ephemeral=True)
    if action.value == "on":
        profile["memory_enabled"] = True
        save_memory()
        return await interaction.response.send_message("🧠 Личная память включена. Новые воспоминания сохраняются по явной команде `/запомни`.", ephemeral=True)
    if action.value == "clear":
        personal_memories.pop(uid, None)
        user_memory.pop(uid, None)
        save_memory()
        return await interaction.response.send_message("🧹 Личные воспоминания удалены.", ephemeral=True)
    lines = ["🧠 **Твоя личная память**"]
    entries = personal_memories.get(uid, [])
    lines.extend(f"{i}. {x['text']}" for i, x in enumerate(entries[-15:], start=max(1, len(entries)-14)))
    lines.append("\nУправление памятью: `/память`.")
    await interaction.response.send_message("\n".join(lines) if entries else "Пока нет сохранённых воспоминаний. Используй `/запомни`.", ephemeral=True)

@bot.tree.command(name="группа_запомни", description="Сохранить общий факт для текущего сервера")
@app_commands.rename(text="факт")
@app_commands.guild_only()
async def slash_group_remember(interaction: discord.Interaction, text: str):
    text = text.strip()
    if not text or len(text) > 300: return await interaction.response.send_message("Факт должен содержать от 1 до 300 символов.", ephemeral=True)
    entries = group_memories.setdefault(str(interaction.guild_id), [])
    if any(x.get("text", "").casefold() == text.casefold() for x in entries): return await interaction.response.send_message("🦊 Этот факт уже сохранён.", ephemeral=True)
    entries.append({"text": text, "created_at": now_iso(), "created_by": interaction.user.id})
    del entries[:-100]
    save_memory()
    await interaction.response.send_message(f"🦊 Запомнила для этого сервера: «{text}»", ephemeral=True)

@bot.tree.command(name="группа_память", description="Посмотреть общую память текущего сервера")
@app_commands.guild_only()
async def slash_group_memory(interaction: discord.Interaction):
    entries = group_memories.get(str(interaction.guild_id), [])
    text = "🧠 **Общая память сервера**\n" + "\n".join(f"{i}. {x['text']}" for i, x in enumerate(entries[-15:], start=max(1, len(entries)-14))) if entries else "Общая память сервера пока пуста."
    await interaction.response.send_message(text[:1900], ephemeral=True)

@bot.tree.command(name="группа_забыть", description="Удалить запись из общей памяти по номеру")
@app_commands.guild_only()
@app_commands.describe(index="Номер записи из /группа_память")
@app_commands.rename(index="номер")
async def slash_group_forget(interaction: discord.Interaction, index: app_commands.Range[int, 1, 100]):
    entries = group_memories.get(str(interaction.guild_id), [])
    if index < 1 or index > len(entries): return await interaction.response.send_message("Такой записи нет; проверь `/группа_память`.", ephemeral=True)
    entry = entries[index-1]
    admin = isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_guild
    if entry.get("created_by") != interaction.user.id and not admin: return await interaction.response.send_message("Удалить запись может её автор или администратор.", ephemeral=True)
    entries.pop(index-1)
    save_memory()
    await interaction.response.send_message("🧹 Запись удалена.", ephemeral=True)

@bot.tree.command(name="сценка", description="Попросить Сенко разыграть короткую сценку")
async def slash_scene(interaction: discord.Interaction):
    scene_type, scene_text = random.choice(RANDOM_SCENES)
    await interaction.response.send_message(scene_text)
    award_relationship(interaction.user.id, 1, "scene", 3)
    save_memory()

@bot.tree.command(name="игры", description="Показать доступные мини-игры")
async def slash_games(interaction: discord.Interaction):
    embed = discord.Embed(title="🎮 Мини-игры Сенко", description="`/угадайчисло` — число от 1 до 10\n`/числоответ` — сделать попытку\n`/викторина` — вопрос с вариантами\n`/викторинаответ` — ответить\n`/эмоция` — угадать настроение\n`/правда` — правда или ложь", color=0xFF8C00)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="угадайчисло", description="Начать игру: угадать число от 1 до 10")
async def slash_number_start(interaction: discord.Interaction):
    key = f"{interaction.guild_id or 'dm'}:{interaction.channel_id}:{interaction.user.id}"
    number_games[key] = {"number": random.randint(1, 10), "attempts": 0, "started_at": now_iso()}
    await interaction.response.send_message("🦊 Я загадала число от **1 до 10**. Используй `/числоответ` и укажи число.")

@bot.tree.command(name="числоответ", description="Сделать попытку в игре угадай число")
@app_commands.describe(guess="Число от 1 до 10")
@app_commands.rename(guess="число")
async def slash_number_guess(interaction: discord.Interaction, guess: app_commands.Range[int, 1, 10]):
    key = f"{interaction.guild_id or 'dm'}:{interaction.channel_id}:{interaction.user.id}"
    game = number_games.get(key)
    if not game: return await interaction.response.send_message("Сначала начни `/угадайчисло`.", ephemeral=True)
    game["attempts"] += 1
    target = game["number"]
    if guess == target:
        attempts = game["attempts"]
        number_games.pop(key, None)
        reward = max(3, 12 - (attempts-1)*2)
        balances[interaction.user.id] = get_balance(interaction.user.id) + reward
        award_relationship(interaction.user.id, 3, "game", 9)
        award_achievement(interaction.user.id, "Первая победа в игре")
        save_memory()
        await interaction.response.send_message(f"🎉 Угадал(а)! Это было **{target}**. Попыток: {attempts}. Награда: **+{reward} 🍃**")
    elif game["attempts"] >= 5:
        number_games.pop(key, None)
        await interaction.response.send_message(f"🦊 Попытки закончились! Я загадала **{target}**.")
    else:
        await interaction.response.send_message("Моё число больше! 🐾" if guess < target else "Моё число меньше! 🐾")

QUIZ_QUESTIONS = [
    {"question": "Как называется самая маленькая разновидность лис?", "A": "Фенек", "B": "Рыжая лиса", "answer": "A"},
    {"question": "Для чего лисе помогает хвост?", "A": "Только для плавания", "B": "Для баланса", "answer": "B"},
    {"question": "Как называют магических лис в японском фольклоре?", "A": "Кицунэ", "B": "Тануки", "answer": "A"},
]

@bot.tree.command(name="викторина", description="Начать короткую викторину Сенко")
async def slash_quiz(interaction: discord.Interaction):
    key = f"{interaction.guild_id or 'dm'}:{interaction.channel_id}:{interaction.user.id}"
    q = random.choice(QUIZ_QUESTIONS)
    quiz_games[key] = {**q, "started_at": now_iso()}
    await interaction.response.send_message(f"🦊 **Викторина**\n{q['question']}\nA) {q['A']}\nB) {q['B']}\nОтветь через `/викторинаответ`.")

@bot.tree.command(name="викторинаответ", description="Ответить на вопрос викторины")
@app_commands.rename(answer="вариант")
@app_commands.choices(answer=[app_commands.Choice(name="A", value="A"), app_commands.Choice(name="B", value="B")])
async def slash_quiz_answer(interaction: discord.Interaction, answer: app_commands.Choice[str]):
    key = f"{interaction.guild_id or 'dm'}:{interaction.channel_id}:{interaction.user.id}"
    game = quiz_games.pop(key, None)
    if not game: return await interaction.response.send_message("Сначала начни `/викторина`.", ephemeral=True)
    if answer.value == game["answer"]:
        balances[interaction.user.id] = get_balance(interaction.user.id) + 5
        award_relationship(interaction.user.id, 2, "game", 9)
        award_achievement(interaction.user.id, "Участник викторины")
        save_memory()
        await interaction.response.send_message("✨ Верно! Награда: **+5 🍃**")
    else: await interaction.response.send_message(f"Не совсем! Правильный ответ: **{game[game['answer']]}**.")

@bot.tree.command(name="сенко_предпочтение", description="Установить предпочтительную категорию медиа")
@app_commands.rename(category="категория")
@app_commands.choices(category=[app_commands.Choice(name=x, value=x) for x in FOX_MEDIA if x not in ("gif",)] + [app_commands.Choice(name="Не выбирать предпочтение", value="выкл")])
async def slash_preference(interaction: discord.Interaction, category: app_commands.Choice[str]):
    pref = "" if category.value == "выкл" else category.value
    ensure_profile(interaction.user.id)["preferences"]["preferred_media"] = pref
    save_memory()
    await interaction.response.send_message("🦊 Предпочтение очищено." if not pref else f"🦊 Сохранила предпочтение: **{pref}**.", ephemeral=True)

@bot.tree.command(name="сенко_статус", description="Кратко проверить состояние Сенко")
async def slash_status(interaction: discord.Interaction):
    available_count = len(all_media_urls())
    verified = sum(1 for v in media_status.values() if isinstance(v, dict) and v.get("ok") is True)
    failed = sum(1 for v in media_status.values() if isinstance(v, dict) and v.get("ok") is False)
    embed = discord.Embed(title="🦊 Senko 3.0 — статус", color=0xFF8C00)
    embed.add_field(name="Хранилище", value="✅ запись доступна" if memory_write_allowed else "⚠️ запись отключена для защиты данных", inline=False)
    embed.add_field(name="Медиа", value=f"{available_count} URL · проверено успешно: {verified} · ошибок: {failed}", inline=False)
    embed.add_field(name="Настроение", value=current_mood, inline=True)
    embed.add_field(name="Профили", value=str(len(profiles)), inline=True)
    if memory_load_error: embed.add_field(name="Предупреждение", value=memory_load_error[:900], inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="сенко_диагностика", description="Подробная диагностика (для администраторов)")
async def slash_diagnostics(interaction: discord.Interaction):
    if not is_admin_member(interaction.user): return await interaction.response.send_message("Доступно администраторам сервера с Manage Server.", ephemeral=True)
    lines = [f"{'✅' if DATA_FILE.exists() else '⚠️'} data.json существует", f"{'✅' if memory_write_allowed else '⚠️'} запись разрешена", f"{'✅' if isinstance(profiles, dict) else '⚠️'} профили загружены", f"{'✅' if isinstance(FOX_MEDIA, dict) else '⚠️'} каталог медиа доступен"]
    if memory_load_error: lines.append("Предупреждение: " + memory_load_error[:300])
    lines.extend([f"Путь данных: `{DATA_FILE.resolve()}`", f"Резервные копии: `{BACKUP_DIR.resolve()}`", f"AI-диалог: {'включён через API' if OPENAI_API_KEY else 'без API — ограниченные шаблонные ответы'}"])
    await interaction.response.send_message("🛠️ **Диагностика Senko 3.0**\n" + "\n".join(lines), ephemeral=True)

@bot.tree.command(name="сенко_медиа_проверить", description="Проверить доступность URL медиа (администратор)")
async def slash_check_media(interaction: discord.Interaction):
    if not is_admin_member(interaction.user): return await interaction.response.send_message("Проверка доступна администраторам сервера.", ephemeral=True)
    urls = all_media_urls()
    if not urls: return await interaction.response.send_message("Каталог медиа пуст.", ephemeral=True)
    await interaction.response.defer(ephemeral=True, thinking=True)
    timeout = aiohttp.ClientTimeout(total=10, connect=5)
    async with aiohttp.ClientSession(timeout=timeout, connector=aiohttp.TCPConnector(limit=8)) as session:
        semaphore = asyncio.Semaphore(8)
        async def one(url):
            async with semaphore: return url, await check_media_url(session, url)
        results = await asyncio.gather(*(one(url) for url in urls))
    lines = []
    for url, result in results:
        media_status[url] = result
        lines.append(f"{'✅' if result.get('ok') else '❌'} `{result.get('status') or 'ERR'}` {result.get('content_type', 'unknown')} — {url}")
    save_memory()
    await interaction.followup.send("**Результаты проверки медиа**\n" + "\n".join(lines)[:1800] + "\n\nℹ️ Проверка HTTP не гарантирует, что клиент отобразит анимацию.", ephemeral=True)

@bot.tree.command(name="сенко_авто", description="Включить или отключить самостоятельную активность")
@app_commands.rename(state="режим")
@app_commands.choices(state=[app_commands.Choice(name="Включить", value="on"), app_commands.Choice(name="Выключить", value="off")])
async def slash_autonomy(interaction: discord.Interaction, state: app_commands.Choice[str]):
    if not is_admin_member(interaction.user): return await interaction.response.send_message("Доступно администраторам сервера.", ephemeral=True)
    settings["autonomous_enabled"] = state.value == "on"
    save_memory()
    await interaction.response.send_message("🦊 Самостоятельная активность включена." if settings["autonomous_enabled"] else "🦊 Самостоятельная активность отключена.", ephemeral=True)

@bot.tree.command(name="связать", description="Запустить доверительную ролевую сценку (требует высшего доверия)")
async def slash_bind(interaction: discord.Interaction):
    uid = interaction.user.id
    if not BIND_ALLOWED_USER_ID:
        return await interaction.response.send_message("🦊 Эта сценка ещё не настроена. Владелец должен указать SENKO_BIND_ALLOWED_USER_ID в настройках Wispbyte.", ephemeral=True)
    if uid != BIND_ALLOWED_USER_ID:
        return await interaction.response.send_message("🦊 Эта особая сценка доступна только специально разрешённому пользователю.", ephemeral=True)
    points = ensure_profile(uid)["relationship_points"]
    level_name, level = relationship_level(points)
    if level < 4:
        return await interaction.response.send_message(f"🦊 Сначала нужно достичь высшего уровня доверия. Сейчас: **{level_name}** ({points}/150 очков).", ephemeral=True)
    await interaction.response.send_message("🦊 Ты достиг высшего уровня доверия. Подтверди, что хочешь начать безобидную вымышленную сценку. Её можно отменить в любой момент.", view=BindConfirmView(uid), ephemeral=True)

# -----------------------------------------------------------------------------
# Conversation with Senko
# -----------------------------------------------------------------------------
ALIASES = ["сенко-сан", "сенко сан", "senko-san", "senko san", "сенко", "senko", "лиса", "мать"]
ALIAS_PATTERN = re.compile(r"(?<![\w])(" + "|".join(re.escape(x) for x in sorted(ALIASES, key=len, reverse=True)) + r")(?![\w])", re.IGNORECASE | re.UNICODE)

def detect_alias(text: str) -> Optional[str]:
    match = ALIAS_PATTERN.search(text)
    return match.group(1).lower() if match else None

def remove_bot_mention(text: str, bot_user: Optional[discord.ClientUser]) -> str:
    if bot_user:
        text = re.sub(rf"<@!?{bot_user.id}>", "", text)
    return text.strip()

def local_chat_reply(text: str, alias: Optional[str], level: int) -> str:
    lower = text.lower().strip()
    if not lower: return "Да? Ты звала меня? *Сенко поворачивает ушки к тебе.* 🦊"
    if any(x in lower for x in ("привет", "здравствуй", "хай", "hello", "hi")):
        return random.choice(["Приве-е-ет! *Сенко радостно машет хвостиками.* Как ты сегодня? 🦊", "Ой, привет! Я как раз тут. Расскажешь, как прошёл день? 🌸"])
    if any(x in lower for x in ("спасибо", "благодарю", "ты лучшая")):
        return random.choice(["Хи-хи, всегда пожалуйста! Мне приятно помогать. 💛", "Не за что! *Сенко довольно шевелит ушками.*"])
    if any(x in lower for x in ("грустно", "плохо", "тяжело", "устал", "устала", "одиноко")):
        return random.choice(["Иди сюда, немного посидим рядом. Не обязательно решать всё сразу. 🦊", "Ох… хочешь рассказать, что случилось? Я послушаю. 🌸"])
    if "?" in lower or any(lower.startswith(x) for x in ("почему", "как ", "зачем", "когда", "что ", "кто ")):
        return "Хм-м, хороший вопрос! Я могу поддержать разговор, но для развёрнутых ответов на любые темы нужно подключить AI API через OPENAI_API_KEY. Расскажешь чуть подробнее? 🦊"
    if level >= 4:
        return random.choice([f"*Сенко внимательно тебя слушает.* Я рада, что ты со мной разговариваешь. Что ты думаешь об этом сам? 💛", f"Угу, я слушаю тебя внимательно. Хочешь, вместе это обдумаем? 🦊"])
    if level >= 2:
        return random.choice(["Угу-угу, продолжай, мне интересно! 🦊", "*Сенко наклоняет голову.* И что было дальше? Рассказывай! 🌸", "Хи-хи, поняла. А как ты сам к этому относишься?"])
    return random.choice(["О, расскажи подробнее! 🦊", "Я слушаю. И что ты об этом думаешь?", "Хм-м… интересно. Что случилось дальше?"])

async def generate_ai_reply(user_id: int, channel_id: int, user_name: str, text: str, alias: Optional[str]) -> str:
    key = f"{channel_id}:{user_id}"
    history = chat_history.setdefault(key, [])
    points = ensure_profile(user_id)["relationship_points"]
    level_name, level = relationship_level(points)
    addressing = f"Пользователь обратился к тебе как «{alias}»." if alias else "Пользователь написал тебе напрямую."
    if not OPENAI_API_KEY:
        reply = local_chat_reply(text, alias, level)
        history.extend([{"role": "user", "content": text[:700]}, {"role": "assistant", "content": reply[:1200]}])
        del history[:-MAX_CHAT_HISTORY]
        return reply
    system_prompt = (
        "Ты — Сенко, добрая, заботливая и немного игривая лиса-компаньон из вымышленного мира. "
        "Пиши на языке пользователя, обычно на русском. Веди естественный диалог, помни недавний контекст этой сессии, "
        "иногда задавай уместные встречные вопросы, не повторяй одну и ту же фразу. Не утверждай, что ты реальное существо "
        "или обладаешь настоящим сознанием. Не выдумывай факты о пользователе. Не обещай выполнять действия в Discord, "
        "если ты их фактически не выполнила. Сохраняй дружелюбный, тёплый стиль и отвечай обычно в 2–5 предложениях. "
        f"Имя пользователя: {user_name}. Уровень отношений по игровой системе: {level_name} (уровень {level}). {addressing} "
        "Все отношения — ролевая механика; личные факты из одного пользователя не раскрывай другому."
    )
    messages = [{"role": "developer", "content": system_prompt}, *history[-MAX_CHAT_HISTORY:], {"role": "user", "content": text[:1500]}]
    timeout = aiohttp.ClientTimeout(total=25, connect=8)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                json={"model": OPENAI_MODEL, "messages": messages, "max_completion_tokens": 280},
            ) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    log.warning("AI API returned HTTP %s: %s", response.status, str(payload)[:300])
                    return local_chat_reply(text, alias, level)
                reply = payload["choices"][0]["message"].get("content")
                if not isinstance(reply, str) or not reply.strip():
                    return local_chat_reply(text, alias, level)
                reply = reply.strip()[:1900]
                history.extend([{"role": "user", "content": text[:1500]}, {"role": "assistant", "content": reply}])
                del history[:-MAX_CHAT_HISTORY]
                return reply
    except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, IndexError, TypeError, ValueError) as error:
        log.warning("AI chat failed; falling back to local reply: %s", error)
        return local_chat_reply(text, alias, level)

# -----------------------------------------------------------------------------
# Background tasks
# -----------------------------------------------------------------------------
@tasks.loop(minutes=5)
async def fox_lifecycle():
    global last_fox_action
    if not settings.get("autonomous_enabled", True): return
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        try: channel = await bot.fetch_channel(CHANNEL_ID)
        except (discord.HTTPException, discord.NotFound, discord.Forbidden):
            log.warning("Cannot access Senko channel %s", CHANNEL_ID)
            return
    now = dt.datetime.now()
    if last_fox_action and (now - last_fox_action).total_seconds() < FOX_COOLDOWN_MINUTES * 60: return
    if random.random() > FOX_ACTION_CHANCE: return
    try:
        await channel.send(random.choice(FOX_ACTIONS))
        last_fox_action = now
        save_memory()
    except discord.HTTPException: log.exception("Autonomous activity failed")
@fox_lifecycle.before_loop
async def before_fox_lifecycle(): await bot.wait_until_ready()

@tasks.loop(hours=1)
async def hunger_tick():
    changed = False
    for uid in list(hunger):
        new_value = min(100, hunger[uid] + 8)
        if new_value != hunger[uid]: hunger[uid], changed = new_value, True
    if changed: save_memory()
@hunger_tick.before_loop
async def before_hunger_tick(): await bot.wait_until_ready()

@tasks.loop(minutes=1)
async def daily_fact_task():
    global last_fact_date
    if not settings.get("daily_fact_enabled", True): return
    now = dt.datetime.now(); today = now.strftime("%d-%m-%Y")
    if now.hour != 9 or now.minute != 0 or last_fact_date in (today, now.strftime("%d-%m")): return
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        try: channel = await bot.fetch_channel(CHANNEL_ID)
        except (discord.HTTPException, discord.NotFound, discord.Forbidden): return
    try:
        await channel.send(f"☀️ **Лисий факт дня:** {random.choice(FOX_FACTS)}")
        last_fact_date = today; save_memory()
    except discord.HTTPException: log.exception("Daily fact send failed")
@daily_fact_task.before_loop
async def before_daily_fact_task(): await bot.wait_until_ready()

# -----------------------------------------------------------------------------
# Message listener. Responds to aliases/@mention anywhere, and all messages in the
# configured Senko chat channel or a DM, with a per-user cooldown.
# -----------------------------------------------------------------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.webhook_id:
        return
    # Keep old ! commands during the transition; commands don't trigger chat replies.
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return
    uid = message.author.id
    now = dt.datetime.now()
    profile = ensure_profile(uid)
    if profile.get("memory_enabled", True):
        first_seen.setdefault(uid, now.isoformat())
        user_memory[uid] = message.content[:200]
        last_messages[uid] = now
        message_counts[uid] = message_counts.get(uid, 0) + 1
    inferred = infer_mood(message.content)
    if inferred: set_mood(inferred)
    save_memory()

    alias = detect_alias(message.content)
    mentioned = bool(bot.user and (bot.user in message.mentions or re.search(rf"<@!?{bot.user.id}>", message.content)))
    in_senko_channel = message.channel.id == CHAT_CHANNEL_ID
    is_dm = message.guild is None
    should_reply = mentioned or alias is not None or in_senko_channel or is_dm
    if not should_reply:
        await bot.process_commands(message)
        return
    previous = last_chat_reply.get(uid)
    if previous and (now - previous).total_seconds() < CHAT_USER_COOLDOWN_SECONDS and not mentioned and alias is None:
        await bot.process_commands(message)
        return
    raw = remove_bot_mention(message.content, bot.user)
    if alias:
        raw = ALIAS_PATTERN.sub("", raw, count=1).strip(" ,.!?—-\n\t")
    if not raw:
        raw = "Ты здесь?" if (mentioned or alias) else message.content
    if alias == "мать":
        alias_style = "мать"
    else:
        alias_style = alias
    try:
        reply = await generate_ai_reply(uid, message.channel.id, message.author.display_name, raw, alias_style)
        await message.reply(reply, mention_author=False, allowed_mentions=discord.AllowedMentions.none())
        last_chat_reply[uid] = now
        award_relationship(uid, 1, "chat", 6)
        save_memory()
    except discord.HTTPException:
        log.exception("Could not send chat reply")
    await bot.process_commands(message)

    
def console_input_worker():
    print("Консоль готова. Формат: send ID_канала текст")

    while True:
        try:
            line = input("senko> ").strip()
        except (EOFError, OSError):
            print("Ввод консоли недоступен.")
            break

        parts = line.split(maxsplit=2)

        if not parts:
            continue

        command = parts[0].lower()

        if command == "send":
            if len(parts) < 3:
                print("Формат: send ID_канала текст")
                continue

            try:
                channel_id = int(parts[1])
            except ValueError:
                print("Ошибка: ID канала должен быть числом.")
                continue

            future = asyncio.run_coroutine_threadsafe(
                send_console_message(channel_id, parts[2]),
                bot.loop
            )

            try:
                future.result(timeout=30)
                print("Сообщение отправлено!")
            except Exception as error:
                print(f"Ошибка отправки: {error}")

        elif command == "reply":
            parts = line.split(maxsplit=3)

            if len(parts) < 4:
                print("Формат: reply ID_КАНАЛА ID_СООБЩЕНИЯ текст")
                continue

            try:
                channel_id = int(parts[1])
                message_id = int(parts[2])
                message_text = parts[3]
            except ValueError:
                print("Ошибка: ID канала и сообщения должны быть числами.")
                continue

            try:
                future = asyncio.run_coroutine_threadsafe(
                    reply_console_message(channel_id, message_id, message_text),
                    bot.loop
                )
                future.result(timeout=30)
                print("Ответ отправлен!")
            except Exception as e:
                print(f"Ошибка ответа: {e}")

        elif command == "status":
            print(f"Бот: {bot.user}")

        else:
            print("Доступные команды: send, reply, status")


async def send_console_message(channel_id: int, text: str):
    channel = bot.get_channel(channel_id)

    if channel is None:
        channel = await bot.fetch_channel(channel_id)

    if not isinstance(channel, discord.abc.Messageable):
        raise ValueError("Этот канал не поддерживает отправку сообщений.")

    await channel.send(
        text,
        allowed_mentions=discord.AllowedMentions.none()
    )


async def reply_console_message(channel_id: int, message_id: int, text: str):
    channel = bot.get_channel(channel_id)

    if channel is None:
        channel = await bot.fetch_channel(channel_id)

    if not hasattr(channel, "fetch_message"):
        raise ValueError("Этот канал не поддерживает ответы на сообщения.")

    message = await channel.fetch_message(message_id)

    await message.reply(
        text,
        allowed_mentions=discord.AllowedMentions.none()
    )


console_thread_started = False
    

# -----------------------------------------------------------------------------
# Startup, command sync, errors
# -----------------------------------------------------------------------------

@bot.event
async def on_ready():
    global commands_synced
    global console_thread_started

    if not console_thread_started:
        console_thread_started = True
        threading.Thread(
            target=console_input_worker,
            daemon=True
        ).start()

    log.info("Senko 3.0 online as %s", bot.user)
    log.info("Data path: %s", DATA_FILE.resolve())

    if not commands_synced:
        try:
            if GUILD_ID_RAW:
                guild = discord.Object(id=int(GUILD_ID_RAW))
                bot.tree.copy_global_to(guild=guild)
                synced = await bot.tree.sync(guild=guild)
                log.info(
                    "Synced %s slash commands to guild %s",
                    len(synced),
                    GUILD_ID_RAW
                )
            else:
                synced = await bot.tree.sync()
                log.info("Synced %s global slash commands", len(synced))

            commands_synced = True

        except (discord.HTTPException, ValueError):
                    log.exception(
                "Slash command sync failed. Check the applications.commands scope and command names."
            )

    log.info(
        "AI chat: %s",
        "enabled (OpenAI API; usage may be billed)"
        if OPENAI_API_KEY
        else "fallback mode; set OPENAI_API_KEY for open-ended conversation"
    )

    if not memory_write_allowed:
        log.error(
            "Data writes disabled to protect existing data: %s",
            memory_load_error
        )

    if not fox_lifecycle.is_running():
        fox_lifecycle.start()

    if not hunger_tick.is_running():
        hunger_tick.start()

    if not daily_fact_task.is_running():
        daily_fact_task.start()

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    log.error("Slash command error: %r", error, exc_info=(type(error), error, error.__traceback__))
    text = "🦊 Команда завершилась с ошибкой. Проверь консоль Wispbyte; существующие данные не нужно удалять."
    try:
        if interaction.response.is_done(): await interaction.followup.send(text, ephemeral=True)
        else: await interaction.response.send_message(text, ephemeral=True)
    except discord.HTTPException: pass

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, (commands.CommandNotFound, commands.CommandOnCooldown)): return
    log.error("Prefix command error: %r", error, exc_info=(type(error), error, error.__traceback__))
    try: await ctx.send("🦊 Ошибка команды. Проверь Console в Wispbyte.")
    except discord.HTTPException: pass

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    log.info("Starting Senko 3.0…")
    bot.run(TOKEN)
else:
    log.error("DISCORD_TOKEN не найден. Добавь его в .env или переменные окружения Wispbyte.")
