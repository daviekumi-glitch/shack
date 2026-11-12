"""SHACK configuration.

Every setting can be supplied as an environment variable, or in a .env file
placed either next to the project or in the data directory (~/.shack/.env).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MODEL = "openai/gpt-oss-20b"
DEFAULT_DATA_DIR = Path.home() / ".shack"

_TRUE = {"1", "true", "yes", "on", "y"}
_FALSE = {"0", "false", "no", "off", "n"}


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    text = value.strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    return default


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def load_dotenv(path: Path) -> None:
    """Read a simple KEY=VALUE .env file without needing extra packages."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _builtin_key() -> str:
    """A key compiled into the APK, so the app works the moment it is installed."""
    try:
        from . import builtin_key

        return (builtin_key.get() or "").strip()
    except Exception:  # noqa: BLE001 - older build without the module
        return ""


@dataclass
class Config:
    api_key: str = ""
    model: str = DEFAULT_MODEL
    data_dir: Path = DEFAULT_DATA_DIR
    history_limit: int = 24
    voice_out: bool = True
    voice_in: bool = False
    tts_rate: int = 0
    voice_profile: str = "rumi"
    wake_word: str = "hey shack"
    safe_mode: bool = True
    max_tool_rounds: int = 6
    request_timeout: int = 60
    personality: str = ""
    extra: dict = field(default_factory=dict)

    # --- paths -----------------------------------------------------------
    @property
    def db_path(self) -> Path:
        return self.data_dir / "shack.db"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "shack.log"

    # --- loading ---------------------------------------------------------
    @classmethod
    def load(cls, project_root: Path | None = None) -> "Config":
        root = project_root or Path(__file__).resolve().parent.parent
        load_dotenv(root / ".env")
        load_dotenv(DEFAULT_DATA_DIR / ".env")

        data_dir = Path(
            os.environ.get("SHACK_DATA_DIR") or DEFAULT_DATA_DIR
        ).expanduser()
        api_key = (
            os.environ.get("SHACK_API_KEY")
            or os.environ.get("GROQ_KEY")
            or os.environ.get("GROQ_API_KEY")
            or _builtin_key()
            or ""
        ).strip()

        cfg = cls(
            api_key=api_key,
            model=(os.environ.get("SHACK_MODEL") or DEFAULT_MODEL).strip(),
            data_dir=data_dir,
            history_limit=_as_int(os.environ.get("SHACK_HISTORY"), 24),
            voice_out=_as_bool(os.environ.get("SHACK_VOICE_OUT"), True),
            voice_in=_as_bool(os.environ.get("SHACK_VOICE_IN"), False),
            tts_rate=_as_int(os.environ.get("SHACK_TTS_RATE"), 0),
            voice_profile=(os.environ.get("SHACK_VOICE") or "rumi").strip().lower(),
            wake_word=(os.environ.get("SHACK_WAKE_WORD") or "hey shack").strip().lower(),
            safe_mode=_as_bool(os.environ.get("SHACK_SAFE_MODE"), True),
            max_tool_rounds=_as_int(os.environ.get("SHACK_MAX_TOOL_ROUNDS"), 6),
            request_timeout=_as_int(os.environ.get("SHACK_TIMEOUT"), 60),
            personality=(os.environ.get("SHACK_PERSONALITY") or "").strip(),
        )
        return cfg

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


def apply_cli_overrides(cfg: Config, **overrides) -> Config:
    """Apply command-line flags on top of the environment configuration."""
    for key, value in overrides.items():
        if value is None:
            continue
        setattr(cfg, key, value)
    return cfg
