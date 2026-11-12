"""The language brain: a thin, dependable Groq (OpenAI-compatible) client."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:  # requests is the only third-party dependency
    import requests
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: requests.\nInstall it with:  pip install -r requirements.txt"
    ) from exc

BASE_URL = "https://api.groq.com/openai/v1"


class BrainError(RuntimeError):
    """Raised when the model cannot be reached or refuses the request."""


class Brain:
    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-oss-20b",
        timeout: int = 60,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise BrainError(
                "No API key found. Set GROQ_KEY (or SHACK_API_KEY) in your "
                ".env file. Get a free key at https://console.groq.com/keys"
            )
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()

    # ------------------------------------------------------------------ http
    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "SHACK/2.0",
        }

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{BASE_URL}/{endpoint}"
        last_error = "unknown error"
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.post(
                    url, headers=self._headers, json=payload, timeout=self.timeout
                )
            except requests.RequestException as exc:
                last_error = f"network problem ({exc.__class__.__name__})"
            else:
                if resp.status_code == 200:
                    return resp.json()
                detail = _error_detail(resp)
                if resp.status_code in (401, 403):
                    raise BrainError(
                        "Groq rejected the API key. Check GROQ_KEY in your .env "
                        f"file. ({detail})"
                    )
                if resp.status_code == 404:
                    raise BrainError(
                        f"Model '{self.model}' is not available on this key. "
                        "Try SHACK_MODEL=openai/gpt-oss-20b or llama-3.3-70b-versatile."
                    )
                if resp.status_code == 429:
                    last_error = "rate limit reached"
                elif resp.status_code >= 500:
                    last_error = f"Groq server error {resp.status_code}"
                else:
                    raise BrainError(f"Groq error {resp.status_code}: {detail}")
            if attempt < self.max_retries:
                time.sleep(min(2**attempt, 8))
        raise BrainError(f"Could not reach the model after {self.max_retries} tries: {last_error}")

    # ------------------------------------------------------------------ chat
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.6,
        max_tokens: int = 900,
    ) -> dict[str, Any]:
        """Return the raw assistant message dict (may contain tool_calls)."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        data = self._post("chat/completions", payload)
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise BrainError("Groq returned an unexpected response.") from exc

        if not message.get("content") and not message.get("tool_calls"):
            message = dict(message)
            message["content"] = "(no answer)"
        return message

    # ------------------------------------------------------------ transcribe
    def transcribe(self, audio_path: Path, language: str | None = None) -> str:
        """Speech to text with Groq Whisper."""
        url = f"{BASE_URL}/audio/transcriptions"
        data = {"model": "whisper-large-v3-turbo"}
        if language:
            data["language"] = language
        try:
            with open(audio_path, "rb") as handle:
                resp = self._session.post(
                    url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": (Path(audio_path).name, handle, "audio/mp4")},
                    data=data,
                    timeout=self.timeout,
                )
        except OSError as exc:
            raise BrainError(f"Could not read the recording: {exc}") from exc
        except requests.RequestException as exc:
            raise BrainError(f"Transcription failed ({exc.__class__.__name__}).") from exc

        if resp.status_code != 200:
            raise BrainError(f"Transcription failed: {_error_detail(resp)}")
        return (resp.json().get("text") or "").strip()

    # -------------------------------------------------------------- summary
    def summarise(self, transcript: str) -> str:
        """Compress older conversation turns into a short memory note."""
        prompt = (
            "Compress this conversation into at most 6 short bullet-free "
            "sentences. Keep names, preferences, decisions, open tasks and "
            "anything the user asked to remember. Drop small talk."
        )
        message = self.chat(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": transcript[:12000]},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        return (message.get("content") or "").strip()


def _error_detail(resp: Any) -> str:
    try:
        body = resp.json()
    except ValueError:
        return (resp.text or "")[:200]
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err)[:200]
        if err:
            return str(err)[:200]
        return json.dumps(body)[:200]
    return str(body)[:200]
