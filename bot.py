import asyncio
import copy
import datetime
import json
import logging
import os
import random
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import aiohttp
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

# ======================================================
# SENKO 2.0 — CONFIGURATION
# ======================================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

CHANNEL_ID = int(os.getenv("SENKO_CHANNEL_ID", "1492134822666174605"))
FOX_COOLDOWN_MINUTES = 30
FOX_ACTION_CHANCE = 0.25
DATA_FILE = Path(os.getenv("SENKO_DATA_FILE", "data.json"))
BACKUP_DIR = Path(os.getenv("SENKO_BACKUP_DIR", "backups"))
SCHEMA_VERSION = 2

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("senko")

# ======================================================
# ITEMS, SHOP, FOOD
# ======================================================

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

FOOD_LIST = [
    "ягоды", "печенье", "молоко", "рыба", "тофу", "мясо", "хлеб", "грибы", "яблоко"
]

# ======================================================
# CHARACTER, MOODS, FACTS, EVENTS
# ======================================================

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
    "🦊 *Лиса свернулась клубочком.*",
    "✨ *Лиса чистит свою шубку.*",
    "🐾 *Лиса оставила отпечаток лапки.*",
    "📦 *Лиса залезла в коробку.*",
    "👂 *Ушки лисы дернулись.*",
    "🌿 *Лиса выглянула из кустов.*",
    "💤 *Лиса сладко зевнула.*",
    "🍃 *Лиса гоняется за упавшим листиком.*",
]

RANDOM_SCENES = [
    ("comfort", "🦊 *Сенко тихонько садится рядом и протягивает лапку.* Всё наладится — не обязательно справляться со всем сразу."),
    ("happy", "✨ *Сенко подпрыгивает на месте.* Кажется, самое время устроить маленький праздник!"),
    ("playful", "🐾 *Сенко выглядывает из-за уголка.* Ну что, сыграем во что-нибудь?"),
    ("sleepy", "💤 *Сенко сладко зевает и сворачивается клубочком.* Пожалуй, небольшой перерыв никому не повредит."),
]

# ======================================================
# MEDIA CATALOG
# Existing URLs from the previous version are retained.
# Add only direct image/GIF URLs that you have permission to use.
# ======================================================

FOX_MEDIA = {
    "обычная": [],
    "радость": [
        "https://media.tenor.com/AnGdBUdReMsAAAAM/senko-discord.gif",
        "https://i.pinimg.com/originals/5c/a5/41/5ca5416c427103f8c5a040ad142327d2.gif",
    ],
    "смущение": [],
    "сонная": [],
    "удивление": [],
    "обида": [],
    "танец": [],
    "грусть": [
        "https://media.tenor.com/HoSYZR66fsQAAAAM/senko-light.gif",
        "https://media.tenor.com/Lsxo6rTUoSYAAAAM/senko-sewayaki-kitsune-no-senko-san.gif",
    ],
    "gif": [],  # special category: assembled from all GIF URLs below
}

MEDIA_FALLBACKS = {
    "смущение": ["радость", "обычная"],
    "сонная": ["грусть", "обычная"],
    "удивление": ["радость", "обычная"],
    "обида": ["грусть", "обычная"],
    "танец": ["радость", "обычная"],
    "грусть": ["сонная", "обычная"],
    "обычная": ["радость", "грусть"],
}

# ======================================================
# PERSISTENT STATE
# Existing top-level keys in data.json are preserved.
# ======================================================

inventories: dict[int, list] = {}
balances: dict[int, int] = {}
hunger: dict[int, int] = {}
user_memory: dict[int, str] = {}
first_seen: dict[int, str] = {}
message_counts: dict[int, int] = {}
last_messages: dict[int, datetime.datetime] = {}

# Senko 2.0 state
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
last_fox_action: Optional[datetime.datetime] = None

# Persistence safety controls
_persisted_root: dict[str, Any] = {}
memory_write_allowed = True
memory_load_error: Optional[str] = None
backup_created = False
save_lock = asyncio.Lock()

# ======================================================
# DATA STORAGE AND SAFE MIGRATION
# ======================================================

def _parse_datetime(value: Any) -> Optional[datetime.datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value)
        # Convert aware timestamps to local naive timestamps, maintaining
        # compatibility with timestamps written by the legacy version.
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
    except (ValueError, TypeError, OverflowError):
        return None


def load_memory() -> dict[str, Any]:
    """Read data.json without ever treating malformed data as an empty file."""
    global memory_write_allowed, memory_load_error, _persisted_root

    if not DATA_FILE.exists():
        memory_write_allowed = True
        memory_load_error = None
        _persisted_root = {}
        log.info("No existing data file; a new one will be created on first save.")
        return {}

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("Корневое значение JSON должно быть объектом.")

        version = data.get("senko_schema_version", 1)
        if not isinstance(version, int):
            raise ValueError("senko_schema_version должен быть целым числом.")
        if version > SCHEMA_VERSION:
            memory_write_allowed = False
            memory_load_error = (
                f"Файл создан более новой версией схемы ({version}); "
                f"текущая версия поддерживает до {SCHEMA_VERSION}."
            )
            log.error("Persistence writes disabled: %s", memory_load_error)
        else:
            memory_write_allowed = True
            memory_load_error = None

        _persisted_root = copy.deepcopy(data)
        log.info("Persistent memory loaded.")
        return data

    except (OSError, json.JSONDecodeError, ValueError) as error:
        memory_write_allowed = False
        memory_load_error = str(error)
        _persisted_root = {}
        log.exception("Could not safely load %s; automatic writes are disabled.", DATA_FILE)
        return {}


def _make_backup() -> None:
    """Create a snapshot of the valid existing data file before changes."""
    global backup_created
    if backup_created or not DATA_FILE.exists() or memory_load_error:
        return
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"{DATA_FILE.stem}_{stamp}{DATA_FILE.suffix}.bak"
        shutil.copy2(DATA_FILE, backup_path)
        backup_created = True
        log.info("Created data backup: %s", backup_path)
    except OSError as error:
        # Do not block runtime use, but clearly show that a backup failed.
        log.exception("Could not create data backup: %s", error)


def _valid_int_keyed_map(raw: Any, value_check) -> dict[int, Any]:
    result: dict[int, Any] = {}
    if not isinstance(raw, dict):
        return result
    for key, value in raw.items():
        try:
            uid = int(key)
        except (ValueError, TypeError):
            continue
        if value_check(value):
            result[uid] = value
    return result


