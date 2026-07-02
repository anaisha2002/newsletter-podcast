"""
summarize.py
Reads output/raw_emails.json, sends newsletter content to Groq in batches
to avoid hitting rate limits, dedupes overlapping stories, and produces
a structured podcast script.
"""

import os
import json
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
RAW_PATH = "output/raw_emails.json"
JSON_OUTPUT_PATH = "output/script.json"
TEXT_OUTPUT_PATH = "output/script.txt"

# Groq client — one object, reused for every call
client = Groq(api_key=GROQ_API_KEY)

BATCH_PROMPT_TEMPLATE = """You are producing a daily news podcast script from a batch of
newsletter emails (mostly AI and finance topics). Below is the raw content of
{count} emails.

Your job:
1. Identify distinct news stories/topics across all emails. Multiple
   newsletters often cover the SAME story — merge these into a single entry
   instead of repeating it.
2. Discard pure ads, sponsor blurbs, "subscribe now" filler, and anything
   that isn't actual news or insight.
3. Produce a JSON object with exactly this structure:

{{
  "headlines": ["short one-liner headline 1", "short one-liner headline 2", ...],
  "summaries": [
    {{"title": "...", "summary": "2-3 sentence summary in plain conversational language"}}
  ],
  "deep_dives": [
    {{"title": "...", "content": "A fuller, podcast-style spoken paragraph (4-8 sentences), explaining the story, why it matters, and any useful context."}}
  ]
}}

Include 2-3 stories max in deep_dives. Include all distinct stories in summaries.

Respond with ONLY the JSON object, no markdown fences, no commentary.

Here is the raw newsletter content:

{content}
"""

MERGE_PROMPT_TEMPLATE = """You are merging multiple batch summaries into one final podcast script.
Below are {count} batches of summaries. Your job is to:

1. Merge all headlines, removing duplicates or near-duplicates.
2. Merge all summaries, removing duplicate stories (keep the best version of each).
3. Select the 2-4 most significant stories for deep_dives.
4. Return a single JSON object with this structure:

{{
  "date": "YYYY-MM-DD",
  "headlines": ["headline 1", "headline 2", ...],
  "summaries": [
    {{"title": "...", "summary": "..."}}
  ],
  "deep_dives": [
    {{"title": "...", "content": "..."}}
  ]
}}

Here are the batches to merge:

{content}
"""


def build_content_blob(emails):
    """Joins emails into text block with clear separators.
    Caps each email body at 1500 chars to reduce token usage.
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


def process_batch(emails_batch, batch_num):
    """Process a single batch of emails through Groq API."""
    print(f"Processing batch {batch_num} ({len(emails_batch)} emails)...")
    
    content_blob = build_content_blob(emails_batch)
    prompt = BATCH_PROMPT_TEMPLATE.format(count=len(emails_batch), content=content_blob)
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
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
        temperature=0.3,
    )
    
    raw_text = response.choices[0].message.content.strip()
    
    # Defensive: strip markdown code fences if the model adds them
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()
    
    batch_result = json.loads(raw_text)
    print(f"Batch {batch_num} complete: {len(batch_result.get('summaries', []))} summaries")
    return batch_result


def merge_batches(batch_results):
    """Merge all batch results into one final script via Groq."""
    print(f"\nMerging {len(batch_results)} batches into final script...")
    
    # Prepare batch content for merging
    batch_content = json.dumps(batch_results, indent=2)
    prompt = MERGE_PROMPT_TEMPLATE.format(count=len(batch_results), content=batch_content)
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that merges and deduplicates podcast script summaries. You always respond with valid JSON only, no extra text.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.3,
    )
    
    raw_text = response.choices[0].message.content.strip()
    
    # Defensive: strip markdown code fences if the model adds them
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()
    
    final_script = json.loads(raw_text)
    print("Final script merged successfully")
    return final_script


def summarize():
    # --- Read the emails saved by fetch_emails.py ---
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    emails = raw["emails"]
    if not emails:
        print("No emails to summarize. Exiting.")
        return None

    # --- Process emails in batches ---
    batch_size = 10  # Process 10 emails per batch (adjust if needed)
    batch_results = []
    
    for i in range(0, len(emails), batch_size):
        batch = emails[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        try:
            result = process_batch(batch, batch_num)
            batch_results.append(result)
            
            # Add delay between batches to avoid rate limiting
            if i + batch_size < len(emails):
                print("Waiting 2 seconds before next batch...")
                time.sleep(2)
        except Exception as e:
            print(f"Error processing batch {batch_num}: {e}")
            raise

    # --- Merge all batches into final script ---
    if len(batch_results) == 1:
        # Only one batch, use it directly (add date field)
        final_script = batch_results[0]
        from datetime import date
        if "date" not in final_script:
            final_script["date"] = str(date.today())
    else:
        # Multiple batches, merge them
        final_script = merge_batches(batch_results)

    # --- Save outputs ---
    with open(JSON_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(final_script, f, indent=2, ensure_ascii=False)

    plaintext = script_to_plaintext(final_script)
    with open(TEXT_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(plaintext)

    print(f"Saved structured script to {JSON_OUTPUT_PATH}")
    print(f"Saved plaintext script to {TEXT_OUTPUT_PATH}")
    return final_script


if __name__ == "__main__":
    summarize()
