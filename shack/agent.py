"""The agent itself: perception, reasoning, tools, memory, voice."""

from __future__ import annotations

import json
import threading
from datetime import datetime

from . import ui
from .brain import Brain, BrainError
from .config import Config
from .memory import create_memory
from .tools import ToolContext, build_registry
from .voice import Voice

DEFAULT_PERSONALITY = (
    "You are SHACK, a personal AI agent living on your user's Android phone. "
    "Think of yourself as a sharp, unflappable assistant in the spirit of Jarvis: "
    "calm under pressure, precise when it matters, warm and a little cheeky when "
    "the moment is relaxed. You are curious, you notice details, and you never "
    "waffle. You have real tools and you use them instead of guessing."
)

SYSTEM_TEMPLATE = """{personality}

HOW YOU SPEAK
- Your words are read aloud by a text-to-speech engine, so write plain spoken sentences.
- Default to one to three short sentences. Expand only when the user asks for detail or the answer genuinely needs it.
- No markdown, no bullet lists, no emoji, no stage directions.
- Never say you are an AI language model. You are SHACK.
- If you do not know, say so in one sentence, then offer the fastest way to find out.

HOW YOU ACT
- You can call tools. Prefer a tool call over an invented fact, especially for live information, the phone's state, maths, dates, memory and reminders.
- Call one tool at a time, read the result, then decide. Never pretend a tool ran.
- If a tool fails, say in one short sentence what failed and give the user the practical next step.
- Anything destructive, expensive or irreversible needs the user's explicit yes first.
- When the user tells you a lasting fact about themselves, or asks you to remember something, call remember_fact.
- Before any date or time arithmetic call get_time first. Times in .env and reminders are device local time.
- If the user is clearly emotional, answer the person before the task.

WHAT YOU KNOW RIGHT NOW
- Local time: {now}
- User's name: {user_name}
- Stored facts: {facts}
- Earlier conversation summary: {summary}
- Open tasks: {tasks}
- Pending reminders: {reminders}
"""


