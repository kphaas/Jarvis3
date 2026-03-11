SCRAPE_TARGETS = {
    "weather": {
        "url": "https://api.open-meteo.com/v1/forecast?latitude=33.749&longitude=-84.388&current_weather=true&hourly=temperature_2m,precipitation_probability,weathercode&forecast_days=1&temperature_unit=fahrenheit&windspeed_unit=mph",
        "keywords": ["weather", "temperature", "rain", "sunny", "cold", "hot", "humid", "outside"],
        "prompt": "Summarize this weather data for Atlanta in 2 friendly sentences. Convert celsius to fahrenheit if needed:"
    },
    "weather_full": {
        "url": "https://api.open-meteo.com/v1/forecast?latitude=33.749&longitude=-84.388&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode&forecast_days=7&temperature_unit=fahrenheit&windspeed_unit=mph",
        "keywords": ["5 day forecast", "week forecast", "weather this week", "weather forecast"],
        "prompt": "Summarize this 7-day Atlanta weather forecast in 3 friendly sentences:"
    },
    "uga_football": {
        "url": "https://www.espn.com/college-football/team/schedule/_/id/61",
        "keywords": ["uga", "georgia bulldogs", "georgia football", "dawgs"],
        "prompt": "Summarize the latest UGA football news in 2 sentences:"
    },
    "soccer": {
        "url": "https://feeds.bbcnews.com/sport/football/rss.xml",
        "keywords": ["soccer", "football", "fifa", "premier league", "mls", "world cup"],
        "prompt": "Summarize the latest soccer news in 2 sentences:"
    },
    "olympics": {
        "url": "https://feeds.bbcnews.com/sport/olympics/rss.xml",
        "keywords": ["olympics", "olympic games", "team usa"],
        "prompt": "Summarize the latest olympics news in 2 sentences:"
    },
    "tech_news": {
        "url": "https://feeds.feedburner.com/hnrss/newest",
        "keywords": ["tech", "technology", "ai news", "openai", "claude", "apple", "microsoft", "gadgets"],
        "prompt": "Summarize the top tech headlines in 3 sentences:"
    },
    "ai_news": {
        "url": "https://www.reddit.com/r/OpenAI+ClaudeAI+MachineLearning/.rss",
        "keywords": ["ai", "artificial intelligence", "llm", "gpt", "claude", "gemini"],
        "prompt": "Summarize the latest AI news in 3 sentences:"
    },
    "atlanta_news": {
        "url": "https://www.reddit.com/r/atlanta/.rss",
        "keywords": ["atlanta", "alpharetta", "johns creek", "roswell", "local news", "georgia news"],
        "prompt": "Summarize the latest local Atlanta area news in 3 sentences:"
    },
    "world_news": {
        "url": "https://feeds.reuters.com/reuters/topNews",
        "keywords": ["world news", "international", "global news", "breaking news", "news", "latest news", "headlines", "latest", "current events"],
        "prompt": "Summarize the top world news headlines in 3 sentences:"
    },
    "politics": {
        "url": "https://feeds.npr.org/1014/rss.xml",
        "keywords": ["politics", "political", "congress", "senate", "president", "election", "government"],
        "prompt": "Give a balanced summary of the latest political news in 3 sentences:"
    },
    "stocks": {
        "url": "https://finance.yahoo.com/rss/topfinstories",
        "keywords": ["stock", "stocks", "market", "nasdaq", "dow", "s&p", "investing", "financial markets"],
        "prompt": "Summarize the latest financial market news in 2 sentences:"
    },
    "reddit_cfb": {
        "url": "https://www.reddit.com/r/CFB/.rss",
        "keywords": ["college football", "cfb", "ncaa football"],
        "prompt": "Summarize the latest college football news in 2 sentences:"
    },
    "reddit_tech": {
        "url": "https://www.reddit.com/r/technology+gadgets+technews/.rss",
        "keywords": ["reddit tech", "r/technology", "r/gadgets"],
        "prompt": "Summarize the top tech posts in 2 sentences:"
    },
    "reddit_general": {
        "url": "https://www.reddit.com/r/news+worldnews+television/.rss",
        "keywords": ["reddit news", "r/news", "trending"],
        "prompt": "Summarize the top Reddit news stories in 3 sentences:"
    },
    "unraid": {
        "url": "https://www.reddit.com/r/unraid/.rss",
        "keywords": ["unraid", "nas", "home server"],
        "prompt": "Summarize the latest Unraid community posts in 2 sentences:"
    },
    "local_events": {
        "url": "https://www.reddit.com/r/Atlanta/.rss?sort=new",
        "keywords": ["events", "things to do", "kids events", "family events", "weekend", "atlanta events"],
        "prompt": "List any local Atlanta events mentioned in 3 sentences:"
    },
    "unifi_network": {
        "url": "local://unifi",
        "keywords": ["network", "wifi", "devices online", "bandwidth", "connected", "switch", "ap"],
        "prompt": "Summarize the network status in 2 sentences:"
    },
    "unraid_stats": {
        "url": "local://unraid",
        "keywords": ["server", "nas", "disk", "array", "parity", "docker", "vm"],
        "prompt": "Summarize the server status in 2 sentences:"
    },
}

def find_scrape_target(intent: str) -> dict | None:
    lower = intent.lower()
    for name, config in SCRAPE_TARGETS.items():
        if any(k in lower for k in config["keywords"]):
            return {"name": name, **config}
    return None
