"""
main.py
Orchestrates the full daily pipeline:
fetch emails → summarize → generate audio → upload & update RSS feed
"""

import asyncio
import os
from fetch_emails import fetch_newsletters
from summarize import summarize
from tts import generate_audio

def main():
    print("=== Step 1: Fetching newsletters from Gmail ===")
    emails = fetch_newsletters()

    if not emails:
        print("No newsletters found today. Stopping.")
        return

    print("\n=== Step 2: Summarizing and deduplicating with Groq ===")
    script = summarize()

    if not script:
        print("Summarization failed. Stopping.")
        return

    print("\n=== Step 3: Generating podcast audio ===")
    asyncio.run(generate_audio())

    # Only run upload step when running in GitHub Actions (not locally)
    if os.environ.get("GITHUB_ACTIONS"):
        print("\n=== Step 4: Uploading to GitHub Releases and updating RSS feed ===")
        from upload_and_feed import main as upload
        upload()
    else:
        print("\n=== Step 4 skipped (running locally) ===")
        print("Upload step only runs in GitHub Actions.")

    print("\nDone.")

if __name__ == "__main__":
    main()
