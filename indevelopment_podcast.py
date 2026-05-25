#!/usr/bin/env python3
"""
In Development Magazine → Podcast
Fetches new articles from indevelopmentmag.com,
converts to MP3 via Edge TTS, commits audio + RSS feed to GitHub Pages.

Subscribe in Pocket Casts: https://lcrawfurd.github.io/indevelopment-podcast/feed.xml
"""

import asyncio
import json
import os
import re
import subprocess
from datetime import datetime
from email.utils import formatdate
from pathlib import Path

import edge_tts
import requests
from bs4 import BeautifulSoup
from readability import Document

# ── Config ─────────────────────────────────────────────────────────────────
BLOG_URL     = "https://www.indevelopmentmag.com"
BASE_DIR     = Path(__file__).parent
AUDIO_DIR    = BASE_DIR / "audio"
PROCESSED    = BASE_DIR / "processed.json"
FEED_FILE    = BASE_DIR / "feed.xml"
GITHUB_USER  = "lcrawfurd"
REPO_NAME    = "indevelopment-podcast"
BASE_URL     = f"https://{GITHUB_USER}.github.io/{REPO_NAME}"
VOICE        = "en-GB-SoniaNeural"   # Change to en-GB-RyanNeural for male
MAX_EPISODES = 50
MAX_CHARS    = 60_000

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def load_processed():
    if PROCESSED.exists():
        return json.loads(PROCESSED.read_text())
    return {}

def save_processed(data):
    PROCESSED.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def x(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def get_html(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text

def get_blog_entries():
    """Scrape the In Development listing for post URLs and titles."""
    html = get_html(BLOG_URL)
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.match(
            r"https?://(?:www\.)?indevelopmentmag\.com/[a-z0-9][a-z0-9-]{4,}/?$", href
        ):
            continue
        if re.search(r"/(category|tag|page|wp-|author)/", href):
            continue
        # Pull title from heading inside the link card
        heading = a.find(["h2", "h3", "h4"])
        title = heading.get_text(strip=True) if heading else a.get_text(strip=True)
        if href not in seen and title and len(title) > 10:
            seen.add(href)
            entries.append({"url": href.rstrip("/"), "title": title})
    return entries

def fetch_article(url):
    """Fetch article body text and authors. Returns (text, authors_str)."""
    try:
        html = get_html(url)
        soup_full = BeautifulSoup(html, "html.parser")

        # Extract authors — try common WordPress selectors
        authors = []
        for sel in [
            "a[rel='author']", ".entry-author", ".author-name",
            ".byline a", ".post-author a", "span.author",
        ]:
            found = [el.get_text(strip=True) for el in soup_full.select(sel)]
            if found:
                authors = found
                break
        # Fallback: "By Name" pattern
        if not authors:
            for tag in soup_full.find_all(string=re.compile(r"^By\s+\w")):
                authors = [str(tag).strip().lstrip("By").strip()]
                break
        authors_str = ", ".join(dict.fromkeys(authors))  # deduplicate, preserve order

        doc = Document(html)
        soup = BeautifulSoup(doc.summary(), "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:MAX_CHARS], authors_str
    except Exception as e:
        print(f"  ✗ fetch failed: {e}")
        return None, ""

async def tts(text, path):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(path))

def make_filename(title):
    date_str = datetime.now().strftime("%Y%m%d")
    slug = re.sub(r"[^\w\s-]", "", title)[:60].strip()
    slug = re.sub(r"\s+", "-", slug).lower()
    return f"{date_str}-{slug}.mp3"

def generate_feed(episodes):
    items = ""
    for ep in sorted(episodes.values(), key=lambda e: e["pub_date"], reverse=True):
        items += f"""
    <item>
      <title>{x(ep['title'] + (' — ' + ep['authors'] if ep.get('authors') else ''))}</title>
      <description>{x(ep.get('summary', ''))}</description>
      <link>{x(ep['url'])}</link>
      <pubDate>{ep['pub_date']}</pubDate>
      <guid isPermaLink="false">{x(ep['url'])}</guid>
      <enclosure url="{BASE_URL}/audio/{ep['filename']}" type="audio/mpeg" length="{ep['size']}"/>
    </item>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>In Development (Audio)</title>
    <description>In Development magazine articles — evidence and argument for a developing world — converted to audio.</description>
    <link>{BLOG_URL}</link>
    <language>en-gb</language>
    <itunes:author>In Development</itunes:author>
    <itunes:category text="Society &amp; Culture"/>
    {items}
  </channel>
</rss>"""

def git_push(new_files, commit_msg):
    os.chdir(BASE_DIR)
    for f in new_files:
        subprocess.run(["git", "add", str(f)], check=True)
    subprocess.run(["git", "add", "processed.json", "feed.xml"], check=True)
    result = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if result.returncode == 0:
        print("Nothing new to commit.")
        return
    subprocess.run(["git", "commit", "-m", commit_msg], check=True)
    subprocess.run(["git", "push"], check=True)


# ── Main ────────────────────────────────────────────────────────────────────

async def main():
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    processed = load_processed()

    print("Fetching In Development listing…")
    entries = get_blog_entries()
    print(f"Found {len(entries)} articles on listing page.")

    new_files = []
    for entry in entries:
        url = entry["url"]
        if url in processed:
            continue

        title = entry["title"]
        print(f"\nProcessing: {title}")

        text, authors = fetch_article(url)
        if not text:
            continue

        by_line = f" by {authors}" if authors else ""
        intro = f"This is an automated reading of an article from In Development magazine: {title}{by_line}."
        outro = "Thank you for listening. For more on global development, visit indevelopmentmag.com."
        full_text = f"{intro} {text} {outro}"
        filename = make_filename(title)
        audio_path = AUDIO_DIR / filename

        try:
            await tts(full_text, audio_path)
            size = audio_path.stat().st_size
            print(f"  ✓ {filename} ({size // 1024} KB)")
        except Exception as e:
            print(f"  ✗ TTS failed: {e}")
            continue

        processed[url] = {
            "title": title,
            "authors": authors,
            "url": url,
            "filename": filename,
            "size": size,
            "pub_date": formatdate(),
            "summary": text[:300],
        }
        save_processed(processed)
        new_files.append(audio_path)

    if not new_files:
        print("\nNo new articles.")
        return

    # Enforce episode cap
    if len(processed) > MAX_EPISODES:
        sorted_eps = sorted(processed.items(), key=lambda kv: kv[1]["pub_date"])
        to_remove = sorted_eps[:len(processed) - MAX_EPISODES]
        for url_key, ep in to_remove:
            old_file = AUDIO_DIR / ep["filename"]
            if old_file.exists():
                old_file.unlink()
                subprocess.run(["git", "rm", "--cached", "-f", str(old_file)],
                               cwd=BASE_DIR, capture_output=True)
            del processed[url_key]
        print(f"Pruned {len(to_remove)} old episode(s).")

    save_processed(processed)
    FEED_FILE.write_text(generate_feed(processed), encoding="utf-8")

    recent = [list(processed.values())[-i]["title"] for i in range(1, min(4, len(new_files)+1))]
    commit_msg = f"Add {len(new_files)} episode(s): {', '.join(t[:35] for t in recent)}"
    git_push(new_files, commit_msg)

    print(f"\nDone. {len(new_files)} new episode(s) pushed.")
    print(f"Subscribe: {BASE_URL}/feed.xml")


if __name__ == "__main__":
    asyncio.run(main())
