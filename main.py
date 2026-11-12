"""SHACK for Android - the Kivy front end that buildozer packages into an APK.

The same agent that runs in Termux runs here: same tools, same memory, same
personality. Voice out goes through Android's own text to speech, voice in
through Android's recogniser, and everything else falls back gracefully.
"""

from __future__ import annotations

import os
import threading
import time

os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform

Window.softinput_mode = "below_target"

CYAN = (0.35, 0.85, 0.95, 1)
DIM = (0.62, 0.66, 0.72, 1)
BG = (0.06, 0.07, 0.09, 1)


def data_dir() -> str:
    """Somewhere writable on both Android and the desktop."""
    if platform == "android":
        from android.storage import app_storage_path  # type: ignore

        base = app_storage_path()
    else:
        base = os.path.expanduser("~")
    path = os.path.join(base, "shack")
    os.makedirs(path, exist_ok=True)
    return path


def saved_key() -> str:
    env = os.environ.get("GROQ_KEY")
    if env:
        return env
    for folder in (data_dir(), os.getcwd()):
        try:
            with open(os.path.join(folder, ".env"), encoding="utf-8") as handle:
                for line in handle:
                    if line.strip().startswith("GROQ_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return ""


def save_key(key: str) -> None:
    path = os.path.join(data_dir(), ".env")
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            lines = [
                line for line in handle.readlines()
                if not line.strip().startswith("GROQ_KEY=")
            ]
    lines.append(f"GROQ_KEY={key}\n")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.writelines(lines)
    os.environ["GROQ_KEY"] = key


class Bubble(Label):
    def __init__(self, text: str, speaker: str = "shack", **kwargs) -> None:
        colour = {"you": (0.75, 0.95, 0.8, 1), "shack": CYAN, "note": DIM}.get(
            speaker, DIM
        )
        tag = {"you": "you", "shack": "SHACK", "note": ""}.get(speaker, speaker)
        prefix = f"[b]{tag}[/b]  " if tag else ""
        super().__init__(
            text=f"{prefix}{text}",
            markup=True,
            color=colour,
            size_hint_y=None,
            halign="left",
            valign="top",
            padding=(dp(10), dp(6)),
            **kwargs,
        )
        self.bind(width=lambda *_: setattr(self, "text_size", (self.width, None)))
        self.bind(texture_size=lambda *_: setattr(self, "height", self.texture_size[1]))


class ShackScreen(BoxLayout):
    status = StringProperty("starting")

    def __init__(self, **kwargs) -> None:
        super().__init__(orientation="vertical", padding=dp(6), spacing=dp(6), **kwargs)
        self.agent = None
        self.busy = False

        head = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(6))
        title = Label(
            text="[b]SHACK[/b]", markup=True, color=CYAN, halign="left", valign="middle"
        )
        title.bind(size=lambda *_: setattr(title, "text_size", (title.width, None)))
        self.status_label = Label(text=self.status, color=DIM, halign="right", valign="middle")
        self.status_label.bind(size=lambda *_: setattr(self.status_label, "text_size", (self.status_label.width, None)))
        voice_btn = Button(text="Voice", size_hint_x=None, width=dp(64))
        voice_btn.bind(on_release=lambda *_: self.cycle_voice())
        head.add_widget(title)
        head.add_widget(self.status_label)
        head.add_widget(voice_btn)
        self.add_widget(head)

        self.log = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        self.log.bind(minimum_height=self.log.setter("height"))
        scroll = ScrollView(bar_width=dp(3))
        scroll.add_widget(self.log)
        self.add_widget(scroll)
        self.scroll = scroll

        bar = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        self.entry = TextInput(
            hint_text="Ask SHACK anything",
            multiline=False,
            write_tab=False,
            background_color=(0.13, 0.15, 0.18, 1),
            foreground_color=(0.95, 0.97, 1, 1),
            cursor_color=CYAN,
            padding=(dp(10), dp(10)),
        )
        self.entry.bind(on_text_validate=lambda *_: self.send())
        send = Button(text="Send", size_hint_x=None, width=dp(64))
        send.bind(on_release=lambda *_: self.send())
        mic = Button(text="Mic", size_hint_x=None, width=dp(56))
        mic.bind(on_release=lambda *_: self.listen())
        bar.add_widget(self.entry)
        bar.add_widget(send)
        bar.add_widget(mic)
        self.add_widget(bar)

    # ------------------------------------------------------------------ setup
    def on_kv_post(self, *_args) -> None:
        Clock.schedule_once(lambda *_: self.boot(), 0.2)

    def note(self, text: str, speaker: str = "note") -> None:
        self.log.add_widget(Bubble(text, speaker))
        Clock.schedule_once(lambda *_: setattr(self.scroll, "scroll_y", 0), 0.05)

    def set_status(self, text: str) -> None:
        self.status = text
        self.status_label.text = text

    def boot(self) -> None:
        os.environ.setdefault("SHACK_DATA_DIR", data_dir())
        from shack.agent import ShackAgent
        from shack.brain import BrainError
        from shack.config import Config

        key = saved_key()
        if not key:
            self.prompt_for_key()
            return
        os.environ["GROQ_KEY"] = key
        config = Config.load()
        config.data_dir = __import__("pathlib").Path(data_dir())
        config.voice_out = True
        try:
            self.agent = ShackAgent(config)
        except BrainError as exc:
            self.note(str(exc))
            self.prompt_for_key()
            return

        agent = self.agent
        # speak on the UI thread, whatever thread asked for it
        agent.say = lambda text: Clock.schedule_once(lambda *_: agent.voice.say(text), 0)
        agent.start_reminder_watcher()

        self.set_status(agent.brain.model.split("/")[-1])
        name = agent.memory.get_fact("user_name")
        hour = time.localtime().tm_hour
        part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        greeting = f"Good {part}{', ' + name if name else ''}. SHACK online."
        agent.say(greeting)
        self.note(greeting, "shack")
        if not name:
            self.note("Tell me your name when you're ready, or just start asking.")

    def prompt_for_key(self) -> None:
        self.note("I need a Groq API key to think. Paste it below and press Send.")
        self.note("Free key: https://console.groq.com/keys")
        self.set_status("needs key")
        self.awaiting_key = True

    # ------------------------------------------------------------------ chat
    def send(self) -> None:
        text = self.entry.text.strip()
        self.entry.text = ""
        if not text:
            return
        if getattr(self, "awaiting_key", False):
            save_key(text)
            self.awaiting_key = False
            self.note("Key saved.", "note")
            self.boot()
            return
        if self.agent is None:
            self.note("Not ready yet, one moment.")
            return
        if text.startswith("/"):
            self.command(text)
            return
        self.ask(text)

    def ask(self, text: str) -> None:
        if self.busy:
            self.note("Still working on the last one.")
            return
        self.busy = True
        self.set_status("thinking")
        self.note(text, "you")

        def work() -> None:
            try:
                answer = self.agent.respond(text)
            except Exception as exc:  # noqa: BLE001 - never kill the UI
                answer = f"Something broke: {exc.__class__.__name__}"
            Clock.schedule_once(lambda *_: self.finish(answer), 0)

        threading.Thread(target=work, daemon=True).start()

    def finish(self, answer: str) -> None:
        self.busy = False
        self.set_status(self.agent.brain.model.split("/")[-1])
        self.note(answer, "shack")
        self.agent.say(answer)

    def cycle_voice(self) -> None:
        if self.agent is None:
            self.note("Not ready yet.")
            return
        from shack import voices

        order = voices.names()
        current = self.agent.voice.profile.key
        nxt = order[(order.index(current) + 1) % len(order)] if current in order else order[0]
        message = self.agent.voice.set_profile(nxt)
        self.note(message, "note")
        self.agent.say(f"This is {self.agent.voice.profile.label}. How does this sound?")

    def listen(self) -> None:
        if self.agent is None:
            self.note("Not ready yet.")
            return
        self.set_status("listening")
        self.note("Listening… say what you need.")

        def work() -> None:
            heard = self.agent.voice._listen_android()  # noqa: SLF001
            def apply(*_):
                self.set_status(self.agent.brain.model.split("/")[-1])
                if heard:
                    self.ask(heard)
                else:
                    self.note("I didn't catch that. Try again or type it.")
            Clock.schedule_once(apply, 0)

        threading.Thread(target=work, daemon=True).start()

    def command(self, text: str) -> None:
        cmd = text.split()[0].lower()
        agent = self.agent
        if cmd in {"/exit", "/quit"}:
            App.get_running_app().stop()
        elif cmd == "/facts":
            facts = agent.memory.all_facts()
            self.note("\n".join(f"{k} = {v}" for k, v in facts) or "Nothing stored yet.")
        elif cmd == "/tasks":
            tasks = agent.memory.list_tasks()
            self.note("\n".join(f"#{t['id']} {t['title']}" for t in tasks) or "No open tasks.")
        elif cmd == "/reminders":
            rows = agent.memory.pending_reminders()
            self.note(
                "\n".join(
                    f"{time.strftime('%a %H:%M', time.localtime(r['due_ts']))} {r['text']}"
                    for r in rows
                )
                or "No reminders."
            )
        elif cmd == "/reset":
            agent.memory.reset_conversation()
            self.note("Conversation cleared. Facts and tasks kept.")
        elif cmd == "/voice":
            parts = text.split()
            if len(parts) > 1:
                self.note(agent.voice.set_profile(parts[1]), "note")
            else:
                self.note(agent.voice.describe(), "note")
        elif cmd == "/voices":
            from shack import voices

            self.note(voices.describe_all(), "note")
        elif cmd == "/key":
            self.prompt_for_key()
        else:
            self.note(
                "Commands: /facts /tasks /reminders /voice /voices /reset /key /exit"
            )


class ShackApp(App):
    title = "SHACK"

    def build(self):
        Window.clearcolor = BG
        return ShackScreen()

    def on_pause(self) -> bool:
        return True

    def on_resume(self) -> None:
        pass


if __name__ == "__main__":
    ShackApp().run()
