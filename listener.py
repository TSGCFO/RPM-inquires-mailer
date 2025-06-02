"""
Background listener for public.inquiries → email alert.

Environment variables required (Render → Environment tab):
  PGHOST            database host (e.g. dpg-xxxxx)
  PGDATABASE        rpm_auto
  PGUSER            rpm_auto_user
  PGPASSWORD        <database password>

  TENANT_ID         5e0201b4-03ba-41c2-bc2e-9fc2475a202d
  CLIENT_ID         6df2862f-dba2-4302-b11b-fdab0a0d2485
  CLIENT_SECRET     <client secret value>

  FROM_EMAIL        fateh@rpmautosales.ca
  TO_EMAIL          info@rpmautosales.ca
"""

import os, json, time, requests, psycopg

# --- Graph helpers -----------------------------------------------------------
TENANT_ID      = os.getenv("TENANT_ID")
CLIENT_ID      = os.getenv("CLIENT_ID")
CLIENT_SECRET  = os.getenv("CLIENT_SECRET")
FROM_EMAIL     = os.getenv("FROM_EMAIL")
TO_EMAIL       = os.getenv("TO_EMAIL")

TOKEN_URL    = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
SENDMAIL_URL = f"https://graph.microsoft.com/v1.0/users/{FROM_EMAIL}/sendMail"

_token_cache = {"access_token": None, "expires_at": 0}

def get_access_token() -> str:
    """Fetch a new token if the current one expires in < 60 seconds."""
    if _token_cache["access_token"] and _token_cache["expires_at"] - time.time() > 60:
        return _token_cache["access_token"]

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    resp = requests.post(TOKEN_URL, data=data, timeout=15)
    resp.raise_for_status()
    body = resp.json()
    _token_cache["access_token"] = body["access_token"]
    _token_cache["expires_at"]   = time.time() + int(body.get("expires_in", 3600))
    return _token_cache["access_token"]

def send_email(body_text: str):
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": {
            "subject": "New inquiry received",
            "body": { "contentType": "Text", "content": body_text },
            "toRecipients": [ { "emailAddress": { "address": TO_EMAIL } } ]
        },
        "saveToSentItems": "false"
    }
    resp = requests.post(SENDMAIL_URL, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()

# --- PostgreSQL listener ------------------------------------------------------
DB_CONN = psycopg.connect(
    host     = os.getenv("PGHOST"),
    dbname   = os.getenv("PGDATABASE"),
    user     = os.getenv("PGUSER"),
    password = os.getenv("PGPASSWORD"),
)

def on_notify(conn, pid, channel, payload):
    try:
        record = json.loads(payload)
        pretty = json.dumps(record, indent=2)
        send_email(pretty)
        print("Sent email for inquiry id:", record.get("id"))
    except Exception as e:
        print("Failed to send email:", e)

print("Listening on channel new_record_channel …")
DB_CONN.add_listener("new_record_channel", on_notify)

while True:
    DB_CONN.poll()
    DB_CONN.commit()
