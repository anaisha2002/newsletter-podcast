"""
main.py
Runs the full daily pipeline: fetch emails -> summarize/dedupe -> generate audio.
Run this with: python main.py
"""

import asyncio
from fetch_emails import fetch_newsletters
from summarize import summarize
from tts import generate_audio


def main():
    print("=== Step 1: Fetching newsletters from Gmail ===")
    emails = fetch_newsletters()

    if not emails:
        print("No newsletters found today. Stopping.")
        return

    print("\n=== Step 2: Summarizing and deduplicating with Gemini ===")
    script = summarize()

    if not script:
        print("Summarization failed. Stopping.")
        return

    print("\n=== Step 3: Generating podcast audio ===")
    asyncio.run(generate_audio())

    print("\nDone. Check the output/ folder for script.txt, script.json, and podcast.mp3")


if __name__ == "__main__":
    main()
