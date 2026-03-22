#!/usr/bin/env python3
import os
import re
import base64
import datetime
import feedparser
import requests
import anthropic
from zoneinfo import ZoneInfo

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MorningBrief/1.0)"}

SECTION_COLORS = {
    "World":    "#2563eb",
    "Tech":     "#7c3aed",
    "AI":       "#0891b2",
    "India":    "#ea580c",
    "Markets":  "#d97706",
    "Health":   "#16a34a",
}

SECTIONS = {
    "World": {
        "emoji": "🌍",
        "feeds": [
            "http://feeds.bbci.co.uk/news/world/rss.xml",
            "https://feeds.reuters.com/reuters/worldNews",
            "https://feeds.npr.org/1001/rss.xml",
        ],
    },
    "Tech": {
        "emoji": "🚀",
        "feeds": [
            "https://techcrunch.com/feed/",
            "https://www.wired.com/feed/rss",
            "https://feeds.arstechnica.com/arstechnica/index",
        ],
    },
    "AI": {
        "emoji": "🤖",
        "feeds": [
            "https://www.technologyreview.com/feed/",
            "https://venturebeat.com/category/ai/feed/",
            "https://the-decoder.com/feed/",
        ],
    },
    "India": {
        "emoji": "🇮🇳",
        "feeds": [
            "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
            "https://www.thehindu.com/feeder/default.rss",
            "https://indianexpress.com/feed/",
            "https://www.livemint.com/rss/news",
        ],
    },
    "Markets": {
        "emoji": "📈",
        "feeds": [
            "https://feeds.reuters.com/reuters/businessNews",
            "https://feeds.bloomberg.com/markets/news.rss",
            "https://www.cnbc.com/id/10000664/device/rss/rss.html",
        ],
    },
    "Health": {
        "emoji": "🧬",
        "feeds": [
            "https://www.statnews.com/feed/",
            "https://www.sciencedaily.com/rss/health_medicine.xml",
            "https://longevity.technology/feed/",
        ],
    },
}

HARSHITA_LENS = """About Harshita (use this lens for "why it matters"):
- Senior Analytics Engineer, 6 years in data, actively moving into product/growth
- Runs a podcast (Founders Without Borders) interviewing immigrant founders building generational businesses
- Works at startups, gravitates toward high-growth early-stage companies
- Building side projects and mini tools to share publicly
- Tracks finances closely, interested in markets and wealth-building
- Cares deeply about India tech/business, founder stories, and the data/AI/product intersection"""


def fetch_articles(feeds, max_per_feed=6):
    articles = []
    for url in feeds:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:max_per_feed]:
                title = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                summary = re.sub(r"<[^>]+>", "", summary)[:400]
                if title:
                    articles.append({
                        "title": title,
                        "summary": summary,
                        "link": entry.get("link", ""),
                    })
        except Exception as e:
            print(f"  Warning: could not fetch {url}: {e}")
    return articles[:12]


def reading_time(html):
    text = re.sub(r"<[^>]+>", "", html)
    words = len(text.split())
    mins = max(1, round(words / 200))
    return f"~{mins} min"


