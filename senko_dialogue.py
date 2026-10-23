"""Локальный диалоговый движок Сенко: без нейросетей, API и сетевых запросов.

Хранит только краткий временный контекст разговора в памяти процесса.
Постоянные факты передаются вызывающим кодом после проверки пользовательских настроек.
"""
from __future__ import annotations

import datetime as dt
import random
import re
import time
from typing import Iterable


class LocalDialogue:
    CONTEXT_TTL_SECONDS = 60 * 60
    MAX_CONTEXTS = 2000

    def __init__(self) -> None:
        self._contexts: dict[tuple[int, int], dict] = {}

    def forget_user(self, user_id: int) -> None:
        """Забыть временный диалог пользователя во всех каналах."""
        for key in list(self._contexts):
            if key[1] == user_id:
                self._contexts.pop(key, None)

    @staticmethod
    def _has(text: str, *parts: str) -> bool:
        return any(part in text for part in parts)

    @staticmethod
    def _choose(options: list[str], previous: str) -> str:
        choices = [value for value in options if value != previous]
        return random.choice(choices or options)

    @staticmethod
    def _topic(text: str) -> str | None:
        if LocalDialogue._has(text, "рисов", "рисую", "нарис", "рисунк", "арт", "скетч"):
            return "drawing"
        if LocalDialogue._has(text, "монтаж", "видео", "озвуч", "ролик", "давинчи"):
            return "video"
        if LocalDialogue._has(text, "играю", "играл", "поиграл", "игр", "майнкрафт"):
            return "games"
        if LocalDialogue._has(text, "учеб", "школ", "урок", "экзамен", "домашк"):
            return "study"
        return None

    @staticmethod
    def _relevant_facts(question: str, facts: Iterable[str], limit: int = 3) -> list[str]:
        """Упрощённый подбор явных воспоминаний по общим основам слов."""
        values = [value.strip() for value in facts if isinstance(value, str) and value.strip()]
        if not values:
            return []
        if LocalDialogue._has(question, "что ты помнишь", "что помнишь", "расскажи обо мне",
                              "что знаешь обо мне", "мои воспоминания"):
            return values[-limit:]
        ignored = {"какой", "какая", "какое", "какие", "моего", "моей", "меня", "моё",
                   "тебе", "себе", "помнишь", "скажи", "расскажи", "пожалуйста"}
        terms = {word[:5] for word in re.findall(r"[а-яёa-z0-9]{4,}", question) if word not in ignored}
        scored: list[tuple[int, int, str]] = []
        for index, value in enumerate(values):
            tokens = {word[:5] for word in re.findall(r"[а-яёa-z0-9]{4,}", value.casefold())}
            score = len(terms & tokens)
            if score:
                scored.append((score, index, value))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [value for _, _, value in scored[:limit]]

    def reply(
        self,
        *,
        user_id: int,
        channel_id: int,
        user_name: str,
        text: str,
        mood: str,
        hunger: int,
        relationship_points: int,
        memories: Iterable[str] = (),
        group_facts: Iterable[str] = (),
        now: dt.datetime | None = None,
    ) -> str:
        now = now or dt.datetime.now().astimezone()
        normalized = re.sub(r"\s+", " ", text.casefold()).strip()
        moment = time.monotonic()
        key = (channel_id, user_id)
        context = self._contexts.get(key)
        if context is None or moment - context.get("last_active", 0) > self.CONTEXT_TTL_SECONDS:
            context = {"topic": None, "last_intent": None, "last_reply": "", "last_active": moment}
            self._contexts[key] = context
        if len(self._contexts) > self.MAX_CONTEXTS:
            oldest = min(self._contexts, key=lambda item: self._contexts[item].get("last_active", 0))
            if oldest != key:
                self._contexts.pop(oldest, None)
        previous = context["last_reply"]
        topic = self._topic(normalized)
        close = relationship_points >= 75
        time_of_day = ("утро" if 5 <= now.hour < 12
                       else "день" if 12 <= now.hour < 18
                       else "вечер" if 18 <= now.hour < 23 else "ночь")

        def finish(options: list[str], intent: str | None = None, new_topic: str | None = None) -> str:
            result = self._choose(options, previous)
            context.update(last_reply=result, last_intent=intent, last_active=moment)
            if new_topic is not None:
                context["topic"] = new_topic
            elif topic is not None:
                context["topic"] = topic
            return result

        if self._has(normalized, "что ты помнишь", "что помнишь", "помнишь обо мне",
                     "что знаешь обо мне", "мои воспоминания", "мой любим", "моя любим",
                     "моё любим", "мое любим"):
            found = self._relevant_facts(normalized, memories)
            if found:
                return finish(["Хи-хи, вот что я помню: " + "; ".join(found) + ". 🦊"], "memory")
            return finish(["Пока у меня нет подходящих записей о тебе. Ты можешь рассказать мне факт через /запомни! 🌸"], "memory")

        if self._has(normalized, "что помнишь о сервере", "что знаешь о сервере",
                     "память сервера", "помнишь про сервер"):
            found = self._relevant_facts("что ты помнишь", group_facts)
            if found:
                return finish(["В общей памяти сервера записано: " + "; ".join(found) + ". 🦊"], "group_memory")
            return finish(["Пока общая память сервера пуста. Её можно пополнить через /группа_запомни!"], "group_memory")

        if context.get("last_intent") == "why_tired" and (
            topic or self._has(normalized, "из-за", "потому что", "весь день")
        ):
            if topic == "drawing":
                return finish(["Ох, столько рисовал! Дай рукам немного отдохнуть. Хочешь, я посижу рядом? 🌸",
                               "Рисование требует сил. Ты сегодня многое сделал — пора немного отдохнуть! 🦊"], "comfort", "drawing")
            if topic == "video":
                return finish(["Монтаж способен здорово вымотать. Может, отвлечёшься от таймлайна и выпьешь чаю? 🍵"], "comfort", "video")
            if topic == "study":
                return finish(["После учёбы отдых особенно важен. Пойдём ненадолго отвлечёмся? 🌸"], "comfort", "study")
            return finish(["Понимаю… Звучит утомительно. Хочешь рассказать, что было самым сложным? 🦊"], "comfort", topic or "tired")

        if self._has(normalized, "спокойной ночи", "пойду спать", "иду спать", "хочу спать"):
            return finish(["Сладких снов! Я тихонечко укрою тебя пушистыми хвостиками. 🌙",
                           "Доброй ночи! Пусть тебе приснится что-нибудь хорошее. 💤"], "sleep", "sleep")

        if self._has(normalized, "привет", "здравствуй", "доброе утро", "добрый день",
                     "добрый вечер", "куку", "хай", "hello"):
            if time_of_day == "ночь":
                return finish(["Ой, ты ещё не спишь? Хи-хи, рада тебя видеть! 🌙",
                               "Приве-ет! У нас тут уже совсем ночной час. 🦊"], "greeting")
            if mood == "сонное":
                return finish(["М-м… привет! *Сенко сонно шевелит ушками.* 💤"], "greeting")
            if close:
                return finish(["А-а, мой дорогой друг! Как же я рада тебя видеть! 💛",
                               "Ты пришёл! *Сенко весело машет хвостиками.* Как твои дела? 🦊"], "greeting")
            return finish(["Приве-ет! Как проходит твой " + time_of_day + "? 🌸",
                           "Ой, привет! *Сенко радостно шевелит ушками.* 🦊"], "greeting")

        if self._has(normalized, "спасибо", "благодарю", "ты лучшая"):
            return finish(["Хи-хи, всегда пожалуйста! 💛",
                           "Мне очень приятно помогать. Обращайся! 🦊"], "thanks")

        if self._has(normalized, "мне грустно", "грустно", "одиноко", "плохо на душе",
                     "расстроен", "расстроена", "тревожно"):
            return finish(["Иди сюда, немного посидим рядом. Хочешь рассказать, что произошло? 🌸",
                           "Жаль, что тебе сейчас тяжело. Я могу побыть рядом и послушать тебя. 💛"], "comfort", "sad")

        if self._has(normalized, "устал", "устала", "вымотал", "усталость"):
            return finish(["Ох… ты, наверное, очень устал. Что тебя сегодня так вымотало? 🦊",
                           "Присядь рядом, я приготовлю чай. Расскажешь, из-за чего устал? 🍵"], "why_tired", "tired")

        if self._has(normalized, "получилось", "я закончил", "я закончила", "победил",
                     "победила", "сделал", "сделала") and not "не получилось" in normalized:
            if topic == "drawing":
                return finish(["Ура-а! Ты закончил рисунок! Наверняка вложил в него много старания. 🌸"], "celebrate", "drawing")
            return finish(["Ух ты, здорово! Я за тебя рада! Расскажешь подробнее? ✨",
                           "Хи-хи, молодец! *Сенко радостно машет хвостиками.* 🦊"], "celebrate")

        if self._has(normalized, "как дела", "как пожива", "как ты себя чувствуешь",
                     "какое у тебя настроение", "ты как"):
            if hunger >= 85:
                return finish(["Животик урчит, но в остальном всё хорошо! Может, угостишь меня чем-нибудь? 🍡"], "mood")
            moods = {
                "сонное": "М-м, немного сонная… Но тебе всегда рада! 💤",
                "игривое": "У-ху! Мне сегодня хочется играть и шалить! 🐾",
                "радостное": "Замечательно! Хвостики сами собой танцуют! ✨",
                "заботливое": "Всё хорошо, спасибо, что спросил! А как ты себя чувствуешь? 🌸",
            }
            return finish([moods.get(mood, "Всё хорошо! 🦊")], "mood")

        if self._has(normalized, "что делаешь", "чем занимаешься", "чем занята"):
            activities = {
                "утро": ["Готовлю завтрак и привожу хвостики в порядок! 🍡"],
                "день": ["Собираю травы для чая и любуюсь облаками. 🍵"],
                "вечер": ["Завариваю душистый чай. Составишь мне компанию? 🌸"],
                "ночь": ["Тихонько устраиваюсь поудобнее, чтобы никого не разбудить. 🌙"],
            }
            return finish(activities[time_of_day], "activity")

        if self._has(normalized, "сколько времени", "который час", "сколько сейчас"):
            return finish([f"По моим часам сейчас {now:%H:%M}. 🦊"], "clock")

        if topic == "drawing":
            return finish(["О, ты снова творишь? Что сейчас рисуешь? 🎨",
                           "Рисование — удивительное занятие! Как продвигается твоя работа? 🌸"], "topic", "drawing")
        if topic == "video":
            return finish(["Монтаж видео — кропотливая работа! Какая часть ролика у тебя сейчас в работе? 🎬",
                           "Ого, занимаешься видео? Надеюсь, таймлайн тебя сегодня не мучает! 🦊"], "topic", "video")
        if topic == "games":
            return finish(["О, игры! Во что сегодня играешь? 🎮",
                           "Хи-хи, расскажешь, что интересного случилось в игре? 🐾"], "topic", "games")
        if topic == "study":
            return finish(["Как идут дела с учёбой? Могу подбодрить тебя! 🌸"], "topic", "study")

        if "?" in normalized or re.match(r"^(как|что|почему|зачем|когда|кто|где)\b", normalized):
            return finish(["Хм-м, хороший вопрос! Я не всё знаю, но мне любопытно услышать, что ты об этом думаешь. 🦊",
                           "Я могу ошибаться в таких вещах. Расскажешь немного подробнее? 🌸"], "question")

        if context.get("topic") == "drawing":
            return finish(["А как продвигается рисунок? Я болею за тебя! 🎨"], "followup")
        if context.get("topic") == "tired":
            return finish(["Надеюсь, ты сможешь немного отдохнуть. Я побуду рядом. 🍵"], "followup")
        if mood == "сонное":
            return finish(["М-м… *Сенко сонно прижимает ушки.* Я слушаю тебя. 💤"], "smalltalk")
        if mood == "игривое":
            return finish(["Хи-хи! *Сенко озорно машет хвостиками.* Расскажешь ещё? 🐾"], "smalltalk")
        return finish(["Угу-угу! Мне интересно, продолжай. 🦊",
                       "Хи-хи, слушаю тебя внимательно! 🌸",
                       "Ого! И что было дальше? ✨"], "smalltalk")
