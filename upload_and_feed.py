"""
upload_and_feed.py
1. Creates a GitHub Release for today's date
2. Uploads podcast.mp3 as a release asset (permanent public URL)
3. Updates feed.xml with the new episode entry
4. feed.xml gets committed to the repo by the GitHub Actions workflow
   and served publicly via GitHub Pages
"""

import os
import json
import requests
from datetime import datetime, timezone
from email.utils import formatdate
import time

# ── Config (injected from environment variables in GitHub Actions) ──────────
GITHUB_TOKEN = os.environ["RELEASE_TOKEN"]
GITHUB_REPO  = os.environ["GITHUB_REPOSITORY"]   # e.g. "anaisha2002/newsletter-podcast"
PAGES_BASE   = os.environ["PAGES_BASE_URL"]       # e.g. "https://anaisha2002.github.io/newsletter-podcast"

AUDIO_PATH   = "output/podcast.mp3"
SCRIPT_PATH  = "output/script.json"
FEED_PATH    = "feed.xml"

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def create_release(tag: str, title: str) -> dict:
    """Creates a GitHub Release and returns the release object."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
    payload = {
        "tag_name": tag,
        "name": title,
        "body": f"Auto-generated daily podcast — {title}",
        "draft": False,
        "prerelease": False,
    }
    resp = requests.post(url, headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()


def upload_asset(release: dict, file_path: str) -> str:
    """Uploads a file to a GitHub Release and returns its public download URL."""
    upload_url = release["upload_url"].replace("{?name,label}", "")
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        data = f.read()

    headers = {**HEADERS, "Content-Type": "audio/mpeg"}
    resp = requests.post(
        upload_url,
        headers=headers,
        params={"name": filename},
        data=data,
    )
    resp.raise_for_status()
    return resp.json()["browser_download_url"]


def load_script_metadata() -> dict:
    """Reads script.json to get today's date and headline count."""
    try:
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def build_new_item(title: str, mp3_url: str, pub_date: str, file_size: int) -> str:
    """Builds one <item> XML block for today's episode."""
    return f"""    <item>
      <title>{title}</title>
      <enclosure url="{mp3_url}" length="{file_size}" type="audio/mpeg"/>
      <guid isPermaLink="false">{mp3_url}</guid>
      <pubDate>{pub_date}</pubDate>
      <itunes:duration>00:05:00</itunes:duration>
    </item>"""


def update_feed(mp3_url: str, episode_title: str, pub_date: str):
    """Prepends a new episode to feed.xml, creating it if it doesn't exist."""
    file_size = os.path.getsize(AUDIO_PATH)
    new_item  = build_new_item(episode_title, mp3_url, pub_date, file_size)

    feed_url  = f"{PAGES_BASE}/feed.xml"
    image_url = f"{PAGES_BASE}/cover.png"   # optional cover art

    if os.path.exists(FEED_PATH):
        # Insert the new episode just before the closing </channel> tag
        with open(FEED_PATH, "r", encoding="utf-8") as f:
            existing = f.read()
        updated = existing.replace("  </channel>", f"{new_item}\n  </channel>")
    else:
        # First ever run — create the feed from scratch
        updated = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>My Daily Newsletter Briefing</title>
    <description>AI and finance newsletters summarised into a daily podcast.</description>
    <link>{PAGES_BASE}</link>
    <language>en</language>
    <itunes:author>Newsletter Podcast Bot</itunes:author>
    <itunes:category text="Technology"/>
    <image>
      <url>{image_url}</url>
      <title>My Daily Newsletter Briefing</title>
      <link>{PAGES_BASE}</link>
    </image>
{new_item}
  </channel>
</rss>"""

    with open(FEED_PATH, "w", encoding="utf-8") as f:
        f.write(updated)

    print(f"Updated {FEED_PATH} with new episode: {episode_title}")


def main():
    now       = datetime.now(timezone.utc)
    date_str  = now.strftime("%Y-%m-%d")
    tag       = f"episode-{date_str}"
    pub_date  = formatdate(time.mktime(now.timetuple()))

    # Load AI-generated metadata for a richer episode title
    meta      = load_script_metadata()
    headlines = meta.get("headlines", [])
    subtitle  = headlines[0] if headlines else "Daily Briefing"
    title     = f"Briefing {date_str} — {subtitle}"

    print(f"Creating GitHub Release: {tag}")
    release   = create_release(tag, title)

    print("Uploading podcast.mp3...")
    mp3_url   = upload_asset(release, AUDIO_PATH)
    print(f"MP3 public URL: {mp3_url}")

    update_feed(mp3_url, title, pub_date)
    print("Done.")


if __name__ == "__main__":
    main()
