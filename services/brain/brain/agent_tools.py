import httpx
import os
import json

BRAIN_URL = "http://100.64.166.22:8182"
ENDPOINT_URL = "http://100.87.223.31:3000"
GATEWAY_URL = "http://100.112.63.25:8282"
ALLOWED_READ_PATHS = [
    "/Users/jarvisbrain/jarvis/services/brain/brain/",
    "/Users/jarvisbrain/jarvis/services/gateway/app/",
    "/Users/jarvisbrain/jarvis/services/endpoint/app/",
]


def _get_secret(key: str) -> str:
    secrets_path = os.path.expanduser("~/jarvis/.secrets")
    try:
        with open(secrets_path) as f:
            for line in f:
                if line.startswith(f"{key}="):
                    return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return ""


async def _try_wikipedia(query: str) -> str | None:
    topic = query.replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"User-Agent": "JARVIS/1.0"})
            if resp.status_code == 200:
                data = resp.json()
                extract = data.get("extract", "")
                if extract and len(extract) > 100:
                    return f"[Wikipedia] {extract[:1500]}"
    except Exception:
        pass
    return None


async def _try_duckduckgo(query: str) -> str | None:
    url = "https://api.duckduckgo.com/"
    params = {"q": query, "format": "json", "no_redirect": "1", "no_html": "1"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params, headers={"User-Agent": "JARVIS/1.0"})
            if resp.status_code == 200:
                data = resp.json()
                abstract = data.get("AbstractText", "")
                answer = data.get("Answer", "")
                related = [r.get("Text", "") for r in data.get("RelatedTopics", [])[:3] if isinstance(r, dict)]
                parts = []
                if answer:
                    parts.append(f"Answer: {answer}")
                if abstract:
                    parts.append(f"Summary: {abstract[:800]}")
                if related:
                    parts.append("Related: " + " | ".join(related)[:400])
                if parts:
                    return f"[DuckDuckGo] " + " ".join(parts)
    except Exception:
        pass
    return None


async def _try_perplexity(query: str) -> str:
    payload = {"intent": query, "complexity": 3}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{BRAIN_URL}/v1/ask", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return f"[Perplexity] {data.get('response', 'No response')[:1500]}"
    except Exception:
        pass
    return "web_search: no results found"


async def tool_ask(input_text: str) -> str:
    payload = {"intent": input_text, "complexity": 2}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{BRAIN_URL}/v1/ask", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", str(data))


async def tool_web_search(input_text: str) -> str:
    wiki = await _try_wikipedia(input_text)
    if wiki:
        return wiki
    ddg = await _try_duckduckgo(input_text)
    if ddg:
        return ddg
    return await _try_perplexity(input_text)


async def tool_weather(input_text: str) -> str:
    city = input_text.strip()

    api_key = _get_secret("OPENWEATHER_API_KEY")
    if api_key:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"q": city, "appid": api_key, "units": "imperial"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    d = resp.json()
                    desc = d["weather"][0]["description"].capitalize()
                    temp = d["main"]["temp"]
                    feels = d["main"]["feels_like"]
                    humidity = d["main"]["humidity"]
                    wind = d["wind"]["speed"]
                    city_name = d.get("name", city)
                    return (f"[OpenWeatherMap] {city_name}: {desc}, {temp:.0f}°F "
                            f"(feels like {feels:.0f}°F), humidity {humidity}%, "
                            f"wind {wind:.0f} mph")
        except Exception:
            pass

    try:
        city_encoded = city.replace(" ", "+")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"https://wttr.in/{city_encoded}?format=4",
                                    headers={"User-Agent": "JARVIS/1.0"})
            if resp.status_code == 200 and resp.text.strip():
                return f"[wttr.in] {resp.text.strip()}"
    except Exception as e:
        return f"weather error: {e}"

    return "weather: unable to fetch weather data"