def _ensure_profile(uid: int) -> dict[str, Any]:
    key = str(uid)
    profile = profiles.get(key)
    if not isinstance(profile, dict):
        profile = {}
        profiles[key] = profile
    profile.setdefault("relationship_points", 0)
    profile.setdefault("achievements", [])
    profile.setdefault("preferences", {})
    profile.setdefault("memory_enabled", True)
    profile.setdefault("last_awards", {})
    try:
        profile["relationship_points"] = max(0, int(profile.get("relationship_points", 0) or 0))
    except (TypeError, ValueError):
        profile["relationship_points"] = 0
    if not isinstance(profile.get("achievements"), list):
        profile["achievements"] = []
    if not isinstance(profile.get("preferences"), dict):
        profile["preferences"] = {}
    if not isinstance(profile.get("last_awards"), dict):
        profile["last_awards"] = {}
    profile["memory_enabled"] = bool(profile.get("memory_enabled", True))
    profile["preferences"].setdefault("auto_reactions", True)
    profile["preferences"].setdefault("preferred_media", "")
    return profile


def restore_memory() -> None:
    global inventories, balances, hunger, user_memory, first_seen
    global message_counts, last_messages, last_fact_date, last_fox_action
    global personal_memories, group_memories, profiles, settings
    global current_mood, current_mood_changed_at, last_event_by_channel, media_status
    global truth_game, mood_game, number_games, quiz_games

    data = load_memory()

    inventories = _valid_int_keyed_map(data.get("inventories", {}), lambda v: isinstance(v, list))
    balances = _valid_int_keyed_map(
        data.get("balances", {}), lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0
    )
    balances = {uid: int(amount) for uid, amount in balances.items()}
    hunger = _valid_int_keyed_map(
        data.get("hunger", {}), lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    )
    hunger = {uid: max(0, min(100, int(value))) for uid, value in hunger.items()}
    user_memory = _valid_int_keyed_map(data.get("user_memory", {}), lambda v: isinstance(v, str))
    first_seen = _valid_int_keyed_map(data.get("first_seen", {}), lambda v: isinstance(v, str))
    message_counts = _valid_int_keyed_map(
        data.get("message_counts", {}), lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 0
    )

    last_messages = {}
    raw_last_messages = data.get("last_messages", {})
    if isinstance(raw_last_messages, dict):
        for key, value in raw_last_messages.items():
            try:
                uid = int(key)
            except (ValueError, TypeError):
                continue
            parsed = _parse_datetime(value)
            if parsed:
                last_messages[uid] = parsed

    raw_personal = data.get("personal_memories", {})
    personal_memories = {}
    if isinstance(raw_personal, dict):
        for key, entries in raw_personal.items():
            try:
                uid = int(key)
            except (ValueError, TypeError):
                continue
            if isinstance(entries, list):
                valid_entries = [
                    entry for entry in entries
                    if isinstance(entry, dict) and isinstance(entry.get("text"), str)
                ]
                personal_memories[uid] = valid_entries[-100:]

    raw_groups = data.get("group_memories", {})
    group_memories = {}
    if isinstance(raw_groups, dict):
        for gid, entries in raw_groups.items():
            if isinstance(entries, list):
                group_memories[str(gid)] = [
                    entry for entry in entries
                    if isinstance(entry, dict) and isinstance(entry.get("text"), str)
                ][-100:]

    raw_profiles = data.get("profiles", {})
    profiles = raw_profiles if isinstance(raw_profiles, dict) else {}
    for key in list(profiles.keys()):
        try:
            int(key)
        except (ValueError, TypeError):
            profiles.pop(key, None)
    for key in profiles:
        try:
            _ensure_profile(int(key))
        except (ValueError, TypeError):
            continue

    raw_settings = data.get("senko_settings", {})
    if isinstance(raw_settings, dict):
        settings = {**settings, **raw_settings}
    settings.setdefault("autonomous_enabled", True)
    settings.setdefault("random_events_enabled", True)
    settings.setdefault("daily_fact_enabled", True)
    settings.setdefault("event_cooldown_minutes", 45)

    raw_mood = data.get("current_mood", "заботливое")
    current_mood = raw_mood if raw_mood in SENKO_MOODS else "заботливое"
    current_mood_changed_at = data.get("current_mood_changed_at") if isinstance(data.get("current_mood_changed_at"), str) else None

    raw_event_times = data.get("last_event_by_channel", {})
    last_event_by_channel = raw_event_times if isinstance(raw_event_times, dict) else {}
    raw_media_status = data.get("media_status", {})
    media_status = raw_media_status if isinstance(raw_media_status, dict) else {}

    # Existing games were session-only; new games are also session-local to avoid
    # resuming stale sessions after a process crash.
    truth_game = {}
    mood_game = {}
    number_games = {}
    quiz_games = {}

    last_fact_date = data.get("last_fact_date") if isinstance(data.get("last_fact_date"), str) else None
    last_fox_action = _parse_datetime(data.get("last_fox_action"))

    if DATA_FILE.exists() and memory_load_error is None:
        _make_backup()


def save_memory() -> bool:
    """Atomically persist state while preserving fields unknown to this version."""
    global _persisted_root

    if not memory_write_allowed:
        log.error("Save skipped to protect existing data: %s", memory_load_error or "write disabled")
        return False

    data = copy.deepcopy(_persisted_root) if isinstance(_persisted_root, dict) else {}
    data.update({
        "senko_schema_version": SCHEMA_VERSION,
        "inventories": inventories,
        "balances": balances,
        "hunger": hunger,
        "user_memory": user_memory,
        "first_seen": first_seen,
        "message_counts": message_counts,
        "last_messages": {str(uid): date.isoformat() for uid, date in last_messages.items()},
        "last_fact_date": last_fact_date,
        "last_fox_action": last_fox_action.isoformat() if last_fox_action else None,
        "personal_memories": {str(uid): entries for uid, entries in personal_memories.items()},
        "group_memories": group_memories,
        "profiles": profiles,
        "senko_settings": settings,
        "current_mood": current_mood,
        "current_mood_changed_at": current_mood_changed_at,
        "last_event_by_channel": last_event_by_channel,
        "media_status": media_status,
    })

    try:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix=f"{DATA_FILE.name}.", suffix=".tmp", dir=str(DATA_FILE.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, DATA_FILE)
            _persisted_root = copy.deepcopy(data)
            return True
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except (OSError, TypeError, ValueError) as error:
        log.exception("Could not save persistent memory: %s", error)
        return False


restore_memory()

# ======================================================
# COMMON HELPERS
# ======================================================

def get_balance(uid: int) -> int:
    return int(balances.get(uid, 0))


def get_inventory(uid: int) -> list:
    return inventories.setdefault(uid, [])


def get_hunger_state(value: int) -> str:
    if value <= 15:
        return "сытая ✨"
    if value >= 85:
        return "очень голодная 🆘"
    return "в норме 👍"


def relationship_level(points: int) -> tuple[str, int]:
    if points >= 150:
        return "Особенный человек", 4
    if points >= 75:
        return "Близкий друг", 3
    if points >= 25:
        return "Друг", 2
    return "Знакомый", 1


