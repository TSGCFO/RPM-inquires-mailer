"""
Background worker:
  • LISTEN on channel new_record_channel
  • When a NOTIFY arrives, send a readable e-mail via Microsoft Graph

Environment variables required (Render → Environment):
  PGHOST,  PGDATABASE,  PGUSER,  PGPASSWORD
  PGHOST2, PGDATABASE2, PGUSER2, PGPASSWORD2  # database/user #2
  TENANT_ID, CLIENT_ID, CLIENT_SECRET
  FROM_EMAIL,  TO_EMAIL
  FROM_EMAIL2, TO_EMAIL2  # e-mail account #2
"""

import os
import json
import time
import requests
import psycopg
from threading import Thread

# Verify that all required environment variables are present
REQUIRED_ENV_VARS = [
    "PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD",  # database/user #1
    "PGHOST2", "PGDATABASE2", "PGUSER2", "PGPASSWORD2",  # database/user #2
    "TENANT_ID", "CLIENT_ID", "CLIENT_SECRET",
    "FROM_EMAIL", "TO_EMAIL",         # email account #1
    "FROM_EMAIL2", "TO_EMAIL2",       # email account #2
]

missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    raise RuntimeError(
        "Missing required environment variables: " + ", ".join(missing_vars)
    )

# ── Microsoft Graph helpers ──────────────────────────────────────────────
TENANT_ID     = os.getenv("TENANT_ID")
CLIENT_ID     = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
FROM_EMAIL    = os.getenv("FROM_EMAIL")      # fateh@rpmautosales.ca
TO_EMAIL      = os.getenv("TO_EMAIL")        # info@rpmautosales.ca

# second e-mail account / database
FROM_EMAIL2   = os.getenv("FROM_EMAIL2")
TO_EMAIL2     = os.getenv("TO_EMAIL2")
PGHOST2       = os.getenv("PGHOST2")
PGDATABASE2   = os.getenv("PGDATABASE2")
PGUSER2       = os.getenv("PGUSER2")
PGPASSWORD2   = os.getenv("PGPASSWORD2")

TOKEN_URL    = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

_token = {"val": None, "exp": 0}

def graph_token() -> str:
    """Cache & refresh the app-only access token (expires in ~1 h)."""
    if _token["exp"] - time.time() > 60:
        return _token["val"]

    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    _token["val"] = body["access_token"]
    _token["exp"] = time.time() + int(body.get("expires_in", 3600))
    return _token["val"]

def send_email(record: dict, from_email: str, to_email: str) -> None:
    """Build a clean, plain-text e-mail from an inquiry row and send it."""
    subject = "🆕 New Inquiry Received"

    # tidy up values; None -> '--' or 'N/A'
    body_lines = [
        f"Name        : {record.get('name', '--')}",
        f"Email       : {record.get('email', '--')}",
        f"Phone       : {record.get('phone') or '--'}",
        f"Subject     : {record.get('subject', '--')}",
        f"Message     : {record.get('message', '--')}",
        f"Vehicle ID  : {record.get('vehicle_id') or 'N/A'}",
        f"Created At  : {record.get('created_at', '--')}",
        f"Status      : {record.get('status', '--')}",
    ]
    body_text = "New Inquiry Received\n" + "-" * 25 + "\n" + "\n".join(body_lines)

    headers = {
        "Authorization": f"Bearer {graph_token()}",
        "Content-Type": "application/json",
    }
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body_text},
            "toRecipients": [{"emailAddress": {"address": to_email}}],
        },
        "saveToSentItems": "false",
    }
    sendmail_url = f"https://graph.microsoft.com/v1.0/users/{from_email}/sendMail"
    requests.post(sendmail_url, headers=headers, json=payload, timeout=15).raise_for_status()

# ── PostgreSQL LISTEN / NOTIFY setup ─────────────────────────────────────

def listen_for_db(config: dict, from_email: str, to_email: str) -> None:
    """Connect to the DB and process notifications."""
    conn = psycopg.connect(
        host=config["host"],
        dbname=config["dbname"],
        user=config["user"],
        password=config["password"],
        autocommit=True,
    )

    with conn.cursor() as cur:
        cur.execute("LISTEN new_record_channel;")

    print("🔔  Listening on channel new_record_channel …")

    for notify in conn.notifies():
        try:
            record = json.loads(notify.payload)
            send_email(record, from_email, to_email)
            print("📨  Email sent for inquiry id:", record.get("id"))
        except Exception as exc:
            print("⚠️  Failed to handle notification:", exc)


def main() -> None:
    """Start listeners for both databases."""
    config1 = {
        "host": os.getenv("PGHOST"),
        "dbname": os.getenv("PGDATABASE"),
        "user": os.getenv("PGUSER"),
        "password": os.getenv("PGPASSWORD"),
    }
    config2 = {
        "host": PGHOST2,
        "dbname": PGDATABASE2,
        "user": PGUSER2,
        "password": PGPASSWORD2,
    }

    t1 = Thread(target=listen_for_db, args=(config1, FROM_EMAIL, TO_EMAIL))
    t2 = Thread(target=listen_for_db, args=(config2, FROM_EMAIL2, TO_EMAIL2))
    t1.start()
    t2.start()
    t1.join()
    t2.join()


if __name__ == "__main__":
    main()