def generate_section_html(client, section_name, articles, covered_titles):
    if not articles:
        return "<p>No stories available today.</p>"

    articles_text = "\n".join(
        [f"- {a['title']}: {a['summary']} [url: {a.get('link', '')}]" for a in articles]
    )

    dedup_note = ""
    if covered_titles:
        dedup_note = f"\nAlready covered in earlier sections (do not repeat these topics): {', '.join(covered_titles)}\n"

    prompt = f"""You are writing the "{section_name}" section of Harshita's Morning Brief — a personal daily digest.

{HARSHITA_LENS}

Here are today's raw headlines and summaries:

{articles_text}
{dedup_note}
Pick the 2-3 stories that actually matter. Skip noise. If something is a big deal, say so clearly.

For each story write:
1. A sharp, direct headline
2. A 2-3 sentence summary of what happened (no fluff, no passive voice)
3. Why it matters — use Harshita's context to CHOOSE what's relevant, but do NOT explicitly reference her personal details, preferences, or activities in the text. Never write things like "You work at startups", "You're building side projects", "For your podcast", "As someone who tracks markets". Instead, explain WHY the story matters in terms of its implications for startups, growth, markets, India tech, or the data/AI/product space — let the relevance speak for itself.
4. One "so what" sentence — the single most important takeaway, stated bluntly
5. A "Read more →" link using the actual URL from the feed data

Tone: Write like a sharp friend who's done the reading. Direct, opinionated, allergic to filler. If something is big, say it's big.

For each story also assign one impact tag from this exact list — pick whichever fits best:
- <span class="story-tag tag-red">⚠️ Ethical Risk</span>
- <span class="story-tag tag-red">🚨 Breaking</span>
- <span class="story-tag tag-orange">⚡ Geopolitical</span>
- <span class="story-tag tag-green">📈 Macro Growth</span>
- <span class="story-tag tag-green">💡 Opportunity</span>
- <span class="story-tag tag-purple">🤖 AI Shift</span>
- <span class="story-tag tag-blue">👀 Watch This</span>
- <span class="story-tag tag-amber">💰 Market Signal</span>
- <span class="story-tag tag-amber">📉 Risk Signal</span>
- <span class="story-tag tag-teal">🧬 Health Breakthrough</span>

Output ONLY raw HTML — no markdown, no code fences, no backticks, no explanation.
Use exactly this structure for each story — every element is a div, no p tags at the top level of .story:

<div class="story">
  <div class="story-header">
    <h3 class="story-title">Headline here</h3>
    <span class="story-tag tag-COLOR">EMOJI Label</span>
  </div>
  <div class="story-summary"><p>2-3 sentence summary.</p></div>
  <div class="story-block"><strong>Why it matters:</strong> Specific reason this matters to Harshita.</div>
  <div class="story-block story-sowhat"><strong>So what:</strong> Single most important takeaway.</div>
  <div class="story-source"><a class="read-more" href="URL">Read more →</a></div>
</div>

CRITICAL: Every block inside .story is a <div>. Do NOT use <p> tags as direct children of <div class="story">. Do NOT add extra </div> tags.

Start your response directly with the first <div> tag. Nothing before or after the HTML."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return clean_story_html(response.content[0].text.strip())


def generate_tldr(client, section_summaries):
    """Generate a Top 3 across all sections."""
    all_stories = "\n".join(
        [f"[{s}] {t}" for s, titles in section_summaries.items() for t in titles]
    )

    prompt = f"""You are writing a "Today's Top 3" executive summary for Harshita's Morning Brief.

{HARSHITA_LENS}

Here are today's stories across all sections:
{all_stories}

Pick the 3 most important stories overall — the ones with the biggest real-world impact or most relevance to Harshita.

For each, write one punchy sentence: what happened and why it matters to Harshita specifically.

Output ONLY raw HTML — no markdown, no code fences, no backticks, no explanation.
Use exactly this structure (3 items):

<div class="tldr-item"><span class="tldr-num">1</span><p class="tldr-text"><strong>Section Name:</strong> One sharp sentence.</p></div>
<div class="tldr-item"><span class="tldr-num">2</span><p class="tldr-text"><strong>Section Name:</strong> One sharp sentence.</p></div>
<div class="tldr-item"><span class="tldr-num">3</span><p class="tldr-text"><strong>Section Name:</strong> One sharp sentence.</p></div>

Start directly with the first <div>. Nothing before or after."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return clean_tldr_html(response.content[0].text.strip())


def clean_story_html(html):
    """Extract content from each story and rebuild with correct div structure."""

    def rebuild_one(body):
        """Given raw HTML for a single story (without outer <div class='story'>),
        extract components and return clean HTML."""
        title = re.search(r'<h3 class="story-title">(.*?)</h3>', body, re.DOTALL)
        tag = re.search(r'(<span class="story-tag[^"]*">[^<]*</span>)', body)
        sm = re.search(
            r'class="story-summary">\s*(?:<p>|<div>)?(.*?)(?:</p>|</div>)',
            body, re.DOTALL
        )
        why = re.search(
            r'<strong>Why it matters:</strong>\s*(.*?)(?:</div>|</p>)',
            body, re.DOTALL
        )
        sowhat = re.search(
            r'<strong>So what:</strong>\s*(.*?)(?:</div>|</p>)',
            body, re.DOTALL
        )
        source = re.search(r'(<a class="read-more"[^>]*>Read more →</a>)', body)

        r = '<div class="story">\n'
        if title and tag:
            r += f'  <div class="story-header">\n    <h3 class="story-title">{title.group(1).strip()}</h3>\n    {tag.group(1)}\n  </div>\n'
        elif title:
            r += f'  <h3 class="story-title">{title.group(1).strip()}</h3>\n'
        if sm and sm.group(1).strip():
            r += f'  <div class="story-summary"><p>{sm.group(1).strip()}</p></div>\n'
        if why and why.group(1).strip():
            r += f'  <div class="story-block"><strong>Why it matters:</strong> {why.group(1).strip()}</div>\n'
        if sowhat and sowhat.group(1).strip():
            r += f'  <div class="story-block story-sowhat"><strong>So what:</strong> {sowhat.group(1).strip()}</div>\n'
        if source:
            r += f'  <div class="story-source">{source.group(1)}</div>\n'
        r += '</div>'
        return r

    # Find all story blocks and replace them in-place
    # Pattern: <div class="story"> ... up to next <div class="story"> or </section>
    pattern = r'<div class="story">(.+?)(?=<div class="story">|</section>)'
    html = re.sub(
        pattern,
        lambda m: rebuild_one(m.group(1)),
        html,
        flags=re.DOTALL,
    )
    return html