def award_relationship(uid: int, points: int = 1, source: str = "interaction", daily_limit: int = 10) -> int:
    """Give relationship points with per-source daily throttling."""
    profile = _ensure_profile(uid)
    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    last_awards = profile["last_awards"]
    record = last_awards.get(source, {})
    if not isinstance(record, dict) or record.get("date") != today:
        record = {"date": today, "count": 0}
    count = int(record.get("count", 0) or 0)
    if count >= daily_limit:
        return 0
    granted = min(max(0, int(points)), daily_limit - count)
    profile["relationship_points"] = int(profile.get("relationship_points", 0)) + granted
    record["count"] = count + granted
    last_awards[source] = record
    return granted


def award_achievement(uid: int, achievement: str) -> bool:
    profile = _ensure_profile(uid)
    if achievement in profile["achievements"]:
        return False
    profile["achievements"].append(achievement)
    return True


def set_mood(mood: str) -> None:
    global current_mood, current_mood_changed_at
    if mood in SENKO_MOODS and mood != current_mood:
        current_mood = mood
        current_mood_changed_at = datetime.datetime.now().isoformat()


def infer_mood(message: str) -> Optional[str]:
    text = message.lower()
    if any(term in text for term in ("грустно", "плохо", "тяжело", "устал", "устала", "поддержи", "грустный")):
        return "заботливое"
    if any(term in text for term in ("ура", "получилось", "победил", "победила", "спасибо", "классно", "ураа")):
        return "радостное"
    if any(term in text for term in ("поиграем", "игра", "шутка", "ха-ха", "ахаха", "хаха")):
        return "игривое"
    if any(term in text for term in ("спокойной ночи", "спать", "сонный", "сонная", "устала спать")):
        return "сонное"
    return None


def current_time_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def is_admin(ctx: commands.Context) -> bool:
    return bool(ctx.guild and isinstance(ctx.author, discord.Member) and ctx.author.guild_permissions.manage_guild)


async def send_long(ctx: commands.Context, text: str) -> None:
    # Discord messages are limited; keep long memory output to a safe length.
    if len(text) <= 1900:
        await ctx.send(text)
    else:
        await ctx.send(text[:1850] + "…\n(вывод сокращён)")

# ======================================================
# MEDIA ENGINE
# ======================================================

def _all_media_urls(category: Optional[str] = None) -> list[str]:
    if category == "gif":
        return list(dict.fromkeys(
            url for name, urls in FOX_MEDIA.items() if name != "gif"
            for url in urls if isinstance(url, str) and url.lower().split("?", 1)[0].endswith(".gif")
        ))
    if category is None:
        return list(dict.fromkeys(url for urls in FOX_MEDIA.values() for url in urls if isinstance(url, str) and url))
    return [url for url in FOX_MEDIA.get(category, []) if isinstance(url, str) and url]


def _media_candidates(category: str) -> list[str]:
    candidates = _all_media_urls(category)
    for fallback_category in MEDIA_FALLBACKS.get(category, []):
        candidates.extend(_all_media_urls(fallback_category))
    # Do not re-try URLs already flagged as broken if other candidates remain.
    candidates = list(dict.fromkeys(candidates))
    return [url for url in candidates if media_status.get(url, {}).get("ok") is not False]


async def send_senko_media(ctx: commands.Context, category: str) -> bool:
    candidates = _media_candidates(category)
    if not candidates:
        available = ", ".join(name for name in FOX_MEDIA if name != "gif" and _all_media_urls(name)) or "пока нет"
        await ctx.send(
            f"🦊 Для категории «{category}» пока нет доступных медиа.\n"
            f"Категории с медиа: {available}"
        )
        return False

    random.shuffle(candidates)
    url = candidates[0]
    embed = discord.Embed(title=f"🦊 Сенкосан — {category}", color=0xFF8C00)
    embed.set_image(url=url)
    embed.set_footer(text="Если анимация не отображается, добавь альтернативную прямую ссылку в каталог.")
    try:
        await ctx.send(embed=embed)
        return True
    except discord.HTTPException as error:
        log.warning("Media send failed for %s: %s", url, error)
        alternatives = [item for item in candidates[1:] if item != url]
        if alternatives:
            fallback_embed = discord.Embed(title=f"🦊 Сенкосан — {category} (запасная реакция)", color=0xFF8C00)
            fallback_embed.set_image(url=alternatives[0])
            try:
                await ctx.send(embed=fallback_embed)
                return True
            except discord.HTTPException:
                pass
        await ctx.send("🦊 Не удалось отправить медиа. Попробуй позже или сообщи владельцу бота.")
        return False


async def check_media_url(session: aiohttp.ClientSession, url: str) -> dict[str, Any]:
    """Check a configured URL. This does not guarantee Discord will animate it."""
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        return {"ok": False, "status": None, "content_type": "invalid-url", "error": "invalid URL"}

    headers = {"User-Agent": "SenkoBot/2.0 media-check"}
    try:
        async with session.get(url, headers=headers, allow_redirects=True) as response:
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            content_length = response.headers.get("Content-Length")
            # Read only a small prefix: enough to inspect common image signatures.
            prefix = await response.content.read(32)
            looks_image = content_type.startswith("image/") or prefix.startswith((b"GIF87a", b"GIF89a", b"\x89PNG", b"\xff\xd8\xff", b"RIFF"))
            ok = response.status < 400 and looks_image
            return {
                "ok": ok,
                "status": response.status,
                "content_type": content_type or "unknown",
                "final_url": str(response.url),
                "content_length": content_length,
                "checked_at": current_time_iso(),
                "error": None if ok else "HTTP error or response is not a recognizable image",
            }
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as error:
        return {"ok": False, "status": None, "content_type": "unknown", "checked_at": current_time_iso(), "error": str(error)[:200]}


@bot.command(name="лиса")
@commands.cooldown(2, 5, commands.BucketType.user)
async def лиса(ctx: commands.Context, *, mood: str = ""):
    mood = mood.lower().strip()
    if not mood:
        available = [name for name in FOX_MEDIA if name != "gif" and _all_media_urls(name)]
        if not available:
            return await ctx.send("🦊 У меня пока нет картинок. Добавь прямые ссылки в FOX_MEDIA.")
        mood = random.choice(available)

    if mood == "gif":
        if not _all_media_urls("gif"):
            return await ctx.send("🦊 В каталоге пока нет URL с расширением .gif. Добавь прямые GIF-ссылки в FOX_MEDIA.")
    elif mood not in FOX_MEDIA:
        available = ", ".join(name for name in FOX_MEDIA if name != "gif" and _all_media_urls(name)) or "пока нет"
        return await ctx.send(f"🦊 Не знаю такую эмоцию. Категории с медиа: {available}")

    category = mood if mood != "gif" else "gif"
    ok = await send_senko_media(ctx, category)
    if ok:
        award_relationship(ctx.author.id, 1, source="media", daily_limit=3)
        save_memory()


