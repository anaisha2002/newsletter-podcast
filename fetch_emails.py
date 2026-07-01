"""
fetch_emails.py
Fetches all emails labeled 'Newsletters' received in the last N hours,
extracts subject + plain-text body, and saves them to output/raw_emails.json

First run will open a browser window asking you to log in to Google and
authorize access. After that, token.json is saved and you won't need to
log in again (until the token expires).
"""

import os
import json
import base64
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
LABEL_NAME = "Newsletters"
LOOKBACK_HOURS = 24
OUTPUT_PATH = "output/raw_emails.json"


def get_gmail_service():
    """Handles OAuth login and returns an authenticated Gmail API client."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_label_id(service, label_name):
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"].lower() == label_name.lower():
            return label["id"]
    raise ValueError(
        f"Label '{label_name}' not found. Create it in Gmail first."
    )


def extract_plain_text(payload):
    """Recursively walks the email payload to find the plain-text part."""
    if payload.get("mimeType") == "text/plain" and "data" in payload.get("body", {}):
        data = payload["body"]["data"]
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    if "parts" in payload:
        for part in payload["parts"]:
            text = extract_plain_text(part)
            if text:
                return text

    # fallback: try html part and strip tags crudely if no plain text exists
    if payload.get("mimeType") == "text/html" and "data" in payload.get("body", {}):
        import re
        data = payload["body"]["data"]
        html = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        text = re.sub("<[^<]+?>", " ", html)
        return text

    return ""


def fetch_newsletters():
    service = get_gmail_service()
    label_id = get_label_id(service, LABEL_NAME)

    query = f"newer_than:1d"  # Gmail search syntax; 1d = last 24h
    results = service.users().messages().list(
        userId="me", labelIds=[label_id], q=query, maxResults=100
    ).execute()

    messages = results.get("messages", [])
    print(f"Found {len(messages)} emails labeled '{LABEL_NAME}' in the last 24h.")

    emails = []
    for msg_meta in messages:
        msg = service.users().messages().get(
            userId="me", id=msg_meta["id"], format="full"
        ).execute()

        headers = msg["payload"].get("headers", [])
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(no subject)")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "(unknown sender)")

        body = extract_plain_text(msg["payload"])
        body = " ".join(body.split())  # collapse excess whitespace

        emails.append({
            "id": msg["id"],
            "subject": subject,
            "from": sender,
            "body": body[:8000],  # cap per-email length to keep prompt size sane
        })

    os.makedirs("output", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at": datetime.now().isoformat(),
            "count": len(emails),
            "emails": emails,
        }, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(emails)} emails to {OUTPUT_PATH}")
    return emails


if __name__ == "__main__":
    fetch_newsletters()