def clean_tldr_html(html):
    """Ensure every tldr-item div is properly closed."""
    # Fix: <div class="tldr-item">...<p>...</p>\n<div class="tldr-item"> (missing </div>)
    html = re.sub(
        r'(</p>)\s*\n(\s*<div class="tldr-item">)',
        r'\1</div>\n\2',
        html,
    )
    # Also fix if the last item is missing </div> before the parent closes
    html = re.sub(
        r'(</p>)\s*\n(\s*</div>)(?!\s*\n\s*</div>)',
        r'\1</div>\n\2',
        html,
    )
    # Prevent double-closing: </div></div>\n</div> -> </div>\n</div>
    # Only for tldr context — match </p></div></div> and dedupe
    html = re.sub(r'(</p>)</div></div>', r'\1</div>', html)

    return html


def extract_titles(html):
    return re.findall(r'class="story-title"[^>]*>([^<]+)<', html)


def fetch_sf_weather():
    """Fetch current weather for San Francisco using Open-Meteo (free, no API key)."""
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": 37.7749,
                "longitude": -122.4194,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "America/Los_Angeles",
                "forecast_days": 1,
            },
            timeout=10,
        )
        data = resp.json()
        cur = data["current"]
        daily = data["daily"]

        # Map WMO weather codes to descriptions + emoji
        wmo = {
            0: ("Clear sky", "☀️"), 1: ("Mostly clear", "🌤️"), 2: ("Partly cloudy", "⛅"),
            3: ("Overcast", "☁️"), 45: ("Foggy", "🌫️"), 48: ("Foggy", "🌫️"),
            51: ("Light drizzle", "🌦️"), 53: ("Drizzle", "🌦️"), 55: ("Heavy drizzle", "🌦️"),
            61: ("Light rain", "🌧️"), 63: ("Rain", "🌧️"), 65: ("Heavy rain", "🌧️"),
            80: ("Light showers", "🌦️"), 81: ("Showers", "🌧️"), 82: ("Heavy showers", "🌧️"),
        }
        code = cur.get("weather_code", 0)
        desc, emoji = wmo.get(code, ("Unknown", "🌡️"))
        temp = round(cur["temperature_2m"])
        high = round(daily["temperature_2m_max"][0])
        low = round(daily["temperature_2m_min"][0])
        humidity = cur["relative_humidity_2m"]
        wind = round(cur["wind_speed_10m"])
        rain_pct = daily["precipitation_probability_max"][0]

        return {
            "emoji": emoji,
            "desc": desc,
            "temp": temp,
            "high": high,
            "low": low,
            "humidity": humidity,
            "wind": wind,
            "rain_pct": rain_pct,
        }
    except Exception as e:
        print(f"  Warning: could not fetch weather: {e}")
        return None


def tldr_html_to_email_table(tldr_html):
    """Convert div-based TLDR HTML to table-based layout for email clients."""
    items = re.findall(
        r'<span class="tldr-num">(\d+)</span>\s*<p class="tldr-text">(.*?)</p>',
        tldr_html,
        re.DOTALL,
    )
    if not items:
        return tldr_html  # fallback: return as-is

    rows = ""
    for num, text in items:
        rows += f"""
    <tr>
      <td style="vertical-align:top;padding-right:12px;padding-bottom:14px;">
        <div style="width:24px;height:24px;border-radius:50%;background:#2563eb;color:white;font-size:11px;font-weight:800;text-align:center;line-height:24px;">{num}</div>
      </td>
      <td style="vertical-align:top;padding-bottom:14px;font-size:14px;color:#0f172a;line-height:1.55;">
        {text}
      </td>
    </tr>"""

    return f'<table cellpadding="0" cellspacing="0" border="0" width="100%">{rows}\n    </table>'