@лиса.error
async def fox_media_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"🦊 Лисичка отдыхает. Попробуй через {max(1, int(error.retry_after))} сек.")
    else:
        raise error


@bot.command(name="лиса_помощь")
async def лиса_помощь(ctx: commands.Context):
    embed = discord.Embed(
        title="🦊 Галерея Сенкосан",
        description=(
            "`!лиса` — случайная реакция\n"
            "`!лиса радость` — радость\n"
            "`!лиса сонная` — сонная реакция (если добавлена)\n"
            "`!лиса грусть` — грустная реакция\n"
            "`!лиса gif` — случайная прямая GIF-ссылка\n\n"
            "Недоступная ссылка может быть заменена запасной реакцией."
        ),
        color=0xFF8C00,
    )
    await ctx.send(embed=embed)

# ======================================================
# AUTONOMOUS ACTIVITY AND DAILY TASKS
# ======================================================

@tasks.loop(minutes=5)
async def fox_lifecycle():
    global last_fox_action
    if not settings.get("autonomous_enabled", True):
        return

    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(CHANNEL_ID)
        except (discord.HTTPException, discord.NotFound, discord.Forbidden):
            log.warning("Could not access Senko channel %s.", CHANNEL_ID)
            return

    now = datetime.datetime.now()
    if last_fox_action is not None:
        elapsed = (now - last_fox_action).total_seconds() / 60
        if elapsed < FOX_COOLDOWN_MINUTES:
            return
    if random.random() > FOX_ACTION_CHANCE:
        return

    previous_action = last_fox_action
    try:
        await channel.send(random.choice(FOX_ACTIONS))
        last_fox_action = now
        save_memory()
    except discord.HTTPException as error:
        log.warning("Autonomous fox action failed: %s", error)
        last_fox_action = previous_action


@fox_lifecycle.before_loop
async def before_fox_lifecycle():
    await bot.wait_until_ready()


@tasks.loop(hours=1)
async def hunger_tick():
    changed = False
    for uid in list(hunger.keys()):
        new_value = min(100, hunger[uid] + 8)
        if new_value != hunger[uid]:
            hunger[uid] = new_value
            changed = True
    if changed:
        save_memory()


@hunger_tick.before_loop
async def before_hunger_tick():
    await bot.wait_until_ready()


@tasks.loop(minutes=1)
async def daily_fact_task():
    global last_fact_date
    if not settings.get("daily_fact_enabled", True):
        return

    now = datetime.datetime.now()
    today = now.strftime("%d-%m-%Y")
    legacy_today = now.strftime("%d-%m")
    if now.hour != 9 or now.minute != 0 or last_fact_date in (today, legacy_today):
        return

    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(CHANNEL_ID)
        except (discord.HTTPException, discord.NotFound, discord.Forbidden):
            return
    try:
        await channel.send(f"☀️ **Лисий факт дня:** {random.choice(FOX_FACTS)}")
        last_fact_date = today
        save_memory()
    except discord.HTTPException as error:
        log.warning("Daily fact send failed: %s", error)


@daily_fact_task.before_loop
async def before_daily_fact_task():
    await bot.wait_until_ready()

# ======================================================
# LEGACY COMMANDS — KEPT FOR BACKWARD COMPATIBILITY
# ======================================================

@bot.command(name="поиск")
@commands.cooldown(1, 10, commands.BucketType.user)
async def поиск(ctx: commands.Context):
    uid = ctx.author.id
    if uid in searching_users:
        return await ctx.send("🦊 Ты уже отправил меня на поиск! Подожди немного.")

    searching_users.add(uid)
    try:
        msg = await ctx.send("🦊 *Лиса внимательно принюхивается и убегает в заросли...*")
        await asyncio.sleep(5)
        roll = random.random()
        if roll < 0.1:
            rarity, reward = "Mythical", 50
        elif roll < 0.4:
            rarity, reward = "Rare", 20
        else:
            rarity, reward = "Common", 5

        item = random.choice(ITEMS[rarity])
        get_inventory(uid).append(item)
        balances[uid] = get_balance(uid) + reward
        award_relationship(uid, 2, source="search", daily_limit=8)
        first_reward = award_achievement(uid, "Первый поиск")
        save_memory()
        suffix = "\n🏅 Открыто достижение: **Первый поиск**!" if first_reward else ""
        await msg.edit(content=f"🦊 **Нашла!**\nПредмет: {item} (`{rarity}`)\nНаграда: `+{reward} 🍃`{suffix}")
    finally:
        searching_users.discard(uid)


@поиск.error
async def поиск_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"🦊 *Лиса отдыхает.* Попробуй снова через {max(1, int(error.retry_after))} сек.")
    else:
        raise error


@bot.command(name="рюкзак")
async def рюкзак(ctx: commands.Context):
    uid = ctx.author.id
    items = inventories.get(uid, [])
    balance = get_balance(uid)
    display = "\n".join(f"• {item}" for item in items[-15:]) if items else "Пусто"
    if len(items) > 15:
        display += f"\n...и ещё {len(items) - 15} предметов"
    embed = discord.Embed(title="🎒 Рюкзак", description=display, color=0xFF8C00)
    embed.add_field(name="🍃 Баланс", value=f"**{balance}** листиков", inline=False)
    await ctx.send(embed=embed)


@bot.command(name="магазин")
async def магазин(ctx: commands.Context):
    embed = discord.Embed(
        title="🏪 Лавка Сенкосан",
        description="Добро пожаловать в мою лавку!\nВыбирай, что тебе приглянулось 🦊",
        color=0xFF8C00,
    )
    for item, price in SHOP_ITEMS.items():
        embed.add_field(name=item, value=f"Цена: **{price} 🍃**\nКупить: `!купить {item}`", inline=True)
    embed.set_footer(text="Зарабатывай листики с помощью !поиск и игр.")
    await ctx.send(embed=embed)


@bot.command(name="купить")
async def купить(ctx: commands.Context, *, item_name: str = ""):
    uid = ctx.author.id
    selected_item = next((item for item in SHOP_ITEMS if item.lower() == item_name.strip().lower()), None)
    if selected_item is None:
        return await ctx.send("🦊 Не знаю такого товара!\nПосмотри ассортимент: `!магазин`")
    price = SHOP_ITEMS[selected_item]
    balance = get_balance(uid)
    if balance < price:
        return await ctx.send(
            "🦊 *Лиса заглянула в твой кошелёк...*\n"
            f"Не хватает **{price - balance} 🍃**.\nПопробуй поискать что-нибудь: `!поиск`"
        )
    balances[uid] = balance - price
    get_inventory(uid).append(selected_item)
    award_relationship(uid, 1, source="shop", daily_limit=3)
    save_memory()
    await ctx.send(
        f"🛍️ **Покупка совершена!**\nТы приобрёл: {selected_item}\n"
        f"Потрачено: **{price} 🍃**\nОсталось: **{balances[uid]} 🍃**"
    )


