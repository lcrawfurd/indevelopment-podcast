# In Development Magazine — Audio Podcast

Automatically converts [In Development](https://www.indevelopmentmag.com) articles into an MP3 podcast feed.

**Subscribe in Pocket Casts (or any podcast app that supports custom RSS feeds):**
```
https://lcrawfurd.github.io/indevelopment-podcast/feed.xml
```

### Which apps work?

| App | Custom RSS? | How to add |
|-----|------------|------------|
| **Pocket Casts** ✓ | Yes | Tap Discover → paste URL in search bar → Subscribe |
| **Overcast** ✓ | Yes | Add Feed → paste URL |
| **AntennaPod** ✓ | Yes | Add Podcast → paste URL |
| **Podcast Addict** ✓ | Yes | Add → RSS feed → paste URL |
| **Apple Podcasts** ✗ | No | Requires submission |
| **Spotify** ✗ | No | Requires submission |

## How it works

1. A daily cron job runs `indevelopment_podcast.py`
2. New articles are fetched from indevelopmentmag.com and converted to MP3 using Microsoft Edge TTS (`en-GB-SoniaNeural` voice)
3. Audio files and an RSS feed are committed and pushed to GitHub Pages

## Setup

```bash
pip install edge-tts requests beautifulsoup4 readability-lxml
```

### Running manually

```bash
python3 indevelopment_podcast.py
```

### Scheduling (macOS LaunchAgent)

Add a LaunchAgent (see CGD podcast repo for template) pointing at this script, running daily.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VOICE` | `en-GB-SoniaNeural` | TTS voice |
| `MAX_EPISODES` | 50 | Maximum episodes kept in the feed |
| `MAX_CHARS` | 60,000 | Maximum characters per article sent to TTS |
