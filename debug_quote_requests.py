#!/usr/bin/env python3
"""Debug script for quote_requests table and notifications"""

import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

def test_database_connection():
    """Test connection to Instance 2 database"""
    database_url = os.getenv("DATABASE_URL_2")
    
    print(f"Testing Instance 2 database connection...")
    print(f"Database URL: {database_url[:50]}...")
    
    try:
        conn = psycopg.connect(database_url, autocommit=True)
        print("✅ Database connection successful")
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def test_quote_requests_table(conn):
    """Test quote_requests table structure and data"""
    try:
        with conn.cursor() as cur:
            # Check if table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'quote_requests'
                );
            """)
            table_exists = cur.fetchone()[0]
            
            if not table_exists:
                print("❌ quote_requests table does not exist")
                return False
                
            print("✅ quote_requests table exists")
            
            # Check table structure
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'quote_requests'
                ORDER BY ordinal_position;
            """)
            columns = cur.fetchall()
            print(f"📋 Table columns: {len(columns)}")
            for col_name, col_type in columns:
                print(f"   - {col_name}: {col_type}")
            
            # Check for existing records
            cur.execute("SELECT COUNT(*) FROM quote_requests;")
            count = cur.fetchone()[0]
            print(f"📊 Total records: {count}")
            
            return True
            
    except Exception as e:
        print(f"❌ Table check failed: {e}")
        return False

def test_trigger_function(conn):
    """Test if the notify_new_quote_request function exists"""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_proc 
                    WHERE proname = 'notify_new_quote_request'
                );
            """)
            function_exists = cur.fetchone()[0]
            
            if function_exists:
                print("✅ notify_new_quote_request function exists")
            else:
                print("❌ notify_new_quote_request function missing")
                
            # Check trigger
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_trigger 
                    WHERE tgname = 'trg_notify_new_quote_request'
                );
            """)
            trigger_exists = cur.fetchone()[0]
            
            if trigger_exists:
                print("✅ trg_notify_new_quote_request trigger exists")
            else:
                print("❌ trg_notify_new_quote_request trigger missing")
                
            return function_exists and trigger_exists
            
    except Exception as e:
        print(f"❌ Trigger check failed: {e}")
        return False

def insert_test_quote_request(conn):
    """Insert a test quote request and check for notifications"""
    try:
        with conn.cursor() as cur:
            # Insert test record
            cur.execute("""
                INSERT INTO quote_requests (
                    name, email, phone, company, service, message, consent, status
                ) VALUES (
                    'Debug Test User',
                    'debug@example.com',
                    '555-0123',
                    'Debug Company Inc',
                    'Debug Service',
                    'This is a debug test message',
                    true,
                    'new'
                ) RETURNING id;
            """)
            
            record_id = cur.fetchone()[0]
            print(f"✅ Test quote request inserted with ID: {record_id}")
            
            # Check if record was inserted correctly
            cur.execute("SELECT * FROM quote_requests WHERE id = %s", (record_id,))
            record = cur.fetchone()
            
            if record:
                print(f"✅ Record retrieved successfully: {record[1]} ({record[4]})")  # name and service
                return record_id
            else:
                print("❌ Failed to retrieve inserted record")
                return None
                
    except Exception as e:
        print(f"❌ Insert test failed: {e}")
        return None

if __name__ == "__main__":
    print("=== Quote Requests Debug Script ===")
    
    conn = test_database_connection()
    if not conn:
        exit(1)
        
    if not test_quote_requests_table(conn):
        exit(1)
        
    if not test_trigger_function(conn):
        print("⚠️  Trigger function missing - notifications may not work")
        
    record_id = insert_test_quote_request(conn)
    if record_id:
        print(f"🎯 Test complete. Check listener logs for notification processing of record {record_id}")
    
    conn.close()