"""Проверки автономного диалогового движка без Discord и сети."""
import datetime as dt
import random
import unittest

from senko_dialogue import LocalDialogue


def say(engine, text, *, uid=1, channel=1, facts=(), group=(), mood="заботливое"):
    return engine.reply(
        user_id=uid, channel_id=channel, user_name="Тестер", text=text,
        mood=mood, hunger=50, relationship_points=75,
        memories=facts, group_facts=group,
        now=dt.datetime(2026, 10, 23, 14, 30),
    )


class OfflineDialogueTests(unittest.TestCase):
    def setUp(self):
        random.seed(1)
        self.bot = LocalDialogue()

    def test_greeting(self):
        self.assertTrue(say(self.bot, "Привет, Сенко"))

    def test_mood(self):
        self.assertIn("сонная", say(self.bot, "Как дела?", mood="сонное"))

    def test_memory(self):
        response = say(self.bot, "Что ты помнишь обо мне?", facts=["Любимый цвет синий"])
        self.assertIn("Любимый цвет синий", response)

    def test_memory_isolation(self):
        say(self.bot, "Что ты помнишь обо мне?", uid=1, facts=["Секрет первого"])
        response = say(self.bot, "Что ты помнишь обо мне?", uid=2)
        self.assertNotIn("Секрет первого", response)

    def test_followup(self):
        say(self.bot, "Я устал")
        response = say(self.bot, "Из-за рисования")
        self.assertIn("рис", response.lower())

    def test_forget(self):
        say(self.bot, "Я устал")
        self.bot.forget_user(1)
        self.assertFalse(any(key[1] == 1 for key in self.bot._contexts))


if __name__ == "__main__":
    unittest.main()
