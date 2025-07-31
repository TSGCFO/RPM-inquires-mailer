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
  Instance 3: PGHOST_3, PGDATABASE_3, PGUSER_3, PGPASSWORD_3
              TENANT_ID_3, CLIENT_ID_3, CLIENT_SECRET_3
              FROM_EMAIL_3, TO_EMAIL_3
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

INSTANCE_3_VARS = [
    "TENANT_ID_3", "CLIENT_ID_3", "CLIENT_SECRET_3",
    "FROM_EMAIL_3", "TO_EMAIL_3",
]

INSTANCE_3_DB_VARS = [
    "PGHOST_3", "PGDATABASE_3", "PGUSER_3", "PGPASSWORD_3"
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
        print(f"[OK] Loaded configuration for {config_2.instance_name}")
    else:
        missing_all = missing_2 + (missing_db_2 if not db_url_2 else [])
        print(f"[WARN] Instance 2 not configured (missing: {', '.join(missing_all)})")
    
    # Check Instance 3 (optional)
    missing_3 = [var for var in INSTANCE_3_VARS if not os.getenv(var)]
    db_url_3 = os.getenv("DATABASE_URL_3")
    missing_db_3 = [var for var in INSTANCE_3_DB_VARS if not os.getenv(var)]
    
    # Instance 3 is optional, but if attempted, needs complete config
    if not missing_3 and (db_url_3 or not missing_db_3):
        config_3 = InstanceConfig(
            connection_string=db_url_3,
            pg_host=os.getenv("PGHOST_3") if not db_url_3 else None,
            pg_database=os.getenv("PGDATABASE_3") if not db_url_3 else None,
            pg_user=os.getenv("PGUSER_3") if not db_url_3 else None,
            pg_password=os.getenv("PGPASSWORD_3") if not db_url_3 else None,
            tenant_id=os.getenv("TENANT_ID_3"),
            client_id=os.getenv("CLIENT_ID_3"),
            client_secret=os.getenv("CLIENT_SECRET_3"),
            from_email=os.getenv("FROM_EMAIL_3"),
            to_email=os.getenv("TO_EMAIL_3"),
            instance_name="Instance-3",
            listen_channel="contact_submission_channel"  # Unique channel for contact_submissions
        )
        configs.append(config_3)
        print(f"[OK] Loaded configuration for {config_3.instance_name}")
    else:
        missing_all_3 = missing_3 + (missing_db_3 if not db_url_3 else [])
        print(f"[WARN] Instance 3 not configured (missing: {', '.join(missing_all_3)})")
    
    print(f"[OK] Loaded configuration for {config_1.instance_name}")
    return configs

# ── Microsoft Graph helpers ──────────────────────────────────────────────

# Token cache: Dict[tenant_id, token_info] with thread safety
_tokens: Dict[str, Dict[str, any]] = {}
_token_lock = threading.Lock()

def graph_token(config: InstanceConfig) -> str:
    """Cache & refresh the app-only access token for a specific tenant (expires in ~1 h)."""
    tenant_id = config.tenant_id
    instance_name = config.instance_name
    
    print(f"[TOKEN] [{instance_name}] Requesting Graph token for tenant: {tenant_id}")
    
    # Thread-safe token cache access
    with _token_lock:
        # Check if we have a valid cached token
        if tenant_id in _tokens:
            token_info = _tokens[tenant_id]
            if token_info["exp"] - time.time() > 60:
                print(f"[TOKEN] [{instance_name}] Using cached token")
                return token_info["val"]
        
        # Need to refresh token - release lock during HTTP request
        print(f"[TOKEN] [{instance_name}] Token expired or missing, requesting new token")
    
    # Request new token (outside lock to avoid blocking other threads during HTTP call)
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    print(f"[TOKEN] [{instance_name}] Token URL: {token_url}")
    
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
        
        print(f"[TOKEN] [{instance_name}] Token response status: {resp.status_code}")
        
        if resp.status_code == 200:
            body = resp.json()
            print(f"[TOKEN] [{instance_name}] Token acquired successfully")
        else:
            print(f"[ERROR] [{instance_name}] Token request failed: {resp.text}")
            resp.raise_for_status()
            
    except Exception as e:
        print(f"[ERROR] [{instance_name}] Token request exception: {e}")
        raise
    
    # Thread-safe token cache update
    with _token_lock:
        _tokens[tenant_id] = {
            "val": body["access_token"],
            "exp": time.time() + int(body.get("expires_in", 3600))
        }
        print(f"[TOKEN] [{instance_name}] Token cached successfully")
        return _tokens[tenant_id]["val"]

class DatabaseListener:
    """Handles database listening and email sending for a single instance."""
    
    def __init__(self, config: InstanceConfig):
        self.config = config
        self.conn: Optional[psycopg.Connection] = None
    
    def connect(self) -> None:
        """Establish database connection with SSL and timeout settings."""
        try:
            connection_params = {
                "autocommit": True,  # LISTEN works best with autocommit
                "connect_timeout": 30,  # 30 second connection timeout
                "keepalives_idle": 30,  # Send keepalive after 30 seconds of inactivity
                "keepalives_interval": 10,  # Send keepalive every 10 seconds
                "keepalives_count": 3,  # Give up after 3 failed keepalives
            }
            
            if self.config.connection_string:
                # Check if this is a Neon database (needs special SSL handling)
                if "neon.tech" in self.config.connection_string:
                    print(f"[SETUP] [{self.config.instance_name}] Detected Neon database, applying SSL optimizations...")
                    # Add SSL-specific parameters for Neon
                    connection_params.update({
                        "sslmode": "require",
                        "application_name": f"rpm-mailer-{self.config.instance_name.lower()}",
                    })
                
                # Use connection string with additional parameters
                self.conn = psycopg.connect(
                    self.config.connection_string,
                    **connection_params
                )
                db_name = self.config.connection_string.split('/')[-1].split('?')[0]
                print(f"[CONN] [{self.config.instance_name}] Connected via connection string to database: {db_name}")
            else:
                # Use individual parameters
                connection_params.update({
                    "host": self.config.pg_host,
                    "dbname": self.config.pg_database,
                    "user": self.config.pg_user,
                    "password": self.config.pg_password,
                })
                
                # Check if this is a Neon database
                if self.config.pg_host and "neon.tech" in self.config.pg_host:
                    print(f"[SETUP] [{self.config.instance_name}] Detected Neon database, applying SSL optimizations...")
                    connection_params.update({
                        "sslmode": "require",
                        "application_name": f"rpm-mailer-{self.config.instance_name.lower()}",
                    })
                
                self.conn = psycopg.connect(**connection_params)
                print(f"[CONN] [{self.config.instance_name}] Connected to database: {self.config.pg_database}")
                
            # Test the connection immediately
            with self.conn.cursor() as cur:
                cur.execute("SELECT version()")
                version = cur.fetchone()[0]
                print(f"[CONN] [{self.config.instance_name}] Database version: {version[:50]}...")
                
        except Exception as e:
            print(f"[ERROR] [{self.config.instance_name}] Failed to connect to database: {e}")
            raise
    
    def send_email(self, record: dict) -> None:
        """Build a clean, plain-text email from an inquiry/quote request/contact submission and send it."""
        # Determine email type based on available fields
        is_quote_request = 'company' in record and 'service' in record
        is_contact_submission = 'inquiry_type' in record and ('first_name' in record or 'last_name' in record)
        
        if is_contact_submission:
            subject = "🆕 New Contact Submission Received"
            header = "New Contact Submission Received"
            
            # Normalize contact submission fields for display
            normalized_record = self._normalize_contact_submission_fields(record)
            
            # Contact submission specific fields
            body_lines = [
                f"Name         : {normalized_record.get('name', '--')}",
                f"Email        : {normalized_record.get('email', '--')}",
                f"Phone        : {normalized_record.get('phone') or '--'}",
                f"Inquiry Type : {normalized_record.get('inquiry_type', '--')}",
                f"Message      : {normalized_record.get('message', '--')}",
                f"Created At   : {normalized_record.get('created_at', '--')}",
            ]
        elif is_quote_request:
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
            print(f"[EMAIL] [{self.config.instance_name}] Sending {subject} to {self.config.to_email}")
            print(f"[EMAIL] [{self.config.instance_name}] Using Graph URL: {sendmail_url}")
            
            response = requests.post(sendmail_url, headers=headers, json=payload, timeout=15)
            
            print(f"[EMAIL] [{self.config.instance_name}] Email API response status: {response.status_code}")
            
            if response.status_code == 202:
                print(f"[SENT] [{self.config.instance_name}] Email sent successfully to {self.config.to_email} for record id: {record.get('id')}")
            else:
                print(f"[ERROR] [{self.config.instance_name}] Email API error: {response.text}")
                response.raise_for_status()
                
        except Exception as e:
            print(f"[ERROR] [{self.config.instance_name}] Failed to send email: {e}")
            print(f"[ERROR] [{self.config.instance_name}] Email config - FROM: {self.config.from_email}, TO: {self.config.to_email}")
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
                if self.config.instance_name == "Instance-2":
                    table_name = "quote_requests"
                elif self.config.instance_name == "Instance-3":
                    table_name = "contact_submissions"
                else:
                    table_name = "inquiries"
                
                cur.execute(f"SELECT * FROM {table_name} WHERE id = %s", (record_id,))
                row = cur.fetchone()
                if row:
                    # Convert row to dict using column names
                    columns = [desc[0] for desc in cur.description]
                    record = dict(zip(columns, row))
                    
                    print(f"[DATA] [{self.config.instance_name}] Raw record fetched: name='{record.get('name')}', email='{record.get('email')}'")
                    
                    # Normalize fields based on table type
                    if table_name == "quote_requests":
                        record = self._normalize_quote_request_fields(record)
                        print(f"[DATA] [{self.config.instance_name}] Normalized quote_requests record for email template")
                    elif table_name == "contact_submissions":
                        record = self._normalize_contact_submission_fields(record)
                        print(f"[DATA] [{self.config.instance_name}] Normalized contact_submissions record for email template")
                    
                    fetch_conn.close()
                    return record
                else:
                    print(f"[WARN]  [{self.config.instance_name}] Record with ID {record_id} not found in {table_name}")
                    fetch_conn.close()
                    return None
        except Exception as e:
            print(f"[ERROR] [{self.config.instance_name}] Failed to fetch record {record_id}: {e}")
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

    def _normalize_contact_submission_fields(self, record: dict) -> dict:
        """Normalize contact_submissions fields to match email template expectations."""
        normalized = record.copy()
        
        # Map contact_submissions fields to standard inquiry format
        # contact_submissions has: first_name, last_name, email, phone, inquiry_type, message, created_at
        
        # Combine first_name and last_name into name if they exist separately
        if 'first_name' in record and 'last_name' in record:
            normalized['name'] = f"{record.get('first_name', '')} {record.get('last_name', '')}".strip()
        elif 'first_name' in record:
            normalized['name'] = record.get('first_name', '')
        elif 'last_name' in record:
            normalized['name'] = record.get('last_name', '')
        
        # Use inquiry_type as subject if available
        if 'inquiry_type' in record:
            normalized['subject'] = f"Contact Inquiry - {record.get('inquiry_type', 'General')}"
        else:
            normalized['subject'] = 'Contact Inquiry'
        
        # For contact submissions, vehicle_id is not relevant, use inquiry_type instead
        if 'inquiry_type' in record:
            normalized['vehicle_id'] = record.get('inquiry_type', 'N/A')
        else:
            normalized['vehicle_id'] = 'Contact Submission'
            
        return normalized

    def listen_and_process(self) -> None:
        """Listen for new records and send notification emails with robust reconnection."""
        max_reconnect_attempts = 3
        reconnect_delay = 10  # Start with 10 seconds
        
        while True:
            reconnect_attempts = 0
            
            try:
                # CRITICAL: Create the connection in the worker thread, not the main thread
                print(f"[SETUP] [{self.config.instance_name}] Creating database connection in worker thread...")
                self.connect()
                
                with self.conn.cursor() as cur:
                    cur.execute(f"LISTEN {self.config.listen_channel};")
                
                print(f"[LISTEN] [{self.config.instance_name}] Listening on channel {self.config.listen_channel}...")
                print(f"[LOOP] [{self.config.instance_name}] Starting notification processing loop...")
                
                # Reset reconnection state on successful connection
                reconnect_attempts = 0
                reconnect_delay = 10
                
                # Main notification processing loop
                while True:
                    try:
                        # Use the connection's built-in notification iterator with timeout
                        self.conn.timeout = 30  # 30 second timeout to detect connection issues
                        
                        for notify in self.conn.notifies():
                            try:
                                print(f"[RECV] [{self.config.instance_name}] Received notification on {notify.channel}: {notify.payload}")
                                
                                # Parse notification payload (expecting minimal JSON with just ID)
                                notification_data = json.loads(notify.payload)
                                
                                # Handle both new minimal format {"id": "123"} and legacy full record format
                                if "id" in notification_data and len(notification_data) == 1:
                                    # New minimal format - fetch full record
                                    record_id = notification_data["id"]
                                    print(f"[FETCH] [{self.config.instance_name}] Fetching full record for ID: {record_id}")
                                    record = self.fetch_full_record(record_id)
                                    if record:
                                        print(f"[SUCCESS] [{self.config.instance_name}] Record fetched successfully, attempting to send email...")
                                        self.send_email(record)
                                        print(f"[OK] [{self.config.instance_name}] Email sending completed for record {record_id}")
                                    else:
                                        print(f"[WARN]  [{self.config.instance_name}] Skipping notification for missing record {record_id}")
                                else:
                                    # Legacy format - use notification data directly
                                    print(f"[RECV] [{self.config.instance_name}] Using legacy notification format")
                                    self.send_email(notification_data)
                                    
                            except Exception as exc:
                                print(f"[WARN]  [{self.config.instance_name}] Failed to handle notification: {exc}")
                                import traceback
                                print(f"[WARN]  [{self.config.instance_name}] Exception traceback:")
                                traceback.print_exc()
                        
                        # Heartbeat check - send a simple query to keep connection alive
                        if hasattr(self.conn, 'cursor'):
                            try:
                                with self.conn.cursor() as cur:
                                    cur.execute("SELECT 1")
                                    cur.fetchone()
                            except Exception as heartbeat_error:
                                print(f"[WARN] [{self.config.instance_name}] Heartbeat failed: {heartbeat_error}")
                                raise heartbeat_error  # Trigger reconnection
                                
                    except KeyboardInterrupt:
                        print(f"[STOP] [{self.config.instance_name}] Listener interrupted")
                        return
                    except Exception as e:
                        error_msg = str(e).lower()
                        # Check for connection-related errors
                        if any(keyword in error_msg for keyword in ['ssl', 'connection', 'closed', 'lost', 'timeout']):
                            print(f"[WARN] [{self.config.instance_name}] Connection error detected: {e}")
                            raise e  # Trigger reconnection logic
                        else:
                            print(f"[WARN] [{self.config.instance_name}] Non-connection error: {e}")
                            time.sleep(5)  # Short pause for non-connection errors
                            
            except KeyboardInterrupt:
                print(f"[STOP] [{self.config.instance_name}] Listener interrupted")
                return
            except Exception as e:
                reconnect_attempts += 1
                print(f"[ERROR] [{self.config.instance_name}] Database connection failed (attempt {reconnect_attempts}/{max_reconnect_attempts}): {e}")
                
                # Close any existing connection
                if self.conn:
                    try:
                        self.conn.close()
                    except:
                        pass
                    self.conn = None
                
                if reconnect_attempts >= max_reconnect_attempts:
                    print(f"[FAIL] [{self.config.instance_name}] Max reconnection attempts reached. Waiting {reconnect_delay} seconds before retry cycle...")
                    time.sleep(reconnect_delay)
                    reconnect_attempts = 0  # Reset for next cycle
                    reconnect_delay = min(reconnect_delay * 1.5, 60)  # Exponential backoff, max 60s
                else:
                    print(f"[LOOP] [{self.config.instance_name}] Attempting to reconnect in {reconnect_delay} seconds...")
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay + 5, 30)  # Gradual increase, max 30s

# ── Main entry point ─────────────────────────────────────────────────────

def main() -> None:
    """Load configurations and start supervised database listeners."""
    configs = load_instance_configs()
    
    if not configs:
        print("[ERROR] No valid configurations found. Exiting.")
        return
    
    print(f"[START] Starting {len(configs)} database listener(s) with supervision...")
    
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
            print(f"[THREAD] Started supervised thread for {config.instance_name}")
        
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
                            print(f"[WARN]  [{instance_name}] Thread completed unexpectedly")
                        except Exception as e:
                            print(f"[FAIL] [{instance_name}] Thread failed with error: {e}")
                        
                        # Restart the failed listener
                        print(f"[LOOP] [{instance_name}] Restarting listener thread...")
                        config = next(c for c in configs if c.instance_name == instance_name)
                        listener = DatabaseListener(config)
                        new_future = executor.submit(listener.listen_and_process)
                        futures[instance_name] = new_future
                        print(f"[OK] [{instance_name}] Thread restarted successfully")
                        
        except KeyboardInterrupt:
            print("\n[STOP] Received interrupt signal. Shutting down...")
            return
        except Exception as e:
            print(f"[ERROR] Unexpected error in supervision loop: {e}")
            return


if __name__ == "__main__":
    main()
