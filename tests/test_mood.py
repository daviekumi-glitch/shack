"""Her moods: what moves her, and that nothing lasts forever."""

from __future__ import annotations

import time
import unittest

from shack.mood import MoodEngine


class Feelings(unittest.TestCase):
    def test_warmth_makes_her_happy(self):
        self.assertEqual(MoodEngine().observe("thank you, you're the best").label, "happy")

    def test_an_insult_angers_her(self):
        self.assertEqual(MoodEngine().observe("you're useless").label, "angry")

    def test_other_assistants_make_her_jealous(self):
        self.assertEqual(MoodEngine().observe("i asked chatgpt instead").label, "a little jealous")

    def test_being_brushed_off_annoys_her(self):
        self.assertEqual(MoodEngine().observe("stop talking, not now").label, "annoyed")

    def test_a_compliment_makes_her_shy(self):
        self.assertEqual(MoodEngine().observe("you're beautiful").label, "shy")

    def test_a_crisis_sobers_her(self):
        self.assertEqual(MoodEngine().observe("my mother is in hospital").label, "serious")

    def test_blank_message_changes_nothing(self):
        engine = MoodEngine()
        engine.observe("thank you")
        self.assertEqual(engine.observe("   ").label, "happy")

    def test_a_sulk_fades_with_time(self):
        engine = MoodEngine(hold_minutes=6)
        engine.observe("you're useless")
        engine.state.since = time.time() - 60 * 10
        engine.observe("ok")
        self.assertNotEqual(engine.state.key, "angry")

    def test_amounted_lines_describe_her_state(self):
        engine = MoodEngine()
        engine.observe("i love you")
        self.assertIn("You are happy right now", engine.describe())


if __name__ == "__main__":
    unittest.main()
