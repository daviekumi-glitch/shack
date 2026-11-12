"""Web, search and weather tools (no API keys required)."""

from __future__ import annotations

import base64
import html as html_lib
import json
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse

import requests

from .registry import ToolContext, ToolError, ToolRegistry

UA = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
}

_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<(script|style|noscript|template)[^>]*>.*?</\1>", re.S | re.I)
_WS = re.compile(r"[ \t\r\f\v]+")
_NL = re.compile(r"\n\s*\n+")

WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "freezing fog", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain",
    67: "freezing rain", 71: "light snow", 73: "snow", 75: "heavy snow",
    77: "snow grains", 80: "rain showers", 81: "rain showers",
    82: "violent rain showers", 85: "snow showers", 86: "snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail",
}


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "svg", "head"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def strip_tags(raw: str) -> str:
    return html_lib.unescape(_TAG.sub("", raw or "")).strip()


def html_to_text(raw: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(raw)
    except Exception:  # noqa: BLE001 - malformed html must not crash
        return strip_tags(raw)
    text = "".join(parser.parts)
    text = _WS.sub(" ", text)
    text = _NL.sub("\n\n", text)
    return text.strip()


# ------------------------------------------------------------------- search
def web_search(ctx: ToolContext, query: str, limit: int = 5) -> str:
    query = (query or "").strip()
    if not query:
        raise ToolError("empty search query")
    limit = max(1, min(10, int(limit or 5)))

    results: list[tuple[str, str, str]] = []
    engines = (_bing, _ddg_lite, _ddg_html)
    for engine in engines:
        try:
            results = engine(query, limit)
        except Exception:  # noqa: BLE001 - one engine failing is normal
            results = []
        if results:
            break

    if not results:
        return (
            "No search results came back. The device may be offline or search "
            "engines are blocking the request. Try again, or fetch a known URL."
        )

    lines = [f"Search results for “{query}”:"]
    for i, (title, url, snippet) in enumerate(results, 1):
        lines.append(f"{i}. {title}\n   {url}")
        if snippet:
            lines.append(f"   {snippet}")
    return "\n".join(lines)


def _clean_url(href: str) -> str:
    href = href.replace("&amp;", "&")
    if href.startswith("//"):
        href = "https:" + href
    if "duckduckgo.com/l/" in href:
        target = parse_qs(urlparse(href).query).get("uddg")
        if target:
            return unquote(target[0])
    if "/ck/a" in href:
        raw = parse_qs(urlparse(href).query).get("u", [""])[0]
        if raw.startswith("a1"):
            raw = raw[2:]
        try:
            padded = raw + "=" * (-len(raw) % 4)
            return base64.urlsafe_b64decode(padded).decode("utf-8", "ignore")
        except (ValueError, UnicodeDecodeError):
            return href
    return href


def _bing(query: str, limit: int) -> list[tuple[str, str, str]]:
    resp = requests.get(
        "https://www.bing.com/search",
        params={"q": query, "count": limit, "setlang": "en"},
        headers=UA,
        timeout=20,
    )
    if resp.status_code != 200:
        return []
    blocks = re.split(r'<li class="b_algo"', resp.text)[1:]
    out: list[tuple[str, str, str]] = []
    for block in blocks[:limit]:
        link = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not link:
            continue
        snippet_match = re.search(r"<p[^>]*>(.*?)</p>", block, re.S)
        snippet = strip_tags(snippet_match.group(1)) if snippet_match else ""
        out.append(
            (
                strip_tags(link.group(2))[:160] or "untitled",
                _clean_url(link.group(1)),
                snippet[:300],
            )
        )
    return out


def _ddg_html(query: str, limit: int) -> list[tuple[str, str, str]]:
    resp = requests.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        headers=UA,
        timeout=20,
    )
    if resp.status_code != 200:
        return []
    body = resp.text
    anchors = re.findall(
        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        body,
        re.S,
    )
    snippets = re.findall(
        r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|div|td)>', body, re.S
    )
    out: list[tuple[str, str, str]] = []
    for i, (href, title_raw) in enumerate(anchors[:limit]):
        snippet = strip_tags(snippets[i]) if i < len(snippets) else ""
        out.append(
            (strip_tags(title_raw)[:160] or "untitled", _clean_url(href), snippet[:300])
        )
    return out


def _ddg_lite(query: str, limit: int) -> list[tuple[str, str, str]]:
    resp = requests.get(
        "https://lite.duckduckgo.com/lite/",
        params={"q": query},
        headers=UA,
        timeout=20,
    )
    if resp.status_code != 200:
        return []
    body = resp.text
    anchors = re.findall(
        r'<a[^>]*class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.S
    )
    snippets = re.findall(r'class="result-snippet"[^>]*>(.*?)</td>', body, re.S)
    out: list[tuple[str, str, str]] = []
    for i, (href, title_raw) in enumerate(anchors[:limit]):
        snippet = strip_tags(snippets[i]) if i < len(snippets) else ""
        out.append(
            (strip_tags(title_raw)[:160] or "untitled", _clean_url(href), snippet[:300])
        )
    return out