async def tool_news(input_text: str) -> str:
    api_key = _get_secret("NEWS_API_KEY")
    if not api_key:
        return "news: NEWS_API_KEY not found in secrets"
    url = "https://newsapi.org/v2/everything"
    params = {"q": input_text, "sortBy": "publishedAt", "pageSize": 5,
              "language": "en", "apiKey": api_key}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                articles = data.get("articles", [])
                if not articles:
                    return "news: no articles found"
                lines = []
                for a in articles[:5]:
                    title = a.get("title", "")
                    source = a.get("source", {}).get("name", "")
                    published = a.get("publishedAt", "")[:10]
                    lines.append(f"[{published}] {source}: {title}")
                return "[NewsAPI] " + "\n".join(lines)
            return f"news: API error {resp.status_code}"
    except Exception as e:
        return f"news error: {e}"


async def tool_sports(input_text: str) -> str:
    lower = input_text.lower()

    if any(k in lower for k in ["uga", "georgia bulldogs", "bulldogs", "college football", "cfb"]):
        return await _espn_cfb_uga()
    elif any(k in lower for k in ["world cup", "fifa", "soccer"]):
        url = "https://www.thesportsdb.com/api/v1/json/3/eventsseason.php?id=4328&s=2024-2025"
    elif any(k in lower for k in ["olympics", "olympic"]):
        url = "https://www.thesportsdb.com/api/v1/json/3/searchevents.php?e=Olympics"
    else:
        url = f"https://www.thesportsdb.com/api/v1/json/3/searchevents.php?e={input_text.replace(' ', '+')}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"User-Agent": "JARVIS/1.0"})
            if resp.status_code == 200:
                data = resp.json()
                events = data.get("events") or data.get("results") or []
                if not events:
                    return "sports: no events found"
                lines = []
                for e in events[:5]:
                    name = e.get("strEvent", "")
                    date = e.get("dateEvent", "")
                    home = e.get("intHomeScore", "")
                    away = e.get("intAwayScore", "")
                    score = f" {home}-{away}" if home != "" and away != "" else ""
                    lines.append(f"[{date}] {name}{score}")
                return "[TheSportsDB] " + "\n".join(lines)
            return f"sports: API error {resp.status_code}"
    except Exception as e:
        return f"sports error: {e}"


async def _espn_cfb_uga() -> str:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/61/schedule",
                params={"season": "2025"},
                headers={"User-Agent": "JARVIS/1.0"}
            )
            if resp.status_code != 200:
                return f"sports: ESPN API error {resp.status_code}"
            data = resp.json()
            events = data.get("events", [])
            if not events:
                return "sports: no UGA games found for 2025 season"
            lines = []
            for e in events[-6:]:
                name = e.get("shortName", "")
                date = e.get("date", "")[:10]
                comps = e.get("competitions", [{}])[0]
                competitors = comps.get("competitors", [])
                score_parts = []
                for c in competitors:
                    team = c.get("team", {}).get("abbreviation", "")
                    score = c.get("score", {}).get("displayValue", "")
                    if team and score:
                        score_parts.append(f"{team} {score}")
                score_str = " | ".join(score_parts) if score_parts else "scheduled"
                lines.append(f"[{date}] {name} — {score_str}")
            return "[ESPN] UGA 2025 Season:\n" + "\n".join(lines)
    except Exception as e:
        return f"sports error: {e}"


async def tool_file_read(input_text: str) -> str:
    abs_path = os.path.abspath(input_text)
    allowed = any(abs_path.startswith(p) for p in ALLOWED_READ_PATHS)
    if not allowed:
        return f"BLOCKED: path not in allowed list: {abs_path}"
    try:
        with open(abs_path, "r") as f:
            return f.read()[:3000]
    except Exception as e:
        return f"file_read error: {e}"


async def tool_code_write(input_text: str) -> str:
    payload = {"goal": input_text, "language": "python"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{BRAIN_URL}/v1/code/write", json=payload)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("filepath", "") + " — " + data.get("status", "")
        return f"code_write failed: {resp.status_code} {resp.text[:200]}"


TOOL_MAP = {
    "ask": tool_ask,
    "web_search": tool_web_search,
    "weather": tool_weather,
    "news": tool_news,
    "sports": tool_sports,
    "code_write": tool_code_write,
    "file_read": tool_file_read,
}


async def run_tool(tool: str, input_text: str) -> str:
    fn = TOOL_MAP.get(tool)
    if not fn:
        return f"unknown tool: {tool}"
    return await fn(input_text)
