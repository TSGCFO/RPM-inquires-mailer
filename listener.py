"""
Background worker:
  • LISTEN on channels for multiple databases
  • When a NOTIFY arrives, send a readable e-mail via Microsoft Graph
  • Supports multiple database/user pairs running concurrently

Environment variables required (Render → Environment):
  Instance 1: PGHOST, PGDATABASE, PGUSER, PGPASSWORD
              TENANT_ID, CLIENT_ID, CLIENT_SECRET
              FROM_EMAIL, TO_EMAIL
  Instance 2: PGHOST_2, PGDATABASE_2, PGUSER_2, PGPASSWORD_2
              TENANT_ID_2, CLIENT_ID_2, CLIENT_SECRET_2
              FROM_EMAIL_2, TO_EMAIL_2
"""

import os
import json
import time
import threading
from dataclasses import dataclass
from typing import Dict, Optional
import requests
import psycopg

# Define required environment variables for both instances
INSTANCE_1_VARS = [
    "PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD",
    "TENANT_ID", "CLIENT_ID", "CLIENT_SECRET",
    "FROM_EMAIL", "TO_EMAIL",
]

INSTANCE_2_VARS = [
    "PGHOST_2", "PGDATABASE_2", "PGUSER_2", "PGPASSWORD_2",
    "TENANT_ID_2", "CLIENT_ID_2", "CLIENT_SECRET_2",
    "FROM_EMAIL_2", "TO_EMAIL_2",
]

@dataclass
class InstanceConfig:
    """Configuration for a single database/email instance."""
    # Database connection
    pg_host: str
    pg_database: str
    pg_user: str
    pg_password: str
    
    # Microsoft Graph
    tenant_id: str
    client_id: str
    client_secret: str
    from_email: str
    to_email: str
    
    # Instance identification
    instance_name: str
    listen_channel: str = "new_record_channel"

def load_instance_configs() -> list[InstanceConfig]:
    """Load configurations for all available instances."""
    configs = []
    
    # Check Instance 1 (required for backward compatibility)
    missing_1 = [var for var in INSTANCE_1_VARS if not os.getenv(var)]
    if missing_1:
        raise RuntimeError(
            f"Missing required Instance 1 environment variables: {', '.join(missing_1)}"
        )
    
    config_1 = InstanceConfig(
        pg_host=os.getenv("PGHOST"),
        pg_database=os.getenv("PGDATABASE"),
        pg_user=os.getenv("PGUSER"),
        pg_password=os.getenv("PGPASSWORD"),
        tenant_id=os.getenv("TENANT_ID"),
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
        from_email=os.getenv("FROM_EMAIL"),
        to_email=os.getenv("TO_EMAIL"),
        instance_name="Instance-1"
    )
    configs.append(config_1)
    
    # Check Instance 2 (optional)
    missing_2 = [var for var in INSTANCE_2_VARS if not os.getenv(var)]
    if not missing_2:
        config_2 = InstanceConfig(
            pg_host=os.getenv("PGHOST_2"),
            pg_database=os.getenv("PGDATABASE_2"),
            pg_user=os.getenv("PGUSER_2"),
            pg_password=os.getenv("PGPASSWORD_2"),
            tenant_id=os.getenv("TENANT_ID_2"),
            client_id=os.getenv("CLIENT_ID_2"),
            client_secret=os.getenv("CLIENT_SECRET_2"),
            from_email=os.getenv("FROM_EMAIL_2"),
            to_email=os.getenv("TO_EMAIL_2"),
            instance_name="Instance-2"
        )
        configs.append(config_2)
        print(f"✅ Loaded configuration for {config_2.instance_name}")
    else:
        print(f"⚠️  Instance 2 not configured (missing: {', '.join(missing_2)})")
    
    print(f"✅ Loaded configuration for {config_1.instance_name}")
    return configs

# ── Microsoft Graph helpers ──────────────────────────────────────────────

# Token cache: Dict[tenant_id, token_info]
_tokens: Dict[str, Dict[str, any]] = {}