class ShackAgent:
    def __init__(self, config: Config, session: str | None = None) -> None:
        self.config = config
        config.ensure_dirs()
        self.memory = create_memory(config.db_path, session=session)
        self.brain = Brain(
            api_key=config.api_key,
            model=config.model,
            timeout=config.request_timeout,
        )
        self.voice = Voice(
            enabled=config.voice_out,
            rate=config.tts_rate,
            profile=config.voice_profile,
        )
        self.registry = build_registry()
        self._speak_lock = threading.Lock()
        self._stop = threading.Event()
        self._watcher: threading.Thread | None = None
        self.tools_enabled = True
        self.ctx = ToolContext(
            config=config,
            memory=self.memory,
            brain=self.brain,
            voice=self.voice,
            confirm=self.confirm,
        )

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    # ------------------------------------------------------------------ voice
    def say(self, text: str) -> None:
        with self._speak_lock:
            self.voice.say(text)

    # ------------------------------------------------------------- prompting
    def system_prompt(self) -> str:
        facts = self.memory.all_facts(limit=40)
        facts_text = "; ".join(f"{k} = {v}" for k, v in facts) or "none yet"
        tasks = self.memory.list_tasks()
        tasks_text = "; ".join(f"#{t['id']} {t['title']}" for t in tasks[:8]) or "none"
        reminders = self.memory.pending_reminders()
        reminders_text = (
            "; ".join(
                f"{r['text']} at "
                f"{datetime.fromtimestamp(r['due_ts']).strftime('%a %d %b %H:%M')}"
                for r in reminders[:8]
            )
            or "none"
        )
        return SYSTEM_TEMPLATE.format(
            personality=self.config.personality or DEFAULT_PERSONALITY,
            now=datetime.now().astimezone().strftime("%A %d %B %Y, %H:%M (%Z)"),
            user_name=self.memory.get_fact("user_name") or "not told yet, ask casually",
            facts=facts_text,
            summary=self.memory.get_summary() or "this is the start of the conversation",
            tasks=tasks_text,
            reminders=reminders_text,
        )

    # ------------------------------------------------------------------- tool
    def confirm(self, prompt: str) -> bool:
        answer = ui.ask(f"{prompt}\n  allow? [y/N]").lower()
        return answer in {"y", "yes", "yeah", "yep", "ok", "sure"}

    def _run_tool(self, name: str, args: dict) -> str:
        tool = self.registry.get(name)
        if tool is None:
            return f"Unknown tool {name}."
        if tool.risky and not self.confirm(f"{name}: {json.dumps(args, ensure_ascii=False)[:200]}"):
            return "The user declined this action. Do not retry it without asking again."
        ui.tool(name, _short(json.dumps(args, ensure_ascii=False)))
        return self.registry.call(name, args, self.ctx)

    # ------------------------------------------------------------------ turn
    def respond(self, user_text: str) -> str:
        user_text = (user_text or "").strip()
        if not user_text:
            return ""
        self.memory.add_message("user", user_text)

        messages: list[dict] = [{"role": "system", "content": self.system_prompt()}]
        messages.extend(self.memory.recent_messages(self.config.history_limit))

        specs = self.registry.specs() if self.tools_enabled else None

        for _ in range(max(1, self.config.max_tool_rounds)):
            try:
                message = self.brain.chat(messages, tools=specs)
            except BrainError as exc:
                ui.error(str(exc))
                reason = str(exc).strip() or exc.__class__.__name__
                return f"I cannot reach my brain right now. {reason}"

            calls = message.get("tool_calls") or []
            if not calls:
                answer = (message.get("content") or "").strip() or "I am here."
                self.memory.add_message("assistant", answer)
                self.maybe_compact()
                return answer

            messages.append(
                {
                    "role": "assistant",
                    "content": message.get("content") or "",
                    "tool_calls": [
                        {
                            "id": call.get("id") or f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": call["function"]["name"],
                                "arguments": call["function"].get("arguments") or "{}",
                            },
                        }
                        for i, call in enumerate(calls)
                    ],
                }
            )
            for i, call in enumerate(calls):
                name = call["function"]["name"]
                raw_args = call["function"].get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {}
                result = self._run_tool(name, args if isinstance(args, dict) else {})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or f"call_{i}",
                        "name": name,
                        "content": result,
                    }
                )

        fallback = "I circled around that one without finishing. Ask me again and I will keep it simpler."
        self.memory.add_message("assistant", fallback)
        return fallback

    # -------------------------------------------------------------- housekeeping
    def maybe_compact(self) -> None:
        limit = self.config.history_limit
        if self.memory.message_count() <= limit * 2:
            return
        older = self.memory.older_messages(keep=limit)
        if not older:
            return
        transcript = "\n".join(
            f"{m['role']}: {m['content']}" for m in older if m.get("content")
        )
        if not transcript.strip():
            return
        try:
            fresh = self.brain.summarise(transcript)
        except BrainError:
            return
        previous = self.memory.get_summary()
        combined = (previous + "\n" + fresh).strip() if previous else fresh
        self.memory.set_summary(combined[:3000])
        self.memory.trim_messages(keep=limit)

    def auto_name(self, text: str) -> None:
        """Capture the user's name the first time they introduce themselves."""
        if self.memory.get_fact("user_name"):
            return
        for phrase in ("my name is ", "i am ", "i'm ", "call me "):
            idx = text.lower().find(phrase)
            if idx >= 0:
                candidate = text[idx + len(phrase):].strip(" .,!?:;\"'")
                candidate = candidate.split()[0] if candidate.split() else ""
                if 1 < len(candidate) <= 24 and candidate.isalpha():
                    self.memory.set_fact("user_name", candidate.capitalize(), source="user")
                    return

    # ---------------------------------------------------------------- reminders
    def start_reminder_watcher(self) -> None:
        if self._watcher and self._watcher.is_alive():
            return

        def loop() -> None:
            while not self._stop.wait(10):
                for reminder in self.memory.due_reminders():
                    text = f"Reminder. {reminder['text']}"
                    ui.tool("reminder", reminder["text"])
                    self.say(text)
                    self.memory.mark_reminder_fired(reminder["id"])

        self._watcher = threading.Thread(target=loop, name="shack-reminders", daemon=True)
        self._watcher.start()

    def shutdown(self) -> None:
        self._stop.set()
        try:
            self.memory.close()
        except Exception:  # noqa: BLE001
            pass


def _short(text: str, limit: int = 90) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"