@bot.command(name="эмоция")
async def эмоция(ctx: commands.Context):
    mood = random.choice(list(MOODS.keys()))
    hint = random.choice(MOODS[mood])
    mood_game[ctx.author.id] = mood
    await ctx.send(f"🦊 **Угадай настроение!**\nПодсказка: *«{hint}»*\nОтветь командой `!угадай {mood}`.")


@bot.command(name="угадай")
async def угадай(ctx: commands.Context, *, guess: str = ""):
    uid = ctx.author.id
    correct = mood_game.get(uid)
    if correct is None:
        return await ctx.send("Сначала начни игру: `!эмоция`")
    if guess.lower().strip() == correct:
        balances[uid] = get_balance(uid) + 10
        mood_game.pop(uid, None)
        award_relationship(uid, 3, source="game", daily_limit=9)
        first_win = award_achievement(uid, "Первая победа в игре")
        save_memory()
        suffix = "\n🏅 Открыто достижение: **Первая победа в игре**!" if first_win else ""
        await ctx.send(f"✨ Верно! Мне {correct}.\nНаграда: **+10 🍃**{suffix}")
    else:
        await ctx.send("❌ Не-а! Попробуй ещё раз.")


@bot.command(name="покормить")
async def покормить(ctx: commands.Context, *, food: str = ""):
    uid = ctx.author.id
    if uid not in hunger:
        hunger[uid] = 50
    food = food.lower().strip()
    if any(item in food for item in FOOD_LIST):
        hunger[uid] = max(0, hunger[uid] - 35)
        award_relationship(uid, 2, source="feed", daily_limit=6)
        save_memory()
        await ctx.send(f"🦊 *Ням!* Теперь я {get_hunger_state(hunger[uid])}")
    else:
        await ctx.send("🦊 Я это не ем... Попробуй ягоды, печенье, молоко или что-нибудь из списка.")


@bot.command(name="правда")
async def правда(ctx: commands.Context):
    fact, answer = random.choice(TRUTH_OR_DARE_FACTS)
    truth_game[ctx.author.id] = answer
    await ctx.send(f"🦊 **Правда или ложь?**\n> {fact}\n\nОтветь: `!ответ правда` или `!ответ ложь`")


@bot.command(name="ответ")
async def ответ(ctx: commands.Context, *, guess: str = ""):
    uid = ctx.author.id
    correct = truth_game.get(uid)
    if correct is None:
        return await ctx.send("🦊 Сначала начни игру: `!правда`")
    guess = guess.lower().strip()
    if guess in ["правда", "да", "true"]:
        user_answer = True
    elif guess in ["ложь", "нет", "false"]:
        user_answer = False
    else:
        return await ctx.send("Ответь `правда` или `ложь`.")
    if user_answer == correct:
        balances[uid] = get_balance(uid) + 5
        award_relationship(uid, 2, source="game", daily_limit=9)
        await ctx.send("✨ Верно! Ты получаешь **+5 🍃**")
    else:
        await ctx.send("❌ Неверный ответ!")
    truth_game.pop(uid, None)
    award_achievement(uid, "Участник викторины")
    save_memory()

# ======================================================
# MEMORY: PERSONAL AND GROUP
# ======================================================

@bot.command(name="запомни")
async def запомни(ctx: commands.Context, *, text: str = ""):
    uid = ctx.author.id
    profile = _ensure_profile(uid)
    if not profile.get("memory_enabled", True):
        return await ctx.send("🦊 Твоя личная память отключена. Включи её командой `!память вкл`.")
    text = text.strip()
    if not text:
        return await ctx.send("Укажи, что запомнить: `!запомни я люблю клубничное мороженое`")
    if len(text) > 300:
        return await ctx.send("🦊 Воспоминание слишком длинное. Максимум — 300 символов.")
    memories = personal_memories.setdefault(uid, [])
    if any(entry.get("text", "").casefold() == text.casefold() for entry in memories):
        return await ctx.send("🦊 Я уже помню это!")
    memories.append({"text": text, "created_at": current_time_iso(), "created_by": uid})
    del memories[:-100]
    award_relationship(uid, 2, source="memory", daily_limit=4)
    first_memory = award_achievement(uid, "Первое воспоминание")
    save_memory()
    suffix = "\n🏅 Достижение: **Первое воспоминание**!" if first_memory else ""
    await ctx.send(f"🧠 Хорошо, я запомню: «{text}»{suffix}")


@bot.command(name="память")
async def память(ctx: commands.Context, action: str = ""):
    uid = ctx.author.id
    profile = _ensure_profile(uid)
    action = action.lower().strip()

    if action in ("выкл", "выключить", "off"):
        profile["memory_enabled"] = False
        personal_memories.pop(uid, None)
        user_memory.pop(uid, None)
        save_memory()
        return await ctx.send("🦊 Личная память отключена, сохранённые личные воспоминания удалены. Групповая память не затронута.")
    if action in ("вкл", "включить", "on"):
        profile["memory_enabled"] = True
        save_memory()
        return await ctx.send("🧠 Личная память снова включена. Новые воспоминания сохраняются только по явной команде `!запомни`.")
    if action in ("очистить", "clear"):
        personal_memories.pop(uid, None)
        user_memory.pop(uid, None)
        save_memory()
        return await ctx.send("🧹 Твои сохранённые личные воспоминания удалены.")

    entries = personal_memories.get(uid, [])
    last_message = user_memory.get(uid)
    status = "включена" if profile.get("memory_enabled", True) else "выключена"
    if not entries and not last_message:
        private_text = f"🧠 Личная память {status}. Пока нет сохранённых воспоминаний. Добавить: `!запомни ...`"
    else:
        lines = [f"🧠 **Твоя память** (личная память {status})"]
        for index, entry in enumerate(entries[-15:], start=max(1, len(entries) - 14)):
            lines.append(f"{index}. {entry['text']}")
        if last_message and profile.get("memory_enabled", True):
            lines.append(f"\nПоследнее замеченное сообщение: {last_message[:200]}")
        lines.append("\nУдалить личную память: `!память очистить` · Отключить: `!память выкл`")
        private_text = "\n".join(lines)

    # Personal memories must not be exposed in a shared server channel.
    try:
        await ctx.author.send(private_text)
    except discord.Forbidden:
        return await ctx.send("🦊 Не могу отправить память в личные сообщения. Разреши личные сообщения от участников сервера и повтори команду; содержимое памяти не опубликовано в этом канале.")
    if ctx.guild:
        await ctx.send("🦊 Отправила твою память в личные сообщения.")


