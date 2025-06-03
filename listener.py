"""
Background worker:
  • LISTEN on channel new_record_channel
  • When a NOTIFY arrives, send a readable e-mail via Microsoft Graph

Environment variables required (Render → Environment):
  PGHOST, PGDATABASE, PGUSER, PGPASSWORD
  TENANT_ID, CLIENT_ID, CLIENT_SECRET
  FROM_EMAIL, TO_EMAIL
"""

import os, json, time, requests, psycopg

# ── Microsoft Graph helpers ──────────────────────────────────────────────
TENANT_ID     = os.getenv("TENANT_ID")
CLIENT_ID     = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
FROM_EMAIL    = os.getenv("FROM_EMAIL")     # fateh@rpmautosales.ca
TO_EMAIL      = os.getenv("TO_EMAIL")       # info@rpmautosales.ca

TOKEN_URL    = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
SENDMAIL_URL = f"https://graph.microsoft.com/v1.0/users/{FROM_EMAIL}/sendMail"

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

def send_email(record: dict):
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
            "toRecipients": [{"emailAddress": {"address": TO_EMAIL}}],
        },
        "saveToSentItems": "false",
    }
    requests.post(SENDMAIL_URL, headers=headers, json=payload, timeout=15).raise_for_status()

# ── PostgreSQL LISTEN / NOTIFY setup ─────────────────────────────────────
def main() -> None:
    """Listen for new records and send notification e-mails."""
    conn = psycopg.connect(
        host=os.getenv("PGHOST"),
        dbname=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        autocommit=True,  # LISTEN works best with autocommit
    )

    with conn.cursor() as cur:
        cur.execute("LISTEN new_record_channel;")

    print("🔔  Listening on channel new_record_channel …")

    for notify in conn.notifies():  # blocks until a NOTIFY is received
        try:
            record = json.loads(notify.payload)
            send_email(record)
            print("📨  Email sent for inquiry id:", record.get("id"))
        except Exception as exc:
            print("⚠️  Failed to handle notification:", exc)


if __name__ == "__main__":
    main()
