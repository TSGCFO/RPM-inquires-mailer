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

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv is optional, environment variables might be set directly
    pass

# Define required environment variables for both instances
# Support both individual vars and connection strings
INSTANCE_1_VARS = [
    "TENANT_ID", "CLIENT_ID", "CLIENT_SECRET",
    "FROM_EMAIL", "TO_EMAIL",
]

INSTANCE_1_DB_VARS = [
    "PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD"
]

INSTANCE_2_VARS = [
    "TENANT_ID_2", "CLIENT_ID_2", "CLIENT_SECRET_2",
    "FROM_EMAIL_2", "TO_EMAIL_2",
]

INSTANCE_2_DB_VARS = [
    "PGHOST_2", "PGDATABASE_2", "PGUSER_2", "PGPASSWORD_2"
]

@dataclass
class InstanceConfig:
    """Configuration for a single database/email instance."""
    # Database connection (either connection string OR individual components)
    connection_string: Optional[str] = None
    pg_host: Optional[str] = None
    pg_database: Optional[str] = None
    pg_user: Optional[str] = None
    pg_password: Optional[str] = None
    
    # Microsoft Graph
    tenant_id: str = None
    client_id: str = None
    client_secret: str = None
    from_email: str = None
    to_email: str = None
    
    # Instance identification
    instance_name: str = None
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
    
    # Instance 1 database connection (connection string OR individual vars)
    db_url_1 = os.getenv("DATABASE_URL")
    missing_db_1 = [var for var in INSTANCE_1_DB_VARS if not os.getenv(var)]
    
    if not db_url_1 and missing_db_1:
        raise RuntimeError(
            f"Instance 1: Either DATABASE_URL or individual DB vars required: {', '.join(missing_db_1)}"
        )
    
    config_1 = InstanceConfig(
        connection_string=db_url_1,
        pg_host=os.getenv("PGHOST") if not db_url_1 else None,
        pg_database=os.getenv("PGDATABASE") if not db_url_1 else None,
        pg_user=os.getenv("PGUSER") if not db_url_1 else None,
        pg_password=os.getenv("PGPASSWORD") if not db_url_1 else None,
        tenant_id=os.getenv("TENANT_ID"),
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
        from_email=os.getenv("FROM_EMAIL"),
        to_email=os.getenv("TO_EMAIL"),
        instance_name="Instance-1",
        listen_channel="new_record_channel"  # For inquiries table
    )
    configs.append(config_1)
    
    # Check Instance 2 (optional)
    missing_2 = [var for var in INSTANCE_2_VARS if not os.getenv(var)]
    db_url_2 = os.getenv("DATABASE_URL_2")
    missing_db_2 = [var for var in INSTANCE_2_DB_VARS if not os.getenv(var)]
    
    # Instance 2 is optional, but if attempted, needs complete config
    if not missing_2 and (db_url_2 or not missing_db_2):
        config_2 = InstanceConfig(
            connection_string=db_url_2,
            pg_host=os.getenv("PGHOST_2") if not db_url_2 else None,
            pg_database=os.getenv("PGDATABASE_2") if not db_url_2 else None,
            pg_user=os.getenv("PGUSER_2") if not db_url_2 else None,
            pg_password=os.getenv("PGPASSWORD_2") if not db_url_2 else None,
            tenant_id=os.getenv("TENANT_ID_2"),
            client_id=os.getenv("CLIENT_ID_2"),
            client_secret=os.getenv("CLIENT_SECRET_2"),
            from_email=os.getenv("FROM_EMAIL_2"),
            to_email=os.getenv("TO_EMAIL_2"),
            instance_name="Instance-2",
            listen_channel="quote_request_channel"  # Unique channel for quote_requests
        )
        configs.append(config_2)
        print(f"✅ Loaded configuration for {config_2.instance_name}")
    else:
        missing_all = missing_2 + (missing_db_2 if not db_url_2 else [])
        print(f"⚠️  Instance 2 not configured (missing: {', '.join(missing_all)})")
    
    print(f"✅ Loaded configuration for {config_1.instance_name}")
    return configs

# ── Microsoft Graph helpers ──────────────────────────────────────────────

# Token cache: Dict[tenant_id, token_info] with thread safety
_tokens: Dict[str, Dict[str, any]] = {}
_token_lock = threading.Lock()

