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

from kivy.animation import Animation
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image as KivyImage
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform

Window.softinput_mode = "below_target"

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Violet night palette, after the Aura reference design.
BG = (0.035, 0.027, 0.07, 1)
PANEL = (0.09, 0.075, 0.15, 1)
PANEL_EDGE = (0.30, 0.24, 0.42, 0.55)
LILAC = (0.88, 0.67, 1.0, 1)
PINK = (0.93, 0.55, 0.95, 1)
TEXT = (0.95, 0.93, 1.0, 1)
DIM = (0.70, 0.62, 0.86, 1)
USER_BUBBLE = (0.20, 0.16, 0.33, 1)
SHACK_BUBBLE = (0.28, 0.17, 0.40, 1)
CYAN = LILAC  # kept for the bits of code that still say CYAN


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


def clean_key(key: str) -> str:
    """Keys arrive with stray spaces or a newline from a phone clipboard."""
    return "".join(key.split())


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


class Picture(KivyImage):
    """Image that keeps its proportions and scales smoothly."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("allow_stretch", True)
        kwargs.setdefault("keep_ratio", True)
        super().__init__(**kwargs)


def _round_fill(widget, colour, radius, edge=None):
    """Paint a rounded panel behind a widget and keep it in step as it resizes."""
    with widget.canvas.before:
        Color(*colour)
        shape = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])
        outline = None
        if edge:
            Color(*edge)
            outline = Line(rounded_rectangle=(*widget.pos, *widget.size, radius), width=1)

    def follow(*_):
        shape.pos = widget.pos
        shape.size = widget.size
        if outline is not None:
            outline.rounded_rectangle = (*widget.pos, *widget.size, radius)

    widget.bind(pos=follow, size=follow)
    return shape


class Bubble(BoxLayout):
    """One chat message: a rounded bubble, you on the right, SHACK on the left."""

    def __init__(self, text: str, speaker: str = "shack", **kwargs) -> None:
        super().__init__(
            orientation="horizontal",
            size_hint_y=None,
            padding=(dp(4), dp(3)),
            spacing=dp(6),
            **kwargs,
        )
        mine = speaker == "you"
        note = speaker == "note"
        colour = USER_BUBBLE if mine else (PANEL if note else SHACK_BUBBLE)
        ink = TEXT if not note else DIM

        self.label = Label(
            text=text,
            color=ink,
            size_hint=(None, None),
            halign="left",
            valign="middle",
            padding=(dp(14), dp(10)),
            font_size=dp(15),
        )
        max_w = lambda: max(dp(120), Window.width * 0.70)  # noqa: E731

        def fit(*_):
            # measure the text unconstrained first so short messages get short bubbles
            self.label.text_size = (None, None)
            self.label.texture_update()
            natural_w = self.label.texture_size[0]
            inner = max_w() - dp(28)
            if natural_w > inner:
                self.label.text_size = (inner, None)
                self.label.texture_update()
            tw, th = self.label.texture_size
            self.label.size = (min(max_w(), tw + dp(28)), th + dp(20))
            self.height = self.label.height + dp(6)

        self.label.bind(text=fit)
        Window.bind(width=fit)
        fit()
        _round_fill(self.label, colour, dp(18), edge=PANEL_EDGE if not mine else None)

        spark = Picture(
            source=os.path.join(ASSETS, "sparkle.png"),
            size_hint=(None, None),
            size=(dp(26), dp(26)),
        )
        gap = Widget()
        if mine:
            self.add_widget(gap)
            self.add_widget(self.label)
        elif note:
            self.add_widget(Widget(size_hint_x=None, width=dp(32)))
            self.add_widget(self.label)
            self.add_widget(gap)
        else:
            column = BoxLayout(orientation="vertical", size_hint=(None, 1), width=dp(30))
            column.add_widget(Widget())
            column.add_widget(spark)
            self.add_widget(column)
            self.add_widget(self.label)
            self.add_widget(gap)


class IconButton(Button):
    """A flat glyph button with no grey slab behind it."""

    def __init__(self, glyph: str = "", image: str = "", **kwargs) -> None:
        super().__init__(
            text=glyph,
            background_normal="",
            background_down="",
            background_color=(0, 0, 0, 0),
            color=LILAC,
            font_size=dp(20),
            **kwargs,
        )
        if image:
            pic = Picture(source=os.path.join(ASSETS, image))
            self.bind(
                pos=lambda *_: setattr(pic, "pos", (self.x + dp(6), self.y + dp(6))),
                size=lambda *_: setattr(pic, "size", (self.width - dp(12), self.height - dp(12))),
            )
            self.add_widget(pic)


class ShackScreen(BoxLayout):
    status = StringProperty("starting")

    def __init__(self, **kwargs) -> None:
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(8), **kwargs)
        self.agent = None
        self.busy = False

        # ---- header: sparkle, SHACK, and three round-ish controls
        head = BoxLayout(size_hint_y=None, height=dp(54), padding=(dp(12), dp(6)), spacing=dp(8))
        _round_fill(head, PANEL, dp(20), edge=PANEL_EDGE)
        logo = Picture(
            source=os.path.join(ASSETS, "sparkle.png"), size_hint=(None, 1), width=dp(34)
        )
        self._avatar = logo
        title = Label(
            text="SHACK",
            color=PINK,
            bold=True,
            font_size=dp(24),
            halign="left",
            valign="middle",
            size_hint_x=1,
        )
        title.bind(size=lambda *_: setattr(title, "text_size", (title.width, title.height)))
        self._voice_btn = IconButton(glyph="Voice", size_hint=(None, 1), width=dp(64))
        self._voice_btn.font_size = dp(13)
        self._voice_btn.bind(on_release=lambda *_: self.sample_voice())
        mic_top = IconButton(glyph="Mic", size_hint=(None, 1), width=dp(48))
        mic_top.font_size = dp(13)
        mic_top.bind(on_release=lambda *_: self.listen())
        head.add_widget(logo)
        head.add_widget(title)
        head.add_widget(self._voice_btn)
        head.add_widget(mic_top)
        self.add_widget(head)

        # ---- stage: the orb, with "SHACK Ready" under it
        stage = BoxLayout(orientation="vertical", size_hint_y=0.46, spacing=dp(4))
        orb_box = FloatLayout()
        self._hero_pic = Picture(
            source=os.path.join(ASSETS, "hero_round.png"),
            size_hint=(None, None),
            size=(dp(190), dp(190)),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        orb_box.add_widget(self._hero_pic)
        stage.add_widget(orb_box)
        self.status_label = Label(
            text="SHACK Ready",
            color=LILAC,
            size_hint_y=None,
            height=dp(22),
            font_size=dp(15),
        )
        self.sub_label = Label(
            text="How can I help you today?",
            color=LILAC,
            size_hint_y=None,
            height=dp(24),
            font_size=dp(15),
        )
        stage.add_widget(self.status_label)
        stage.add_widget(self.sub_label)
        self.add_widget(stage)
        self._hero = stage

        # ---- conversation panel
        panel = BoxLayout(orientation="vertical", padding=(dp(6), dp(6)))
        _round_fill(panel, PANEL, dp(22), edge=PANEL_EDGE)
        self.log = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        self.log.bind(minimum_height=self.log.setter("height"))
        scroll = ScrollView(bar_width=dp(3), bar_color=PANEL_EDGE)
        scroll.add_widget(self.log)
        panel.add_widget(scroll)
        self.scroll = scroll
        self.add_widget(panel)

        # ---- input pill
        bar = BoxLayout(size_hint_y=None, height=dp(52), padding=(dp(14), dp(4)), spacing=dp(6))
        _round_fill(bar, PANEL, dp(26), edge=PANEL_EDGE)
        self.entry = TextInput(
            hint_text="Ask anything...",
            multiline=False,
            write_tab=False,
            background_normal="",
            background_active="",
            background_color=(0, 0, 0, 0),
            foreground_color=TEXT,
            hint_text_color=(0.62, 0.52, 0.80, 1),
            cursor_color=PINK,
            padding=(dp(2), dp(13)),
            font_size=dp(16),
        )
        self.entry.bind(on_text_validate=lambda *_: self.send())
        send = IconButton(image="sparkle.png", size_hint=(None, 1), width=dp(44))
        send.bind(on_release=lambda *_: self.send())
        bar.add_widget(self.entry)
        bar.add_widget(send)
        self.add_widget(bar)

    # ------------------------------------------------------------------ setup
    def on_kv_post(self, *_args) -> None:
        Clock.schedule_once(lambda *_: self.boot(), 0.2)

    def show_face(self) -> None:
        """Start the orb breathing; it stays on screen like in the reference."""
        self._breathe_hero()

    # ------------------------------------------------------------- her face
    def _face_pieces(self):
        """The orb, and the small sparkle in the header."""
        return [w for w in (getattr(self, "_avatar", None), getattr(self, "_hero_pic", None)) if w is not None]

    def _stop_face(self) -> None:
        for widget in self._face_pieces():
            Animation.cancel_all(widget)
        orb = self._hero_pic
        orb.size = (dp(190), dp(190))
        orb.opacity = 1.0
        self._avatar.opacity = 1.0

    def start_talking(self) -> None:
        """The orb swells and flickers in time with her words."""
        self._stop_face()
        self.set_status("speaking")
        orb = self._hero_pic
        big, small = dp(214), dp(196)
        beat = Animation(size=(big, big), opacity=1.0, duration=0.16, t="out_quad")
        beat += Animation(size=(small, small), opacity=0.82, duration=0.2, t="in_out_quad")
        beat += Animation(size=(dp(206), dp(206)), opacity=1.0, duration=0.13, t="out_quad")
        beat += Animation(size=(dp(192), dp(192)), opacity=0.78, duration=0.22, t="in_out_quad")
        beat.repeat = True
        beat.start(orb)
        glint = Animation(opacity=0.4, duration=0.17) + Animation(opacity=1.0, duration=0.17)
        glint.repeat = True
        glint.start(self._avatar)

    def start_listening_face(self) -> None:
        """A slow, wide swell: she is listening, not talking."""
        self._stop_face()
        self.set_status("listening")
        sway = Animation(size=(dp(206), dp(206)), duration=0.7, t="in_out_sine")
        sway += Animation(size=(dp(186), dp(186)), duration=0.7, t="in_out_sine")
        sway.repeat = True
        sway.start(self._hero_pic)

    def stop_face_motion(self) -> None:
        self._stop_face()
        self._breathe_hero()
        if self.awaiting_key_state():
            self.set_status("needs key")
        elif self.busy:
            self.set_status("thinking")
        else:
            self.set_status("Ready")

    def awaiting_key_state(self) -> bool:
        return bool(getattr(self, "awaiting_key", False))

    def _breathe_hero(self) -> None:
        orb = self._hero_pic
        Animation.cancel_all(orb)
        breathe = Animation(opacity=0.78, duration=2.0, t="in_out_sine") + Animation(
            opacity=1.0, duration=2.0, t="in_out_sine"
        )
        breathe.repeat = True
        breathe.start(orb)

    def say_with_face(self, text: str) -> None:
        """Speak, with her face moving for as long as the words take."""
        if self.agent is None:
            return
        words = len(str(text).split())
        rate = getattr(self.agent.voice.profile, "rate", 1.0) or 1.0
        seconds = max(1.0, min(45.0, (words / 2.6) / rate))

        def speak(*_):
            self.start_talking()
            try:
                self.agent.voice.say(text)
            finally:
                Clock.schedule_once(lambda *_: self.stop_face_motion(), seconds)

        Clock.schedule_once(speak, 0)

    def hide_face(self) -> None:
        """The orb stays put now, so there is nothing to hide."""

    def note(self, text: str, speaker: str = "note") -> None:
        self.log.add_widget(Bubble(text, speaker))
        Clock.schedule_once(lambda *_: setattr(self.scroll, "scroll_y", 0), 0.05)

    def set_status(self, text: str) -> None:
        self.status = text
        pretty = {
            "Ready": ("SHACK Ready", "How can I help you today?"),
            "thinking": ("Thinking...", "One moment."),
            "listening": ("Listening...", "Go ahead, I am here."),
            "speaking": ("Speaking...", ""),
            "needs key": ("Needs a key", "Paste your Groq key below."),
            "starting": ("Waking up...", ""),
        }
        top, bottom = pretty.get(text, ("SHACK Ready", "How can I help you today?"))
        self.status_label.text = top
        self.sub_label.text = bottom

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

        from shack import ui as shack_ui

        shack_ui.set_error_sink(lambda msg: self.note(msg, "note"))

        agent = self.agent
        agent.say = self.say_with_face
        agent.start_reminder_watcher()

        self.set_status("Ready")
        self._voice_btn.text = "Voice"
        name = agent.memory.get_fact("user_name")
        hour = time.localtime().tm_hour
        part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        greeting = f"Good {part}{', ' + name if name else ''}. SHACK online."
        agent.say(greeting)
        self.note(greeting, "shack")
        self.show_face()
        if not name:
            self.note("Tell me your name when you're ready, or just start asking.")

    def prompt_for_key(self) -> None:
        self.note("I need a Groq API key to think. Paste it below and press the sparkle.")
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
            key = clean_key(text)
            if not key.startswith("gsk_"):
                self.note(
                    "That does not look like a Groq key. They start with gsk_. "
                    "Copy the whole key from console.groq.com/keys and paste it here.",
                    "note",
                )
                return
            save_key(key)
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
        self.set_status("Ready")
        self.note(answer, "shack")
        self.agent.say(answer)

    def sample_voice(self) -> None:
        """Hear her voice without changing it. Rumi stays until /voice says otherwise."""
        if self.agent is None:
            self.note("Not ready yet.")
            return
        profile = self.agent.voice.profile
        self.note(f"{profile.label}: {profile.blurb}. Say /voice for other voices.", "note")
        self.say_with_face("Hi, it is me. This is how I sound.")

    def check_brain(self) -> None:
        """Ask Groq what is wrong, in words, instead of guessing."""
        if self.agent is None:
            self.note("Not ready yet.")
            return
        self.note("Checking the key and the connection...", "note")

        def work() -> None:
            from shack.brain import BASE_URL, _error_detail

            brain = self.agent.brain
            try:
                resp = brain._session.get(
                    f"{BASE_URL}/models", headers=brain._headers, timeout=20
                )
            except Exception as exc:  # noqa: BLE001 - report anything
                msg = f"No connection to Groq: {exc.__class__.__name__}. Check mobile data or wifi."
            else:
                if resp.status_code == 200:
                    try:
                        ids = [m.get("id", "") for m in resp.json().get("data", [])]
                    except ValueError:
                        ids = []
                    has_model = brain.model in ids
                    msg = (
                        f"Key works. {len(ids)} models available. "
                        + (
                            f"{brain.model} is ready."
                            if has_model
                            else f"{brain.model} is NOT on this account. Try /model llama-3.3-70b-versatile"
                        )
                    )
                elif resp.status_code in (401, 403):
                    msg = (
                        "Groq rejected the key. It is wrong, expired, or from another "
                        f"service. ({_error_detail(resp)})"
                    )
                else:
                    msg = f"Groq answered {resp.status_code}: {_error_detail(resp)}"
            Clock.schedule_once(lambda *_: self.note(msg, "note"), 0)

        threading.Thread(target=work, daemon=True).start()

    def check_sound(self) -> None:
        """Say, in plain words, why the phone is quiet."""
        if self.agent is None:
            self.note("Not ready yet.")
            return
        android = getattr(self.agent.voice, "_android", None)
        lines = [f"Voice: {self.agent.voice.profile.label}."]
        if android is None:
            lines.append("No Android speech engine is loaded, so she cannot talk out loud.")
        else:
            lines.append(android.diagnose().capitalize() + ".")
            if getattr(android, "last_error", ""):
                lines.append(android.last_error.capitalize() + ".")
        lines.append("If it is quiet: turn the media volume up, check the phone is not on silent, and in Android Settings, System, Languages, Text-to-speech, make sure a Google speech engine is installed.")
        for line in lines:
            self.note(line, "note")
        self.say_with_face("Testing one, two, three. Can you hear me now?")

    def listen(self) -> None:
        if self.agent is None:
            self.note("Not ready yet.")
            return
        self.start_listening_face()
        self.note("Listening… say what you need.", "note")

        def work() -> None:
            heard = self.agent.voice._listen_android()  # noqa: SLF001
            def apply(*_):
                self.stop_face_motion()
                if heard:
                    self.ask(heard)
                else:
                    reason = getattr(self.agent.voice, "listen_error", "") or "I didn't catch that."
                    self.note(f"{reason}.", "note")
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
        elif cmd == "/test":
            self.check_brain()
        elif cmd == "/sound":
            self.check_sound()
        else:
            self.note(
                "Commands: /test /sound /key /facts /tasks /reminders /voice /voices /reset /exit"
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