@bot.command(name="группа_запомни")
@commands.guild_only()
async def группа_запомни(ctx: commands.Context, *, text: str = ""):
    text = text.strip()
    if not text:
        return await ctx.send("Укажи общий факт: `!группа_запомни наша команда называется Лисья стая`")
    if len(text) > 300:
        return await ctx.send("🦊 Максимум — 300 символов.")
    gid = str(ctx.guild.id)
    entries = group_memories.setdefault(gid, [])
    if any(entry.get("text", "").casefold() == text.casefold() for entry in entries):
        return await ctx.send("🦊 Это уже есть в общей памяти!")
    entries.append({"text": text, "created_at": current_time_iso(), "created_by": ctx.author.id})
    del entries[:-100]
    save_memory()
    await ctx.send(f"🦊 Запомнила для этого сервера: «{text}»")


@bot.command(name="группа_память")
@commands.guild_only()
async def группа_память(ctx: commands.Context):
    entries = group_memories.get(str(ctx.guild.id), [])
    if not entries:
        return await ctx.send("🧠 Общая память этого сервера пока пуста. Добавить факт: `!группа_запомни ...`")
    lines = ["🧠 **Общая память сервера**"]
    for index, entry in enumerate(entries[-15:], start=max(1, len(entries) - 14)):
        lines.append(f"{index}. {entry['text']}")
    lines.append("\nУдаление записи: `!группа_забыть номер` (автор записи или администратор).")
    await send_long(ctx, "\n".join(lines))


@bot.command(name="группа_забыть")
@commands.guild_only()
async def группа_забыть(ctx: commands.Context, index: int):
    gid = str(ctx.guild.id)
    entries = group_memories.get(gid, [])
    if index < 1 or index > len(entries):
        return await ctx.send("🦊 Номер записи не найден. Посмотри список командой `!группа_память`.")
    target = entries[index - 1]
    is_owner = target.get("created_by") == ctx.author.id
    if not is_owner and not is_admin(ctx):
        return await ctx.send("🦊 Удалить эту запись может её автор или администратор сервера.")
    removed = entries.pop(index - 1)
    save_memory()
    await ctx.send(f"🧹 Удалена общая запись: «{removed['text']}»")

# ======================================================
# MOOD AND PERSONAL PROFILES
# ======================================================

@bot.command(name="настроение")
async def настроение(ctx: commands.Context, *, requested: str = ""):
    requested = requested.lower().strip()
    aliases = {
        "забота": "заботливое", "заботливое": "заботливое", "заботливая": "заботливое",
        "радость": "радостное", "радостное": "радостное", "весёлое": "радостное", "веселое": "радостное",
        "сонное": "сонное", "сон": "сонное",
        "игривое": "игривое", "игра": "игривое",
    }
    if requested:
        selected = aliases.get(requested)
        if not selected:
            return await ctx.send("Доступные настроения: заботливое, радостное, сонное, игривое.")
        set_mood(selected)
        save_memory()
    else:
        # Keep the current mood, but occasionally shift it for variety.
        if random.random() < 0.18:
            set_mood(random.choice(list(SENKO_MOODS.keys())))
        save_memory()
    await ctx.send(f"🦊 **Сейчас я {current_mood}.**\n{random.choice(SENKO_MOODS[current_mood])}")


@bot.command(name="профиль")
async def профиль(ctx: commands.Context, member: Optional[discord.Member] = None):
    member = member or ctx.author
    profile = _ensure_profile(member.id)
    points = int(profile.get("relationship_points", 0))
    level_name, level_num = relationship_level(points)
    next_targets = {1: 25, 2: 75, 3: 150}
    next_target = next_targets.get(level_num)
    progress = f"{points}/{next_target} очков до следующего уровня" if next_target else "Максимальный уровень достигнут"
    achievements = profile.get("achievements", [])
    embed = discord.Embed(title=f"🦊 Профиль — {member.display_name}", color=0xFF8C00)
    embed.add_field(name="💗 Отношения с Сенко", value=f"**{level_name}** · уровень {level_num}\n{progress}", inline=False)
    embed.add_field(name="🏅 Достижения", value="\n".join(f"• {a}" for a in achievements[-10:]) or "Пока нет", inline=False)
    embed.add_field(name="🧠 Личная память", value="Включена" if profile.get("memory_enabled", True) else "Выключена", inline=True)
    embed.add_field(name="🍃 Листики", value=str(get_balance(member.id)), inline=True)
    await ctx.send(embed=embed)


@bot.command(name="достижения")
async def достижения(ctx: commands.Context):
    profile = _ensure_profile(ctx.author.id)
    unlocked = profile.get("achievements", [])
    all_achievements = ["Первый поиск", "Первая победа в игре", "Первое воспоминание", "Участник викторины"]
    lines = [f"✅ {name}" if name in unlocked else f"▫️ {name}" for name in all_achievements]
    await ctx.send("🏅 **Достижения Сенкосан**\n" + "\n".join(lines))


@bot.command(name="сенко_предпочтение")
async def сенко_предпочтение(ctx: commands.Context, *, category: str = ""):
    category = category.lower().strip()
    profile = _ensure_profile(ctx.author.id)
    if not category:
        current = profile["preferences"].get("preferred_media") or "не выбрано"
        return await ctx.send(f"🦊 Твоя предпочтительная категория: **{current}**. Установить: `!сенко_предпочтение радость` или `!сенко_предпочтение выкл`.")
    if category in ("выкл", "нет", "сброс"):
        profile["preferences"]["preferred_media"] = ""
    elif category in FOX_MEDIA and category != "gif":
        profile["preferences"]["preferred_media"] = category
    else:
        return await ctx.send("Такой категории нет. Используй категорию из `!лиса_помощь`.")
    save_memory()
    await ctx.send("🦊 Предпочтение сохранено!")

# ======================================================
# RANDOM EVENTS
# ======================================================

@bot.command(name="сценка")
async def сценка(ctx: commands.Context):
    scene_type, scene_text = random.choice(RANDOM_SCENES)
    await ctx.send(scene_text)
    preferred = _ensure_profile(ctx.author.id)["preferences"].get("preferred_media")
    category = preferred if preferred and _all_media_urls(preferred) else {
        "comfort": "грусть", "happy": "радость", "playful": "радость", "sleepy": "сонная"
    }.get(scene_type, "радость")
    if _all_media_urls(category) and random.random() < 0.65:
        await send_senko_media(ctx, category)
    award_relationship(ctx.author.id, 1, source="scene", daily_limit=3)
    save_memory()