# -------------------------------------------------------------------- fetch
def fetch_url(ctx: ToolContext, url: str, max_chars: int = 4000) -> str:
    url = (url or "").strip()
    if not url:
        raise ToolError("no url given")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        resp = requests.get(url, headers=UA, timeout=25)
    except requests.RequestException as exc:
        raise ToolError(f"could not reach {url} ({exc.__class__.__name__})") from exc
    if resp.status_code >= 400:
        raise ToolError(f"{url} returned HTTP {resp.status_code}")

    ctype = resp.headers.get("Content-Type", "")
    if not any(word in ctype for word in ("html", "text", "json")):
        return f"{url} is a {ctype or 'binary'} file, not readable text."
    raw = resp.text
    text = html_to_text(_SCRIPT.sub(" ", raw)) if "html" in ctype else raw
    text = re.sub(r"\n{3,}", "\n\n", text)
    limit = max(500, min(12000, int(max_chars or 4000)))
    if len(text) > limit:
        text = text[:limit] + "…"
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
    title = strip_tags(title_match.group(1)) if title_match else url
    return f"{title}\n{url}\n\n{text}"


# ------------------------------------------------------------------ weather
def get_weather(ctx: ToolContext, location: str) -> str:
    location = (location or "").strip()
    if not location:
        raise ToolError("which place? Give a city name")
    try:
        return _weather_open_meteo(location)
    except ToolError:
        return _weather_wttr(location)


def _weather_open_meteo(location: str) -> str:
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": location, "count": 1, "language": "en", "format": "json"},
            headers=UA,
            timeout=15,
        ).json()
    except (requests.RequestException, ValueError) as exc:
        raise ToolError("geocoding unreachable") from exc

    places = geo.get("results") or []
    if not places:
        raise ToolError(f"no place called {location}")
    place = places[0]
    label = ", ".join(
        part
        for part in (place.get("name"), place.get("admin1"), place.get("country"))
        if part
    )
    try:
        data = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                "precipitation,weather_code,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max,weather_code",
                "timezone": "auto",
                "forecast_days": 3,
            },
            headers=UA,
            timeout=15,
        ).json()
    except (requests.RequestException, ValueError) as exc:
        raise ToolError("forecast unreachable") from exc

    cur = data.get("current") or {}
    code = cur.get("weather_code")
    lines = [
        f"Weather in {label}:",
        f"now: {WMO.get(code, 'code ' + str(code))}, {cur.get('temperature_2m')}°C "
        f"(feels {cur.get('apparent_temperature')}°C), humidity "
        f"{cur.get('relative_humidity_2m')}%, wind {cur.get('wind_speed_10m')} km/h",
    ]
    daily = data.get("daily") or {}
    for i, day in enumerate((daily.get("time") or [])[:3]):
        try:
            lines.append(
                f"{day}: {WMO.get(daily['weather_code'][i], 'unsettled')}, "
                f"{daily['temperature_2m_min'][i]}–{daily['temperature_2m_max'][i]}°C, "
                f"rain chance {daily['precipitation_probability_max'][i]}%"
            )
        except (KeyError, IndexError, TypeError):
            continue
    return "\n".join(lines)


def _weather_wttr(location: str) -> str:
    try:
        resp = requests.get(
            f"https://wttr.in/{location}",
            params={"format": "j1"},
            headers={"User-Agent": "curl/8.0"},
            timeout=25,
        )
        data = json.loads(resp.text)
        current = data["current_condition"][0]
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        raise ToolError(f"could not get weather for {location}") from exc

    lines = [
        f"Weather in {location}:",
        f"now: {current['weatherDesc'][0]['value']}, {current['temp_C']}°C "
        f"(feels {current['FeelsLikeC']}°C), humidity {current['humidity']}%, "
        f"wind {current['windspeedKmph']} km/h",
    ]
    for day in (data.get("weather") or [])[:3]:
        lines.append(
            f"{day.get('date')}: {day['hourly'][4]['weatherDesc'][0]['value']}, "
            f"{day.get('mintempC')}–{day.get('maxtempC')}°C"
        )
    return "\n".join(lines)


def register(registry: ToolRegistry) -> None:
    registry.add(
        "web_search",
        "Search the live web for current facts, news, prices, sports, or anything "
        "you do not already know. Returns titles, links and snippets.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"},
                "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 10},
            },
            "required": ["query"],
        },
        web_search,
        group="web",
    )
    registry.add(
        "fetch_url",
        "Download a web page or API endpoint and return its readable text. "
        "Use it after search when you need the details.",
        {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "max_chars": {"type": "integer", "default": 4000},
            },
            "required": ["url"],
        },
        fetch_url,
        group="web",
    )
    registry.add(
        "get_weather",
        "Current weather and a three day forecast for any city or town.",
        {
            "type": "object",
            "properties": {"location": {"type": "string", "description": "City name"}},
            "required": ["location"],
        },
        get_weather,
        group="web",
    )
