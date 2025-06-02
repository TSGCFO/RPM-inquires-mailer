"""
Background worker
  • LISTEN on channel new_record_channel
  • when a NOTIFY arrives, e-mail the row via Microsoft Graph

Env-vars required (exact names):
  PGHOST, PGDATABASE, PGUSER, PGPASSWORD
  TENANT_ID, CLIENT_ID, CLIENT_SECRET
  FROM_EMAIL, TO_EMAIL
"""

import os, json, time, requests, psycopg

# ── Graph helpers ──────────────────────────────────────────────────────────
TENANT_ID     = os.getenv("TENANT_ID")
CLIENT_ID     = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
FROM_EMAIL    = os.getenv("FROM_EMAIL")
TO_EMAIL      = os.getenv("TO_EMAIL")

TOKEN_URL    = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
SENDMAIL_URL = f"https://graph.microsoft.com/v1.0/users/{FROM_EMAIL}/sendMail"

_token = {"val": None, "exp": 0}
def graph_token() -> str:
    """Cache & refresh Graph access token (expires ~3600 s)."""
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
    data = resp.json()
    _token["val"] = data["access_token"]
    _token["exp"] = time.time() + int(data.get("expires_in", 3600))
    return _token["val"]

def send_email(record: dict):
    """Send a readable e-mail from an inquiry row (dict)."""
    subject = "🆕  New Inquiry Received"

    # Pull out known columns, falling back to “--” if missing
    lines = [
        f"Name        : {record.get('name', '--')}",
        f"Email       : {record.get('email', '--')}",
        f"Phone       : {record.get('phone') or '--'}",
        f"Subject     : {record.get('subject', '--')}",
        f"Message     : {record.get('message', '--')}",
        f"Vehicle ID  : {record.get('vehicle_id') or 'N/A'}",
        f"Created At  : {record.get('created_at', '--')}",
        f"Status      : {record.get('status', '--')}",
    ]
    body_text = "New Inquiry Received\n" + "-" * 25 + "\n" + "\n".join(lines)

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

# ── PostgreSQL LISTEN / NOTIFY ────────────────────────────────────────────
conn = psycopg.connect(               # uses blocking (normal) connection
    host=os.getenv("PGHOST"),
    dbname=os.getenv("PGDATABASE"),
    user=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
    autocommit=True,                  # required for LISTEN to work right
)

with conn.cursor() as cur:
    cur.execute("LISTEN new_record_channel;")

print("🔔  Listening on channel new_record_channel …")

for notify in conn.notifies():        # blocks until a NOTIFY is received 1
    try:
        record = json.loads(notify.payload)
        pretty = json.dumps(record, indent=2)
        send_email(pretty)
        print("📨  Email sent for inquiry id:", record.get("id"))
    except Exception as exc:
        print("⚠️  Failed to handle notification:", exc)