def maybe_random_event(channel_id: int, now: datetime.datetime) -> Optional[str]:
    key = str(channel_id)
    previous = _parse_datetime(last_event_by_channel.get(key))
    cooldown = max(5, int(settings.get("event_cooldown_minutes", 45)))
    if previous and (now - previous).total_seconds() < cooldown * 60:
        return None
    if random.random() > 0.025:
        return None
    last_event_by_channel[key] = now.isoformat()
    return random.choice(RANDOM_SCENES)[1]

# ======================================================
# MINI-GAMES (new, separate from legacy games)
# ======================================================

@bot.command(name="игры")
async def игры(ctx: commands.Context):
    await ctx.send(
        "🎮 **Мини-игры Сенкосан 2.0**\n"
        "`!угадайчисло` — угадай число от 1 до 10\n"
        "`!числоответ 5` — сделать попытку\n"
        "`!викторина` — вопрос с вариантами\n"
        "`!викторинаответ A` — ответить A/B\n"
        "`!эмоция` — старая игра на настроение\n"
        "`!правда` — старая игра «правда или ложь»"
    )


def _game_key(ctx: commands.Context) -> str:
    return f"{ctx.guild.id if ctx.guild else 'dm'}:{ctx.channel.id}:{ctx.author.id}"


@bot.command(name="угадайчисло")
@commands.cooldown(1, 8, commands.BucketType.user)
async def угадайчисло(ctx: commands.Context):
    key = _game_key(ctx)
    number_games[key] = {"number": random.randint(1, 10), "attempts": 0, "started_at": current_time_iso()}
    await ctx.send("🦊 Я загадала число от **1 до 10**. Отвечай: `!числоответ 5`.")


@bot.command(name="числоответ")
async def числоответ(ctx: commands.Context, guess: int):
    key = _game_key(ctx)
    game = number_games.get(key)
    if not game:
        return await ctx.send("Сначала начни игру: `!угадайчисло`.")
    if guess < 1 or guess > 10:
        return await ctx.send("Число должно быть от 1 до 10.")
    game["attempts"] += 1
    target = game["number"]
    if guess == target:
        attempts = game["attempts"]
        number_games.pop(key, None)
        reward = max(3, 12 - (attempts - 1) * 2)
        balances[ctx.author.id] = get_balance(ctx.author.id) + reward
        award_relationship(ctx.author.id, 3, source="game", daily_limit=9)
        award_achievement(ctx.author.id, "Первая победа в игре")
        save_memory()
        await ctx.send(f"🎉 Угадал(а)! Это было **{target}**. Попыток: {attempts}. Награда: **+{reward} 🍃**")
    elif game["attempts"] >= 5:
        number_games.pop(key, None)
        await ctx.send(f"🦊 Попытки закончились! Я загадала **{target}**. Попробуем ещё раз: `!угадайчисло`.")
    else:
        await ctx.send("Моё число больше! 🐾" if guess < target else "Моё число меньше! 🐾")


QUIZ_QUESTIONS = [
    {"question": "Как называется самая маленькая разновидность лис?", "A": "Фенек", "B": "Рыжая лиса", "answer": "A"},
    {"question": "Для чего лисе помогает хвост?", "A": "Только для плавания", "B": "Для баланса", "answer": "B"},
    {"question": "Как называют магических лис в японском фольклоре?", "A": "Кицунэ", "B": "Тануки", "answer": "A"},
]


@bot.command(name="викторина")
@commands.cooldown(1, 8, commands.BucketType.user)
async def викторина(ctx: commands.Context):
    key = _game_key(ctx)
    q = random.choice(QUIZ_QUESTIONS)
    quiz_games[key] = {**q, "started_at": current_time_iso()}
    await ctx.send(f"🦊 **Викторина**\n{q['question']}\nA) {q['A']}\nB) {q['B']}\nОтвет: `!викторинаответ A` или `!викторинаответ B`.")


@bot.command(name="викторинаответ")
async def викторинаответ(ctx: commands.Context, answer: str = ""):
    key = _game_key(ctx)
    game = quiz_games.pop(key, None)
    if not game:
        return await ctx.send("Сначала начни игру: `!викторина`.")
    answer = answer.upper().strip()
    if answer not in ("A", "B"):
        quiz_games[key] = game
        return await ctx.send("Ответ должен быть A или B.")
    if answer == game["answer"]:
        balances[ctx.author.id] = get_balance(ctx.author.id) + 5
        award_relationship(ctx.author.id, 2, source="game", daily_limit=9)
        award_achievement(ctx.author.id, "Участник викторины")
        save_memory()
        await ctx.send("✨ Верно! Награда: **+5 🍃**")
    else:
        await ctx.send(f"Не совсем! Правильный ответ: **{game[game['answer']]}**.")

# ======================================================
# DIAGNOSTICS — owner/admin only for detailed checks
# ======================================================

@bot.command(name="сенко_статус")
async def сенко_статус(ctx: commands.Context):
    status = "✅ доступна" if memory_write_allowed else "⚠️ запись отключена ради защиты данных"
    media_count = len(_all_media_urls())
    verified_count = sum(1 for value in media_status.values() if isinstance(value, dict) and value.get("ok") is True)
    failed_count = sum(1 for value in media_status.values() if isinstance(value, dict) and value.get("ok") is False)
    embed = discord.Embed(title="🦊 Senko 2.0 — статус", color=0xFF8C00)
    embed.add_field(name="Хранилище", value=status, inline=False)
    embed.add_field(name="Медиа в каталоге", value=str(media_count), inline=True)
    embed.add_field(name="Проверены / доступны", value=f"{verified_count} / {media_count}", inline=True)
    embed.add_field(name="Ошибки URL", value=str(failed_count), inline=True)
    embed.add_field(name="Настроение", value=current_mood, inline=True)
    embed.add_field(name="Профили", value=str(len(profiles)), inline=True)
    embed.add_field(name="Пользователи с памятью", value=str(len(personal_memories)), inline=True)
    if memory_load_error:
        embed.add_field(name="Предупреждение", value=memory_load_error[:900], inline=False)
    await ctx.send(embed=embed)


@bot.command(name="сенко_диагностика")
async def сенко_диагностика(ctx: commands.Context):
    if not is_admin(ctx):
        return await ctx.send("🦊 Подробная диагностика доступна администраторам сервера с разрешением Manage Server.")
    checks = []
    checks.append(("data.json существует", DATA_FILE.exists()))
    checks.append(("Запись разрешена", memory_write_allowed))
    checks.append(("Профили загружены", isinstance(profiles, dict)))
    checks.append(("Каталог медиа читается", isinstance(FOX_MEDIA, dict)))
    checks.append(("Модули игр доступны", isinstance(number_games, dict) and isinstance(quiz_games, dict)))
    lines = [f"{'✅' if ok else '⚠️'} {name}" for name, ok in checks]
    if memory_load_error:
        lines.append(f"\nОшибка/предупреждение хранения: {memory_load_error[:500]}")
    lines.append(f"\nПуть данных: `{DATA_FILE.resolve()}`")
    lines.append(f"Резервные копии: `{BACKUP_DIR.resolve()}`")
    await send_long(ctx, "🛠️ **Диагностика Senko 2.0**\n" + "\n".join(lines))


