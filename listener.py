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
from concurrent.futures import ThreadPoolExecutor, Future
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

# Token cache: Dict[tenant_id, token_info] with thread safety
_tokens: Dict[str, Dict[str, any]] = {}
_token_lock = threading.Lock()

def graph_token(config: InstanceConfig) -> str:
    """Cache & refresh the app-only access token for a specific tenant (expires in ~1 h)."""
    tenant_id = config.tenant_id
    
    # Thread-safe token cache access
    with _token_lock:
        # Check if we have a valid cached token
        if tenant_id in _tokens:
            token_info = _tokens[tenant_id]
            if token_info["exp"] - time.time() > 60:
                return token_info["val"]
        
        # Need to refresh token - release lock during HTTP request
        pass
    
    # Request new token (outside lock to avoid blocking other threads during HTTP call)
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
    
    # Thread-safe token cache update
    with _token_lock:
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
    
    def fetch_full_record(self, record_id: str) -> Optional[dict]:
        """Fetch complete record from database using the ID."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT * FROM inquiries WHERE id = %s", (record_id,))
                row = cur.fetchone()
                if row:
                    # Convert row to dict using column names
                    columns = [desc[0] for desc in cur.description]
                    return dict(zip(columns, row))
                else:
                    print(f"⚠️  [{self.config.instance_name}] Record with ID {record_id} not found")
                    return None
        except Exception as e:
            print(f"❌ [{self.config.instance_name}] Failed to fetch record {record_id}: {e}")
            return None

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
                    # Parse notification payload (expecting minimal JSON with just ID)
                    notification_data = json.loads(notify.payload)
                    
                    # Handle both new minimal format {"id": "123"} and legacy full record format
                    if "id" in notification_data and len(notification_data) == 1:
                        # New minimal format - fetch full record
                        record_id = notification_data["id"]
                        record = self.fetch_full_record(record_id)
                        if record:
                            self.send_email(record)
                        else:
                            print(f"⚠️  [{self.config.instance_name}] Skipping notification for missing record {record_id}")
                    else:
                        # Legacy format - use notification data directly
                        print(f"📥 [{self.config.instance_name}] Using legacy notification format")
                        self.send_email(notification_data)
                        
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
    """Load configurations and start supervised database listeners."""
    configs = load_instance_configs()
    
    if not configs:
        print("❌ No valid configurations found. Exiting.")
        return
    
    print(f"🚀 Starting {len(configs)} database listener(s) with supervision...")
    
    # Use ThreadPoolExecutor for better thread management
    with ThreadPoolExecutor(max_workers=len(configs), thread_name_prefix="Listener") as executor:
        # Submit all listener tasks
        futures: Dict[str, Future] = {}
        
        for config in configs:
            listener = DatabaseListener(config)
            future = executor.submit(listener.listen_and_process)
            futures[config.instance_name] = future
            print(f"🧵 Started supervised thread for {config.instance_name}")
        
        try:
            # Supervision loop - check for failed threads every 30 seconds
            while True:
                time.sleep(30)
                
                # Check each future for completion/failure
                for instance_name, future in list(futures.items()):
                    if future.done():
                        try:
                            # This will raise any exception that occurred in the thread
                            future.result(timeout=0.1)
                            print(f"⚠️  [{instance_name}] Thread completed unexpectedly")
                        except Exception as e:
                            print(f"💥 [{instance_name}] Thread failed with error: {e}")
                        
                        # Restart the failed listener
                        print(f"🔄 [{instance_name}] Restarting listener thread...")
                        config = next(c for c in configs if c.instance_name == instance_name)
                        listener = DatabaseListener(config)
                        new_future = executor.submit(listener.listen_and_process)
                        futures[instance_name] = new_future
                        print(f"✅ [{instance_name}] Thread restarted successfully")
                        
        except KeyboardInterrupt:
            print("\n🛑 Received interrupt signal. Shutting down...")
            return
        except Exception as e:
            print(f"❌ Unexpected error in supervision loop: {e}")
            return


if __name__ == "__main__":
    main()
