"""Deep memory: what she learns, what she recalls, and who built her."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from shack import deep_memory
from shack.agent import CREATOR, ShackAgent
from shack.config import Config


class Learning(unittest.TestCase):
    def test_name_and_place_keep_their_capitals(self):
        facts = dict(deep_memory.extract_facts("My name is afick and I live in Blantyre"))
        self.assertEqual(facts["user_name"], "Afick")
        self.assertEqual(facts["location"], "Blantyre")

    def test_remember_captures_the_sentence(self):
        facts = deep_memory.extract_facts("Remember that I prefer tea over coffee")
        self.assertIn(("note", "I prefer tea over coffee"), facts)

    def test_likes_and_people(self):
        facts = dict(deep_memory.extract_facts("I love reggae music"))
        self.assertEqual(facts["likes"], "reggae music")
        facts = dict(deep_memory.extract_facts("my sister is called thandi"))
        self.assertEqual(facts["person_sister"], "Thandi")

    def test_ordinary_chat_teaches_nothing(self):
        self.assertEqual(deep_memory.extract_facts("what is the weather today?"), [])


class Recalling(unittest.TestCase):
    FACTS = [
        ("user_name", "Afick"),
        ("person_sister", "Thandi"),
        ("likes", "reggae music"),
        ("dislikes", "loud ringtones"),
    ]

    def test_the_question_brings_up_the_right_memory(self):
        keys = [k for k, _ in deep_memory.recall(self.FACTS, "what is my sister called?")]
        self.assertIn("person_sister", keys)

    def test_essentials_always_come_back(self):
        keys = [k for k, _ in deep_memory.recall(self.FACTS, "hello")]
        self.assertIn("user_name", keys)

    def test_prompt_block_is_readable(self):
        block = deep_memory.summarise_for_prompt(self.FACTS)
        self.assertIn("user name: Afick", block)
        self.assertTrue(block.startswith("- "))

    def test_empty_memory_says_so(self):
        self.assertEqual(deep_memory.summarise_for_prompt([]), "nothing stored yet")


class Identity(unittest.TestCase):
    def _agent(self):
        tmp = Path(tempfile.mkdtemp())
        config = Config.load()
        config.api_key = "gsk_test"
        config.data_dir = tmp
        return ShackAgent(config)

    def test_she_knows_her_creator(self):
        agent = self._agent()
        self.assertEqual(agent.memory.get_fact("creator"), CREATOR)
        self.assertIn(CREATOR, agent.system_prompt())

    def test_what_she_learns_survives_restart(self):
        agent = self._agent()
        agent.learn("My name is Afick and I live in Blantyre")
        again = ShackAgent(agent.config)
        self.assertEqual(again.memory.get_fact("user_name"), "Afick")
        self.assertEqual(again.memory.get_fact("location"), "Blantyre")


if __name__ == "__main__":
    unittest.main()