def graph_token(config: InstanceConfig) -> str:
    """Cache & refresh the app-only access token for a specific tenant (expires in ~1 h)."""
    tenant_id = config.tenant_id
    instance_name = config.instance_name
    
    print(f"🔑 [{instance_name}] Requesting Graph token for tenant: {tenant_id}")
    
    # Thread-safe token cache access
    with _token_lock:
        # Check if we have a valid cached token
        if tenant_id in _tokens:
            token_info = _tokens[tenant_id]
            if token_info["exp"] - time.time() > 60:
                print(f"🔑 [{instance_name}] Using cached token")
                return token_info["val"]
        
        # Need to refresh token - release lock during HTTP request
        print(f"🔑 [{instance_name}] Token expired or missing, requesting new token")
    
    # Request new token (outside lock to avoid blocking other threads during HTTP call)
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    print(f"🔑 [{instance_name}] Token URL: {token_url}")
    
    try:
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
        
        print(f"🔑 [{instance_name}] Token response status: {resp.status_code}")
        
        if resp.status_code == 200:
            body = resp.json()
            print(f"🔑 [{instance_name}] Token acquired successfully")
        else:
            print(f"❌ [{instance_name}] Token request failed: {resp.text}")
            resp.raise_for_status()
            
    except Exception as e:
        print(f"❌ [{instance_name}] Token request exception: {e}")
        raise
    
    # Thread-safe token cache update
    with _token_lock:
        _tokens[tenant_id] = {
            "val": body["access_token"],
            "exp": time.time() + int(body.get("expires_in", 3600))
        }
        print(f"🔑 [{instance_name}] Token cached successfully")
        return _tokens[tenant_id]["val"]

