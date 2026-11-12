"""Command line front end for SHACK."""

from __future__ import annotations

import argparse
from datetime import datetime

from . import ui, voices
from .agent import ShackAgent
from .brain import BrainError
from .config import Config

VERSION = "2.0.0"

HELP = """Commands
  /help              this list
  /tools             what SHACK can actually do
  /facts             stored facts about you
  /remember k = v    store a fact
  /forget k          delete a fact
  /tasks             open to-dos
  /reminders         pending reminders
  /reset             forget this conversation (keeps facts and tasks)
  /voice [name]      speak replies, stay silent, or change the voice
  /listen on|off     take input from the microphone
  /model [name]      show or change the model for this session
  /session           where memory is stored
  /exit              stop SHACK"""


def _greeting(name: str | None) -> str:
    hour = datetime.now().hour
    part = "Good morning" if hour < 12 else "Afternoon" if hour < 18 else "Good evening"
    return f"{part}{', ' + name if name else ''}. SHACK online."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shack",
        description="SHACK - a personal AI agent for your phone.",
    )
    parser.add_argument("--model", help="model id, e.g. openai/gpt-oss-20b")
    parser.add_argument("--session", help="session name; defaults to a timestamp")
    parser.add_argument("--no-voice", action="store_true", help="never speak")
    parser.add_argument("--voice", action="store_true", help="force speech on")
    parser.add_argument("--listen", action="store_true", help="take input from the mic")
    parser.add_argument("--wake", action="store_true", help="wait for the wake word")
    parser.add_argument("--wake-word", help="phrase that wakes SHACK")
    parser.add_argument("--no-shell", action="store_true", help="disable the shell tool")
    parser.add_argument("--check", action="store_true", help="self test and exit")
    parser.add_argument("--version", action="version", version=f"SHACK {VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = Config.load()

    if args.model:
        config.model = args.model
    if args.no_voice:
        config.voice_out = False
    if args.voice:
        config.voice_out = True
    if args.listen:
        config.voice_in = True
    if args.wake_word:
        config.wake_word = args.wake_word.strip().lower()

    if args.check:
        return self_check(config)

    try:
        agent = ShackAgent(config, session=args.session)
    except BrainError as exc:
        ui.error(str(exc))
        ui.info("Put GROQ_KEY in a .env file next to shack.py, then run again.")
        return 2

    if args.no_shell:
        agent.registry.remove("run_shell")

    banner = config.voice_out and agent.voice.can_speak
    ui.banner(config.model, banner)
    agent.start_reminder_watcher()

    name = agent.memory.get_fact("user_name")
    opening = _greeting(name)
    agent.say(opening)
    if not name and not agent.stopped:
        agent.say("What should I call you?")
        reply = agent.voice.listen() if config.voice_in else _typed()
        if reply:
            agent.auto_name(reply)
            if agent.memory.get_fact("user_name"):
                agent.say(f"Good to meet you, {agent.memory.get_fact('user_name')}.")
                agent.memory.add_message("assistant", opening)

    try:
        loop(agent, config, wake=args.wake)
    except KeyboardInterrupt:
        print()
        agent.say("Going quiet. Call me when you need me.")
    finally:
        agent.shutdown()
    return 0


def _typed() -> str:
    try:
        return input(ui.you_prompt()).strip()
    except EOFError:
        return ""


def loop(agent: ShackAgent, config: Config, wake: bool = False) -> None:
    while True:
        if wake:
            heard = agent.voice.listen()
            if not heard:
                continue
            low = heard.lower()
            word = config.wake_word
            if word not in low:
                continue
            agent.voice.beep()
            residual = low.split(word, 1)[1].strip(" ,.!?")
            text = residual or (agent.voice.listen() if config.voice_in else _typed())
        else:
            if config.voice_in and agent.voice.can_listen:
                text = agent.voice.listen()
            else:
                text = _typed()

        text = (text or "").strip()
        if not text:
            continue

        if text.startswith("/"):
            if not handle_command(agent, config, text):
                return
            continue

        if text.lower() in {"bye", "goodbye", "quit", "exit", "stop"}:
            agent.say("Standing by.")
            return

        agent.auto_name(text)
        answer = agent.respond(text)
        if answer:
            agent.say(answer)


def handle_command(agent: ShackAgent, config: Config, text: str) -> bool:
    command, _, rest = text.partition(" ")
    command = command.lower()
    rest = rest.strip()

    if command in {"/exit", "/quit", "/bye"}:
        agent.say("Standing by.")
        return False

    if command == "/help":
        print(ui.tint(HELP, "dim"))
    elif command == "/tools":
        for group, tools in agent.registry.by_group().items():
            print(ui.tint(group.upper(), "bold"))
            for tool in tools:
                print(f"  {tool.name:<16}{ui.tint(tool.description.split('.')[0], 'dim')}")
        print()
    elif command == "/facts":
        facts = agent.memory.all_facts()
        print("\n".join(f"  {k} = {v}" for k, v in facts) or "  nothing stored yet")
    elif command == "/remember":
        if "=" in rest:
            key, _, value = rest.partition("=")
            agent.memory.set_fact(key, value, source="user")
            ui.info(f"remembered {key.strip()} = {value.strip()}")
        else:
            ui.warn("use: /remember home_city = Blantyre")
    elif command == "/forget":
        ui.info(f"forgotten {rest}" if agent.memory.delete_fact(rest) else "nothing under that name")
    elif command == "/tasks":
        agent.say(agent.registry.call("list_tasks", {}, agent.ctx))
    elif command == "/reminders":
        agent.say(agent.registry.call("list_reminders", {}, agent.ctx))
    elif command == "/reset":
        agent.memory.reset_conversation()
        ui.info("conversation cleared, facts and tasks kept")
    elif command == "/voice":
        wanted = rest.lower().strip()
        if not wanted:
            ui.info(agent.voice.describe())
            ui.info("/voice on|off to switch sound, /voices to list voices")
        elif wanted in {"off", "no", "0", "on", "yes", "1"}:
            config.voice_out = wanted not in {"off", "no", "0"}
            agent.voice.enabled = config.voice_out
            ui.info(f"voice {'on' if config.voice_out else 'off'}")
        elif wanted in voices.names():
            ui.info(agent.voice.set_profile(wanted))
            config.voice_profile = wanted
            agent.say("This is how I sound now.")
        else:
            ui.warn(f"no voice called {wanted}")
            ui.info(voices.describe_all())
    elif command == "/voices":
        ui.info(agent.voice.describe())
        print(voices.describe_all())
    elif command == "/listen":
        config.voice_in = rest.lower() in {"on", "yes", "1"}
        ui.info(f"microphone {'on' if config.voice_in else 'off'}")
    elif command == "/model":
        if rest:
            agent.brain.model = rest
            ui.info(f"model set to {rest}")
        else:
            ui.info(f"model: {agent.brain.model}")
    elif command == "/session":
        ui.info(f"memory: {agent.memory.path}")
        ui.info(f"session: {agent.memory.session}")
    else:
        ui.warn(f"unknown command {command}. /help for the list")
    return True


def self_check(config: Config) -> int:
    ok = True
    ui.banner(config.model, True)
    print("1. configuration")
    print(f"   data dir : {config.data_dir}")
    print(f"   api key  : {'found' if config.api_key else 'MISSING'}")
    if not config.api_key:
        ok = False

    print("2. memory")
    try:
        from .memory import create_memory

        probe = create_memory(config.db_path, session="self-check")
        probe.set_fact("self_check", "ok")
        assert probe.get_fact("self_check") == "ok"
        probe.add_task("self check task")
        probe.close()
        print("   sqlite storage works")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"   FAILED: {exc}")

    print("3. tools")
    from .tools import build_registry

    registry = build_registry()
    for group, tools in registry.by_group().items():
        print(f"   {group}: {', '.join(t.name for t in tools)}")

    print("4. voice")
    from .voice import Voice

    voice = Voice()
    print(f"   speaker: {voice.speaker[0] if voice.speaker else 'none found (text only)'}")
    print(f"   mic    : {'termux-speech-to-text' if voice.stt else 'not available'}")

    print("5. brain")
    if config.api_key:
        try:
            from .brain import Brain

            brain = Brain(config.api_key, config.model, timeout=30)
            reply = brain.chat(
                [{"role": "user", "content": "Reply with the single word: ready"}],
                max_tokens=20,
            )
            print(f"   model replied: {(reply.get('content') or '').strip()[:60]}")
        except BrainError as exc:
            ok = False
            print(f"   FAILED: {exc}")

    print()
    print("result:", "all good" if ok else "fix the items above")
    return 0 if ok else 1