def send_email(date_str, tldr_html, time_str):
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print("No RESEND_API_KEY — skipping email")
        return

    brief_url = "https://harshitagirase.github.io/ai-daily-briefing/"

    # Fetch weather for San Francisco
    weather = fetch_sf_weather()
    weather_html = ""
    if weather:
        weather_html = f"""
    <div style="background:#f0f7ff;border-radius:10px;padding:16px 20px;margin-bottom:24px;">
      <div style="font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#2563eb;margin-bottom:10px;">San Francisco Weather</div>
      <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:8px;">
        <tr>
          <td style="font-size:2rem;padding-right:12px;vertical-align:middle;">{weather['emoji']}</td>
          <td style="vertical-align:middle;">
            <div style="font-size:1.3rem;font-weight:800;color:#0f172a;">{weather['temp']}°F</div>
            <div style="font-size:0.82rem;color:#475569;">{weather['desc']}</div>
          </td>
        </tr>
      </table>
      <div style="font-size:0.8rem;color:#475569;line-height:1.6;">
        High {weather['high']}°F &middot; Low {weather['low']}°F &middot; 💧 {weather['rain_pct']}% rain &middot; 💨 {weather['wind']} mph
      </div>
    </div>"""

    # Convert div-based TLDR to table-based for email compatibility
    email_tldr = tldr_html_to_email_table(tldr_html)

    email_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family:'Open Sans',-apple-system,BlinkMacSystemFont,sans-serif;background:#f4f4f4;margin:0;padding:0;">
<div style="max-width:600px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
  <div style="background:linear-gradient(135deg,#1e3a8a,#2563eb);padding:28px 32px;">
    <div style="display:inline-block;background:rgba(255,255,255,0.2);color:white;font-weight:800;font-size:1rem;padding:8px 14px;border-radius:10px;letter-spacing:0.04em;margin-bottom:14px;">HG</div>
    <h1 style="color:white;font-size:1.4rem;font-weight:800;margin:0 0 4px;">☀️ Harshita's Morning Brief</h1>
    <p style="color:rgba(255,255,255,0.75);font-size:0.85rem;margin:0;">{date_str} &middot; Generated at {time_str}</p>
  </div>
  <div style="padding:28px 32px;">
    {weather_html}
    <p style="font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#2563eb;margin:0 0 14px;">Today's Top 3</p>
    {email_tldr}
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;">
    <div style="text-align:center;padding:8px 0 4px;">
      <a href="{brief_url}" style="display:inline-block;background:#2563eb;color:white;font-weight:700;font-size:0.9rem;text-decoration:none;padding:12px 28px;border-radius:8px;">Read the full brief →</a>
    </div>
  </div>
  <div style="padding:16px 32px 24px;text-align:center;color:#94a3b8;font-size:0.75rem;">
    You're receiving this because you set it up. &middot; <a href="{brief_url}" style="color:#2563eb">View online</a>
  </div>
</div>
</body>
</html>"""

    # Format short date for subject line (e.g. "March 22")
    short_date = datetime.datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%B %-d")

    resp = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": "onboarding@resend.dev",
            "to": "harshitagirase97@gmail.com",
            "subject": f"Hi Harshita! Here's the brief for {short_date}",
            "html": email_html,
        },
    )
    if resp.status_code in (200, 201):
        print("✅ Email sent")
    else:
        print(f"❌ Email failed ({resp.status_code}): {resp.text}")


def generate_digest():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    client = anthropic.Anthropic(api_key=api_key)
    now = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
    date_str = now.strftime("%A, %B %-d, %Y")
    time_str = now.strftime("%-I:%M %p %Z")
    iso_ts = now.isoformat()

    sections_html = ""
    nav_pills = ""
    section_summaries = {}
    covered_titles = []

    for section_name, config in SECTIONS.items():
        emoji = config["emoji"]
        section_id = section_name.lower().replace(" & ", "-").replace(" ", "-")
        color = SECTION_COLORS[section_name]

        print(f"Fetching {section_name}...")
        articles = fetch_articles(config["feeds"])
        print(f"  Got {len(articles)} articles. Summarizing with Claude...")
        stories_html = generate_section_html(client, section_name, articles, covered_titles)

        # Track titles for deduplication
        titles = extract_titles(stories_html)
        covered_titles.extend(titles)
        section_summaries[section_name] = titles

        read_time = reading_time(stories_html)

        sections_html += f"""
        <section id="{section_id}" class="section">
            <div class="section-header" style="border-color:{color}">
                <div class="section-title-wrap">
                    <span class="section-emoji">{emoji}</span>
                    <h2 class="section-title">{section_name}</h2>
                </div>
                <span class="section-meta">{read_time}</span>
            </div>
            {stories_html}
        </section>