class DatabaseListener:
    """Handles database listening and email sending for a single instance."""
    
    def __init__(self, config: InstanceConfig):
        self.config = config
        self.conn: Optional[psycopg.Connection] = None
    
    def connect(self) -> None:
        """Establish database connection."""
        try:
            if self.config.connection_string:
                # Use connection string
                self.conn = psycopg.connect(
                    self.config.connection_string,
                    autocommit=True,  # LISTEN works best with autocommit
                )
                db_name = self.config.connection_string.split('/')[-1].split('?')[0]
                print(f"🔗 [{self.config.instance_name}] Connected via connection string to database: {db_name}")
            else:
                # Use individual parameters
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
        """Build a clean, plain-text email from an inquiry/quote request and send it."""
        # Determine email type based on available fields
        is_quote_request = 'company' in record and 'service' in record
        
        if is_quote_request:
            subject = "🆕 New Quote Request Received"
            header = "New Quote Request Received"
            
            # Quote request specific fields
            body_lines = [
                f"Name         : {record.get('name', '--')}",
                f"Email        : {record.get('email', '--')}",
                f"Phone        : {record.get('phone') or '--'}",
                f"Company      : {record.get('company', '--')}",
                f"Service      : {record.get('service', '--')}",
                f"Message      : {record.get('message', '--')}",
                f"Consent      : {'Yes' if record.get('consent') else 'No'}",
                f"Current Ships: {record.get('current_shipments') or 'N/A'}",
                f"Expected Ships: {record.get('expected_shipments') or 'N/A'}",
                f"Services     : {record.get('services') or 'N/A'}",
                f"Created At   : {record.get('created_at', '--')}",
                f"Status       : {record.get('status', '--')}",
            ]
        else:
            subject = "🆕 New Inquiry Received"
            header = "New Inquiry Received"
            
            # Standard inquiry fields
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
        
        body_text = f"{header}\n" + "-" * len(header) + "\n" + "\n".join(body_lines)
        
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
            print(f"📧 [{self.config.instance_name}] Sending {subject} to {self.config.to_email}")
            print(f"📧 [{self.config.instance_name}] Using Graph URL: {sendmail_url}")
            
            response = requests.post(sendmail_url, headers=headers, json=payload, timeout=15)
            
            print(f"📧 [{self.config.instance_name}] Email API response status: {response.status_code}")
            
            if response.status_code == 202:
                print(f"📨 [{self.config.instance_name}] Email sent successfully to {self.config.to_email} for record id: {record.get('id')}")
            else:
                print(f"❌ [{self.config.instance_name}] Email API error: {response.text}")
                response.raise_for_status()
                
        except Exception as e:
            print(f"❌ [{self.config.instance_name}] Failed to send email: {e}")
            print(f"❌ [{self.config.instance_name}] Email config - FROM: {self.config.from_email}, TO: {self.config.to_email}")
            raise
    
    def fetch_full_record(self, record_id: str) -> Optional[dict]:
        """Fetch complete record from database using the ID."""
        try:
            # Use a fresh connection for data fetching to avoid LISTEN/NOTIFY interference
            if self.config.connection_string:
                fetch_conn = psycopg.connect(self.config.connection_string, autocommit=True)
            else:
                fetch_conn = psycopg.connect(
                    host=self.config.pg_host,
                    dbname=self.config.pg_database,
                    user=self.config.pg_user,
                    password=self.config.pg_password,
                    autocommit=True
                )
            
            with fetch_conn.cursor() as cur:
                # Determine table name based on instance
                table_name = "quote_requests" if self.config.instance_name == "Instance-2" else "inquiries"
                
                cur.execute(f"SELECT * FROM {table_name} WHERE id = %s", (record_id,))
                row = cur.fetchone()
                if row:
                    # Convert row to dict using column names
                    columns = [desc[0] for desc in cur.description]
                    record = dict(zip(columns, row))
                    
                    print(f"📄 [{self.config.instance_name}] Raw record fetched: name='{record.get('name')}', email='{record.get('email')}'")
                    
                    # For quote_requests, map fields to match email template expectations
                    if table_name == "quote_requests":
                        record = self._normalize_quote_request_fields(record)
                        print(f"📄 [{self.config.instance_name}] Normalized record for email template")
                    
                    fetch_conn.close()
                    return record
                else:
                    print(f"⚠️  [{self.config.instance_name}] Record with ID {record_id} not found in {table_name}")
                    fetch_conn.close()
                    return None
        except Exception as e:
            print(f"❌ [{self.config.instance_name}] Failed to fetch record {record_id}: {e}")
            if 'fetch_conn' in locals():
                fetch_conn.close()
            return None
    
    def _normalize_quote_request_fields(self, record: dict) -> dict:
        """Normalize quote_requests fields to match email template expectations."""
        # Map quote_requests fields to standard inquiry format for email template
        normalized = record.copy()
        
        # Add missing fields with appropriate values
        if 'subject' not in normalized:
            service = record.get('service', 'Quote Request')
            normalized['subject'] = f"Quote Request - {service}"
        
        if 'vehicle_id' not in normalized:
            # For quote requests, we can use service type or company info
            company = record.get('company', '')
            service = record.get('service', '')
            normalized['vehicle_id'] = f"{company} - {service}" if company and service else 'N/A'
        
        return normalized

    def listen_and_process(self) -> None:
        """Listen for new records and send notification emails."""
        # CRITICAL: Create the connection in the worker thread, not the main thread
        # PostgreSQL LISTEN/NOTIFY doesn't work reliably across thread boundaries
        print(f"🔧 [{self.config.instance_name}] Creating database connection in worker thread...")
        self.connect()
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(f"LISTEN {self.config.listen_channel};")
            
            print(f"🔔 [{self.config.instance_name}] Listening on channel {self.config.listen_channel}...")
            
            # Simple notification loop - let psycopg handle the blocking
            print(f"🔄 [{self.config.instance_name}] Starting notification processing loop...")
            
            while True:
                try:
                    # Use the connection's built-in notification iterator
                    for notify in self.conn.notifies():
                        try:
                            print(f"📥 [{self.config.instance_name}] Received notification on {notify.channel}: {notify.payload}")
                            
                            # Parse notification payload (expecting minimal JSON with just ID)
                            notification_data = json.loads(notify.payload)
                            
                            # Handle both new minimal format {"id": "123"} and legacy full record format
                            if "id" in notification_data and len(notification_data) == 1:
                                # New minimal format - fetch full record
                                record_id = notification_data["id"]
                                print(f"📋 [{self.config.instance_name}] Fetching full record for ID: {record_id}")
                                record = self.fetch_full_record(record_id)
                                if record:
                                    print(f"🎯 [{self.config.instance_name}] Record fetched successfully, attempting to send email...")
                                    self.send_email(record)
                                    print(f"✅ [{self.config.instance_name}] Email sending completed for record {record_id}")
                                else:
                                    print(f"⚠️  [{self.config.instance_name}] Skipping notification for missing record {record_id}")
                            else:
                                # Legacy format - use notification data directly
                                print(f"📥 [{self.config.instance_name}] Using legacy notification format")
                                self.send_email(notification_data)
                                
                        except Exception as exc:
                            print(f"⚠️  [{self.config.instance_name}] Failed to handle notification: {exc}")
                            import traceback
                            print(f"⚠️  [{self.config.instance_name}] Exception traceback:")
                            traceback.print_exc()
                            
                except KeyboardInterrupt:
                    print(f"🛑 [{self.config.instance_name}] Listener interrupted")
                    break
                except Exception as e:
                    print(f"⚠️  [{self.config.instance_name}] Notification loop error: {e}")
                    time.sleep(5)  # Pause before retrying
        
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
            # Create a worker function that creates the listener in the thread context
            def worker(cfg=config):
                listener = DatabaseListener(cfg)
                listener.listen_and_process()
                
            future = executor.submit(worker)
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
