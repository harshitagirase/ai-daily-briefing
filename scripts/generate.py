#!/usr/bin/env python3
import os
import datetime
import feedparser
import requests
import anthropic
from zoneinfo import ZoneInfo

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MorningBrief/1.0)"}

SECTIONS = {
    "Tech": {
        "emoji": "💻",
        "feeds": [
            "https://techcrunch.com/feed/",
            "https://www.wired.com/feed/rss",
            "https://feeds.arstechnica.com/arstechnica/index",
        ],
    },
    "US": {
        "emoji": "🇺🇸",
        "feeds": [
            "https://feeds.npr.org/1001/rss.xml",
            "http://feeds.bbci.co.uk/news/rss.xml",
        ],
    },
    "World": {
        "emoji": "🌍",
        "feeds": [
            "http://feeds.bbci.co.uk/news/world/rss.xml",
            "https://feeds.reuters.com/reuters/worldNews",
        ],
    },
    "India": {
        "emoji": "🇮🇳",
        "feeds": [
            "https://feeds.feedburner.com/ndtvnews-india-news",
            "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
        ],
    },
    "Science": {
        "emoji": "🔬",
        "feeds": [
            "https://www.sciencedaily.com/rss/all.xml",
            "https://www.newscientist.com/feed/home/",
        ],
    },
    "Health": {
        "emoji": "🧠",
        "feeds": [
            "https://rss.medicalnewstoday.com/featurednews.xml",
            "https://www.statnews.com/feed/",
        ],
    },
    "Business": {
        "emoji": "📈",
        "feeds": [
            "https://feeds.reuters.com/reuters/businessNews",
            "https://feeds.bloomberg.com/markets/news.rss",
        ],
    },
}


def fetch_articles(feeds, max_per_feed=6):
    articles = []
    for url in feeds:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:max_per_feed]:
                title = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                # Strip any HTML tags from summary
                import re
                summary = re.sub(r"<[^>]+>", "", summary)[:400]
                if title:
                    articles.append({"title": title, "summary": summary})
        except Exception as e:
            print(f"  Warning: could not fetch {url}: {e}")
    return articles[:12]


def generate_section_html(client, section_name, articles):
    if not articles:
        return "<p>No stories available today.</p>"

    articles_text = "\n".join(
        [f"- {a['title']}: {a['summary']}" for a in articles]
    )

    prompt = f"""You are writing the "{section_name}" section of a daily news digest called "Harshita's Morning Brief".

Here are today's raw headlines and summaries from RSS feeds:

{articles_text}

Pick the 3-5 most important or interesting stories. For each:
- Write a punchy, clear headline
- Write 2-3 sentences: what happened + why it matters
- Tone: smart, direct, no fluff

Output ONLY raw HTML — no markdown, no code fences, no backticks, no explanation.
Use exactly this structure for each story:

<div class="story">
  <h3 class="story-title">Headline here</h3>
  <p class="story-body">What happened. Why it matters.</p>
</div>

Start your response directly with the first <div> tag. Nothing before or after the HTML."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate_digest():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    client = anthropic.Anthropic(api_key=api_key)
    now = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
    date_str = now.strftime("%A, %B %-d, %Y")
    time_str = now.strftime("%-I:%M %p %Z")

    sections_html = ""
    nav_links = ""

    for section_name, config in SECTIONS.items():
        emoji = config["emoji"]
        section_id = section_name.lower()

        print(f"Fetching {section_name}...")
        articles = fetch_articles(config["feeds"])
        print(f"  Got {len(articles)} articles. Summarizing with Claude...")
        stories_html = generate_section_html(client, section_name, articles)

        sections_html += f"""
        <section id="{section_id}" class="section">
            <h2 class="section-title">{emoji} {section_name}</h2>
            {stories_html}
        </section>
"""
        nav_links += f'<a href="#{section_id}" class="nav-link">{emoji} {section_name}</a>\n'

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Harshita's Morning Brief — {date_str}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <header>
            <p class="eyebrow">MORNING BRIEF</p>
            <h1>&#9728;&#65039; Harshita's Morning Brief</h1>
            <p class="date">{date_str}</p>
            <hr class="divider">
        </header>

        <nav class="jump-nav">
            <p class="nav-label">JUMP TO SECTION</p>
            <div class="nav-links">
                {nav_links}
            </div>
        </nav>

        <main>
            {sections_html}
        </main>

        <footer>
            <p>Generated at {time_str} &middot; Powered by Claude + RSS feeds</p>
        </footer>
    </div>
</body>
</html>"""

    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(page)

    print(f"✅ Saved index.html")


if __name__ == "__main__":
    generate_digest()