@bot.command(name="сенко_медиа_проверить")
async def сенко_медиа_проверить(ctx: commands.Context):
    if not is_admin(ctx):
        return await ctx.send("🦊 Проверка ссылок доступна администраторам сервера.")
    urls = _all_media_urls()
    if not urls:
        return await ctx.send("🦊 Каталог медиа пуст.")
    await ctx.send(f"🦊 Проверяю {len(urls)} медиа-ссылок. Это может занять некоторое время…")
    timeout = aiohttp.ClientTimeout(total=10, connect=5)
    connector = aiohttp.TCPConnector(limit=8, ssl=True)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        semaphore = asyncio.Semaphore(8)
        async def limited_check(url: str):
            async with semaphore:
                return url, await check_media_url(session, url)
        results = await asyncio.gather(*(limited_check(url) for url in urls))
    lines = []
    for url, result in results:
        media_status[url] = result
        mark = "✅" if result.get("ok") else "❌"
        lines.append(f"{mark} `{result.get('status') or 'ERR'}` {result.get('content_type', 'unknown')} — {url}")
    save_memory()
    await send_long(ctx, "**Результаты проверки медиа**\n" + "\n".join(lines))
    await ctx.send("ℹ️ HTTP-проверка не гарантирует, что Discord покажет анимацию: это отдельно проверяется отправкой в клиент.")


@bot.command(name="сенко_авто")
async def сенко_авто(ctx: commands.Context, toggle: str = ""):
    if not is_admin(ctx):
        return await ctx.send("🦊 Настройка самостоятельной активности доступна администраторам сервера.")
    toggle = toggle.lower().strip()
    if toggle in ("вкл", "on", "да"):
        settings["autonomous_enabled"] = True
        save_memory()
        return await ctx.send("🦊 Самостоятельная активность включена.")
    if toggle in ("выкл", "off", "нет"):
        settings["autonomous_enabled"] = False
        save_memory()
        return await ctx.send("🦊 Самостоятельная активность отключена.")
    current = "включена" if settings.get("autonomous_enabled", True) else "отключена"
    await ctx.send(f"Самостоятельная активность {current}. Используй `!сенко_авто вкл` или `!сенко_авто выкл`.")

# ======================================================
# HELP
# ======================================================

@bot.command(name="помощь", aliases=["help"])
async def помощь(ctx: commands.Context):
    embed = discord.Embed(title="🦊 Команды Сенкосан 2.0", description="Старые команды сохранены; ниже — основные возможности.", color=0xFF8C00)
    embed.add_field(name="🎮 Поиск и экономика", value="`!поиск` · `!рюкзак` · `!магазин` · `!купить название` · `!покормить еда`", inline=False)
    embed.add_field(name="🕹️ Игры", value="`!эмоция` · `!угадай настроение` · `!правда` · `!ответ правда/ложь`\n`!игры` · `!угадайчисло` · `!числоответ 5` · `!викторина` · `!викторинаответ A`", inline=False)
    embed.add_field(name="🖼️ Медиа и настроение", value="`!лиса [категория]` · `!лиса_помощь` · `!настроение [состояние]` · `!сценка`", inline=False)
    embed.add_field(name="🧠 Память и профиль", value="`!запомни текст` · `!память` · `!память выкл/вкл/очистить` · `!профиль` · `!достижения`", inline=False)
    embed.add_field(name="👥 Память сервера", value="`!группа_запомни текст` · `!группа_память` · `!группа_забыть номер`", inline=False)
    embed.add_field(name="🛠️ Статус", value="`!сенко_статус` · `!сенко_диагностика` (админы) · `!сенко_медиа_проверить` (админы)", inline=False)
    await ctx.send(embed=embed)

# ======================================================
# MESSAGE HANDLER
# ======================================================

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Always pass prefixed messages to commands and don't treat them as memories.
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    uid = message.author.id
    now = datetime.datetime.now()
    profile = _ensure_profile(uid)

    # Preserve old behaviour: keep a short last-message note for users who have memory enabled.
    if profile.get("memory_enabled", True):
        if uid not in first_seen:
            first_seen[uid] = now.isoformat()
        user_memory[uid] = message.content[:200]
        last_messages[uid] = now
        message_counts[uid] = message_counts.get(uid, 0) + 1

    inferred = infer_mood(message.content)
    if inferred:
        set_mood(inferred)

    if "привет" in message.content.lower():
        await message.channel.send("Привет! 🦊")
    elif message.content and settings.get("random_events_enabled", True):
        scene = maybe_random_event(message.channel.id, now)
        if scene:
            try:
                await message.channel.send(scene)
            except discord.HTTPException as error:
                log.warning("Random event send failed: %s", error)
                last_event_by_channel.pop(str(message.channel.id), None)

    # Persist only non-command traffic; new memory entries require explicit !запомни.
    save_memory()
    await bot.process_commands(message)

# ======================================================
# STARTUP AND SHUTDOWN
# ======================================================

@bot.event
async def on_ready():
    log.info("Senko 2.0 online as %s", bot.user)
    log.info("Persistent data path: %s", DATA_FILE.resolve())
    if memory_write_allowed:
        log.info("Persistent memory enabled. Existing keys will be preserved.")
    else:
        log.error("Persistent writes disabled to protect data: %s", memory_load_error)
    if not fox_lifecycle.is_running():
        fox_lifecycle.start()
    if not hunger_tick.is_running():
        hunger_tick.start()
    if not daily_fact_task.is_running():
        daily_fact_task.start()


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"🦊 Не хватает аргумента: `{error.param.name}`. Посмотри `!помощь`.")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send("🦊 Не удалось разобрать аргумент. Проверь команду и попробуй ещё раз.")
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"🦊 Нужно немного подождать: {max(1, int(error.retry_after))} сек.")
        return
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("🦊 Эта команда работает только на сервере Discord.")
        return
    log.error("Unhandled command error: %r", error, exc_info=(type(error), error, error.__traceback__))
    await ctx.send("🦊 Произошла ошибка команды. Владелец может проверить логи и `!сенко_диагностика`.")


@bot.event
async def on_disconnect():
    # Best-effort save on disconnect; state is also saved during normal operations.
    save_memory()


TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    log.info("Discord token found. Starting Senko 2.0…")
    bot.run(TOKEN)
else:
    log.error("Token not found. Set DISCORD_TOKEN in your .env file.")