"""
        nav_pills += f'<a href="#{section_id}" class="nav-pill" style="color:{color};border-color:{color}">{emoji} {section_name}</a>\n'

    print("Generating Top 3 TLDR...")
    tldr_html = generate_tldr(client, section_summaries)
    email_tldr = tldr_html  # save before embedding in page

    # SVG favicon (HG initials) — base64 encoded to avoid quote-escaping issues
    favicon_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#2563eb"/><text x="16" y="22" text-anchor="middle" font-family="system-ui,sans-serif" font-weight="800" font-size="13" fill="white">HG</text></svg>'
    favicon_uri = "data:image/svg+xml;base64," + base64.b64encode(favicon_svg.encode()).decode()

    page = f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Harshita's Morning Brief — {date_str}</title>
    <link rel="icon" href="{favicon_uri}">
    <link rel="stylesheet" href="style.css">

    <!-- Open Graph -->
    <meta property="og:title" content="Harshita's Morning Brief — {date_str}">
    <meta property="og:description" content="A personal daily digest across Tech, US, World, India, Science, Health, and Business — curated with a sharp, opinionated lens.">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://harshitagirase.github.io/ai-daily-briefing/">
</head>
<body>
<div class="container">

    <header class="site-header">
        <div class="header-left">
            <div class="hg-logo">HG</div>
            <div class="header-titles">
                <p class="eyebrow">Morning Brief</p>
                <h1>Harshita's Morning Brief</h1>
                <p class="tagline">Curated daily. Opinionated by design.</p>
            </div>
        </div>
        <div class="header-right">
            <div class="date-badge">{date_str}</div>
            <button class="dark-toggle" id="darkToggle" title="Toggle dark mode">🌙</button>
        </div>
    </header>

    <hr class="divider">

    <div class="freshness">
        <span class="freshness-dot" id="freshDot"></span>
        <span id="freshLabel">Generated at {time_str}</span>
    </div>

    <div class="tldr">
        <p class="tldr-label">Today's Top 3</p>
        {tldr_html}
    </div>

    <nav class="jump-nav">
        <p class="nav-label">Jump to section</p>
        <div class="nav-links">
            {nav_pills}
        </div>
    </nav>

    <main>
        {sections_html}
    </main>

    <footer>
        <p>Generated at {time_str} &middot; Powered by Claude + RSS feeds</p>
    </footer>

</div>

<script>
(function() {{
    // Dark mode
    var toggle = document.getElementById('darkToggle');
    var html = document.documentElement;
    var saved = localStorage.getItem('theme') || 'light';
    html.setAttribute('data-theme', saved);
    toggle.textContent = saved === 'dark' ? '☀️' : '🌙';

    toggle.addEventListener('click', function() {{
        var current = html.getAttribute('data-theme');
        var next = current === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
        toggle.textContent = next === 'dark' ? '☀️' : '🌙';
    }});

    // Staleness indicator
    var generated = new Date('{iso_ts}');
    var now = new Date();
    var hoursAgo = (now - generated) / 3600000;
    var dot = document.getElementById('freshDot');
    var label = document.getElementById('freshLabel');
    if (hoursAgo < 2) {{
        dot.className = 'freshness-dot';
        label.textContent = 'Fresh — generated at {time_str}';
    }} else if (hoursAgo < 12) {{
        dot.className = 'freshness-dot stale';
        label.textContent = Math.floor(hoursAgo) + 'h ago — updates daily at 6 AM PT';
    }} else {{
        dot.className = 'freshness-dot very-stale';
        label.textContent = 'Yesterday\u2019s edition — updates daily at 6 AM PT';
    }}
}})();
</script>
</body>
</html>"""

    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(page)

    print("✅ Saved index.html")
    send_email(date_str, email_tldr, time_str)


if __name__ == "__main__":
    generate_digest()
