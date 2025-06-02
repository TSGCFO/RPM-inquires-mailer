"""
Listener for public.inquiries  ➜  e-mail via Microsoft Graph

psycopg 3 version – no add_listener()

ENV VARS (same as before)
-------------------------
PGHOST, PGDATABASE, PGUSER, PGPASSWORD
TENANT_ID, CLIENT_ID, CLIENT_SECRET
FROM_EMAIL, TO_EMAIL
"""

import os, json, time, requests, psycopg

# ---------- Graph helpers (unchanged) ----------
TENANT_ID, CLIENT_ID  = os.getenv("TENANT_ID"), os.getenv("CLIENT_ID")
CLIENT_SECRET         = os.getenv("CLIENT_SECRET")
FROM_EMAIL, TO_EMAIL  = os.getenv("FROM_EMAIL"), os.getenv("TO_EMAIL")

TOKEN_URL    = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
SENDMAIL_URL = f"https://graph.microsoft.com/v1.0/users/{FROM_EMAIL}/sendMail"

_token = {"value": None, "exp": 0}
def graph_token() -> str:
    if _token["exp"] - time.time() > 60:
        return _token["value"]

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
    _token["value"] = data["access_token"]
    _token["exp"]   = time.time() + int(data.get("expires_in", 3600))
    return _token["value"]

def send_email(body_text: str):
    headers = {
        "Authorization": f"Bearer {graph_token()}",
        "Content-Type": "application/json",
    }
    payload = {
        "message": {
            "subject": "🆕 New inquiry received",
            "body": {"contentType": "Text", "content": body_text},
            "toRecipients": [{"emailAddress": {"address": TO_EMAIL}}],
        },
        "saveToSentItems": "false",
    }
    requests.post(SENDMAIL_URL, headers=headers, json=payload, timeout=15).raise_for_status()

# ---------- Postgres connection & notifier ----------
conn = psycopg.connect(
    host=os.getenv("PGHOST"),
    dbname=os.getenv("PGDATABASE"),
    user=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
)

with conn.cursor() as cur:
    cur.execute("LISTEN new_record_channel;")
conn.commit()

print("🔔 Listening on channel new_record_channel …")

while True:
    conn.poll()                       # check for backend messages
    while conn.notifies:              # handle all pending notifications
        notify = conn.notifies.pop(0)
        try:
            record = json.loads(notify.payload)
            send_email(json.dumps(record, indent=2))
            print("📨 Email sent for inquiry id:", record.get("id"))
        except Exception as e:
            print("⚠️  Failed to send email:", e)
    time.sleep(0.5)                   # small sleep to avoid tight loop
