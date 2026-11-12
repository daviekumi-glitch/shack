"""Offline tests: no network, no API key needed.

Run with:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from shack.config import Config
from shack.memory import Memory
from shack.tools import ToolContext, build_registry
from shack import voices
from shack.voice import Voice, clean_for_speech, pace


def make_ctx(tmp: Path) -> ToolContext:
    config = Config(api_key="test-key", data_dir=tmp, voice_out=False)
    config.ensure_dirs()
    memory = Memory(config.db_path, session="tests")
    return ToolContext(config=config, memory=memory, brain=None, voice=None, confirm=None)


class RegistryTests(unittest.TestCase):
    def test_expected_tools_present(self) -> None:
        registry = build_registry()
        for name in (
            "get_time",
            "web_search",
            "fetch_url",
            "get_weather",
            "calculate",
            "remember_fact",
            "add_task",
            "set_reminder",
            "run_shell",
        ):
            self.assertIsNotNone(registry.get(name), f"missing tool {name}")

    def test_specs_are_valid_schemas(self) -> None:
        for spec in build_registry().specs():
            self.assertEqual(spec["type"], "function")
            self.assertIn("parameters", spec["function"])
            self.assertEqual(spec["function"]["parameters"]["type"], "object")


class ToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.ctx = make_ctx(self.tmp)
        self.registry = build_registry()

    def call(self, name: str, args: dict) -> str:
        return self.registry.call(name, args, self.ctx)

    def test_calculate(self) -> None:
        self.assertIn("465", self.call("calculate", {"expression": "(1200*0.35)+45"}))
        self.assertIn("4", self.call("calculate", {"expression": "sqrt(16)"}))
        self.assertIn("failed", self.call("calculate", {"expression": "__import__('os')"}))

    def test_convert_units(self) -> None:
        self.assertIn("7.456", self.call("convert_units", {"value": 12, "from_unit": "km", "to_unit": "mi"}))
        self.assertIn("212", self.call("convert_units", {"value": 100, "from_unit": "c", "to_unit": "f"}))

    def test_memory_roundtrip(self) -> None:
        self.call("remember_fact", {"key": "home_city", "value": "Blantyre"})
        self.assertIn("Blantyre", self.call("recall_facts", {"query": "city"}))
        self.call("forget_fact", {"key": "home_city"})
        self.assertIn("Nothing", self.call("recall_facts", {"query": "city"}))

    def test_tasks(self) -> None:
        self.call("add_task", {"title": "ship SHACK"})
        self.assertIn("ship SHACK", self.call("list_tasks", {}))
        self.call("complete_task", {"title_match": "SHACK"})
        self.assertIn("No open tasks", self.call("list_tasks", {}))

    def test_reminder(self) -> None:
        out = self.call("set_reminder", {"text": "stretch", "when": "25 minutes"})
        self.assertIn("stretch", out)
        self.assertIn("stretch", self.call("list_reminders", {}))
        reminder_id = int(out.split("#")[1].split()[0])
        self.call("cancel_reminder", {"reminder_id": reminder_id})
        self.assertIn("No reminders", self.call("list_reminders", {}))

    def test_safe_mode_blocks_destructive_shell(self) -> None:
        out = self.call("run_shell", {"command": "rm -rf /"})
        self.assertIn("safe mode", out)

    def test_unknown_tool_and_bad_arguments(self) -> None:
        self.assertIn("Unknown tool", self.call("teleport", {}))
        self.assertIn("bad arguments", self.call("calculate", {"expr": "1+1"}))


class HistoryTests(unittest.TestCase):
    def test_trim_keeps_newest(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        memory = Memory(tmp / "m.db", session="s")
        for i in range(10):
            memory.add_message("user", f"line {i}")
        memory.trim_messages(keep=3)
        kept = memory.recent_messages(10)
        self.assertEqual(len(kept), 3)
        self.assertEqual(kept[-1]["content"], "line 9")
        memory.close()

    def test_older_messages_does_not_deadlock(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        memory = Memory(tmp / "m2.db", session="s")
        for i in range(5):
            memory.add_message("user", f"line {i}")
        older = memory.older_messages(keep=2)
        self.assertEqual([m["content"] for m in older], ["line 0", "line 1", "line 2"])
        memory.close()


class VoiceTests(unittest.TestCase):
    def test_default_voice_is_the_warm_one(self) -> None:
        profile = voices.get(None)
        self.assertEqual(profile.key, "rumi")
        self.assertGreater(profile.pitch, 1.0)   # sits a little high
        self.assertLess(profile.rate, 1.0)       # and takes its time

    def test_unknown_voice_falls_back(self) -> None:
        self.assertEqual(voices.get("does-not-exist").key, "rumi")
        self.assertEqual(voices.get("ORION").key, "orion")

    def test_termux_commands_carry_pitch_and_rate(self) -> None:
        voice = Voice(enabled=False, profile="rumi")
        cmds = voice._commands("/usr/bin/termux-tts-speak", "termux-tts-speak", "hello")
        self.assertIn("-p", cmds[0])
        self.assertIn("1.06", " ".join(cmds[0]))
        self.assertIn("0.94", " ".join(cmds[0]))
        self.assertEqual(cmds[-1], ["/usr/bin/termux-tts-speak", "hello"])

    def test_espeak_speed_follows_the_profile(self) -> None:
        voice = Voice(enabled=False, profile="orion")
        cmd = voice._commands("/usr/bin/espeak-ng", "espeak-ng", "hi")[0]
        self.assertIn("en+m3", cmd)
        self.assertLess(int(cmd[cmd.index("-s") + 1]), 175)  # slower than default

    def test_speech_is_cleaned_and_split(self) -> None:
        self.assertEqual(clean_for_speech("**hi** 🎉 — ok"), "hi , ok")
        self.assertEqual(pace("One. Two! Three?"), ["One.", "Two!", "Three?"])


if __name__ == "__main__":
    unittest.main()