def graph_token(config: InstanceConfig) -> str:
    """Cache & refresh the app-only access token for a specific tenant (expires in ~1 h)."""
    tenant_id = config.tenant_id
    
    # Check if we have a valid cached token
    if tenant_id in _tokens:
        token_info = _tokens[tenant_id]
        if token_info["exp"] - time.time() > 60:
            return token_info["val"]
    
    # Request new token
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    resp = requests.post(
        token_url,
        data={
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    
    # Cache the token
    _tokens[tenant_id] = {
        "val": body["access_token"],
        "exp": time.time() + int(body.get("expires_in", 3600))
    }
    
    return _tokens[tenant_id]["val"]

class DatabaseListener:
    """Handles database listening and email sending for a single instance."""
    
    def __init__(self, config: InstanceConfig):
        self.config = config
        self.conn: Optional[psycopg.Connection] = None
    
    def connect(self) -> None:
        """Establish database connection."""
        try:
            self.conn = psycopg.connect(
                host=self.config.pg_host,
                dbname=self.config.pg_database,
                user=self.config.pg_user,
                password=self.config.pg_password,
                autocommit=True,  # LISTEN works best with autocommit
            )
            print(f"🔗 [{self.config.instance_name}] Connected to database: {self.config.pg_database}")
        except Exception as e:
            print(f"❌ [{self.config.instance_name}] Failed to connect to database: {e}")
            raise
    
    def send_email(self, record: dict) -> None:
        """Build a clean, plain-text email from an inquiry row and send it."""
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
        
        sendmail_url = f"https://graph.microsoft.com/v1.0/users/{self.config.from_email}/sendMail"
        headers = {
            "Authorization": f"Bearer {graph_token(self.config)}",
            "Content-Type": "application/json",
        }
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body_text},
                "toRecipients": [{"emailAddress": {"address": self.config.to_email}}],
            },
            "saveToSentItems": "false",
        }
        
        try:
            requests.post(sendmail_url, headers=headers, json=payload, timeout=15).raise_for_status()
            print(f"📨 [{self.config.instance_name}] Email sent to {self.config.to_email} for inquiry id: {record.get('id')}")
        except Exception as e:
            print(f"❌ [{self.config.instance_name}] Failed to send email: {e}")
            raise
    
    def listen_and_process(self) -> None:
        """Listen for new records and send notification emails."""
        if not self.conn:
            self.connect()
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(f"LISTEN {self.config.listen_channel};")
            
            print(f"🔔 [{self.config.instance_name}] Listening on channel {self.config.listen_channel}...")
            
            for notify in self.conn.notifies():  # blocks until a NOTIFY is received
                try:
                    record = json.loads(notify.payload)
                    self.send_email(record)
                except Exception as exc:
                    print(f"⚠️  [{self.config.instance_name}] Failed to handle notification: {exc}")
        
        except Exception as e:
            print(f"❌ [{self.config.instance_name}] Database listening failed: {e}")
            # Try to reconnect after a delay
            print(f"🔄 [{self.config.instance_name}] Attempting to reconnect in 5 seconds...")
            time.sleep(5)
            try:
                self.connect()
                self.listen_and_process()
            except Exception as reconnect_error:
                print(f"💥 [{self.config.instance_name}] Failed to reconnect: {reconnect_error}")
                print(f"⏸️  [{self.config.instance_name}] Listener stopped.")
                return

# ── Main entry point ─────────────────────────────────────────────────────

def main() -> None:
    """Load configurations and start multiple database listeners concurrently."""
    configs = load_instance_configs()
    
    if not configs:
        print("❌ No valid configurations found. Exiting.")
        return
    
    print(f"🚀 Starting {len(configs)} database listener(s)...")
    
    threads = []
    
    # Create and start a thread for each configuration
    for config in configs:
        listener = DatabaseListener(config)
        thread = threading.Thread(
            target=listener.listen_and_process,
            name=f"Listener-{config.instance_name}",
            daemon=True  # Allows main process to exit cleanly
        )
        threads.append(thread)
        thread.start()
        print(f"🧵 Started thread for {config.instance_name}")
    
    try:
        # Wait for all threads to complete (they shouldn't under normal operation)
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("\n🛑 Received interrupt signal. Shutting down...")
        return
    except Exception as e:
        print(f"❌ Unexpected error in main thread: {e}")
        return


if __name__ == "__main__":
    main()
