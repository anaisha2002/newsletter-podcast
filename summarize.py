"""
summarize.py
Reads output/raw_emails.json, sends all newsletter content to Groq (free,
works from India) in one prompt, asks it to dedupe overlapping stories and
produce a structured podcast script (Headlines / Summaries / Deep Dives),
and saves the result as both JSON (structured) and plain text (for TTS).
"""

import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
RAW_PATH = "output/raw_emails.json"
JSON_OUTPUT_PATH = "output/script.json"
TEXT_OUTPUT_PATH = "output/script.txt"

# Groq client — one object, reused for every call
client = Groq(api_key=GROQ_API_KEY)

PROMPT_TEMPLATE = """You are producing a daily news podcast script from a batch of
newsletter emails (mostly AI and finance topics). Below is the raw content of
{count} emails received today.

Your job:
1. Identify distinct news stories/topics across all emails. Multiple
   newsletters often cover the SAME story — merge these into a single entry
   instead of repeating it.
2. Discard pure ads, sponsor blurbs, "subscribe now" filler, and anything
   that isn't actual news or insight.
3. Produce a JSON object with exactly this structure:

{{
  "date": "YYYY-MM-DD",
  "headlines": ["short one-liner headline 1", "short one-liner headline 2", ...],
  "summaries": [
    {{"title": "...", "summary": "2-3 sentence summary in plain conversational language"}}
  ],
  "deep_dives": [
    {{"title": "...", "content": "A fuller, podcast-style spoken paragraph (4-8 sentences), explaining the story, why it matters, and any useful context. Written to be read aloud naturally, not like a bullet list."}}
  ]
}}

Only include 2-4 stories in deep_dives — pick the most significant/interesting
ones. Include all distinct stories in summaries. Headlines should cover
everything in summaries, just condensed to one line each.

Respond with ONLY the JSON object, no markdown fences, no commentary.

Here is today's raw newsletter content:

{content}
"""


def build_content_blob(emails):
    """Joins all emails into one big text block with clear separators.
    We cap each email body at 1500 chars — newsletters front-load their
    actual content; the rest is footers, ads, and unsubscribe links.
    """
    parts = []
    for e in emails:
        truncated_body = e['body'][:1500]
        parts.append(
            f"--- EMAIL ---\nFrom: {e['from']}\nSubject: {e['subject']}\nBody: {truncated_body}\n"
        )
    return "\n".join(parts)


def script_to_plaintext(script):
    """
    Converts the structured JSON script into a flowing spoken script for TTS.
    The AI returns structured data (good for machines); this turns it into
    natural sentences with transitions (good for listening to).
    """
    lines = []
    lines.append(f"Here's your news briefing for {script.get('date', 'today')}.")
    lines.append("")
    lines.append("First, the headlines.")
    for h in script.get("headlines", []):
        lines.append(h)
    lines.append("")
    lines.append("Now let's go through these in a bit more detail.")
    for s in script.get("summaries", []):
        lines.append(f"{s['title']}. {s['summary']}")
    lines.append("")
    if script.get("deep_dives"):
        lines.append("And now, a closer look at today's bigger stories.")
        for d in script.get("deep_dives", []):
            lines.append(f"{d['title']}.")
            lines.append(d["content"])
    lines.append("")
    lines.append("That's all for today. Talk to you tomorrow.")
    return "\n\n".join(lines)


def summarize():
    # --- Read the emails saved by fetch_emails.py ---
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    emails = raw["emails"]
    if not emails:
        print("No emails to summarize. Exiting.")
        return None

    # --- Build the prompt ---
    content_blob = build_content_blob(emails)
    prompt = PROMPT_TEMPLATE.format(count=len(emails), content=content_blob)

    # --- Call Groq API ---
    # Groq uses the OpenAI-style "chat completions" format:
    # messages is a list with roles — "system" sets behaviour,
    # "user" is the actual request. We put everything in "user" for simplicity.
    print(f"Sending {len(emails)} emails to Groq for summarization...")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",   # Groq's best free model
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that produces structured JSON podcast scripts from newsletter emails. You always respond with valid JSON only, no extra text.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.3,   # lower = more consistent, less creative (good for structured tasks)
    )

    # --- Extract and clean the response text ---
    raw_text = response.choices[0].message.content.strip()

    # Defensive: strip markdown code fences if the model adds them
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    # --- Parse JSON and save outputs ---
    script = json.loads(raw_text)

    with open(JSON_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2, ensure_ascii=False)

    plaintext = script_to_plaintext(script)
    with open(TEXT_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(plaintext)

    print(f"Saved structured script to {JSON_OUTPUT_PATH}")
    print(f"Saved plaintext script to {TEXT_OUTPUT_PATH}")
    return script


if __name__ == "__main__":
    summarize()
