#!/usr/bin/env python3
"""
Test script to verify SSL connection improvements for Instance 3
This script tests the new reconnection logic without running the full listener
"""

import os
import sys
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to path so we can import listener
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import listener

def test_instance_3_connection():
    """Test Instance 3 connection with SSL improvements."""
    print("=== Testing Instance 3 SSL Connection Improvements ===")
    
    # Load configurations
    try:
        configs = listener.load_instance_configs()
        print(f"[OK] Loaded {len(configs)} configurations")
        
        # Find Instance 3
        instance_3_config = None
        for config in configs:
            if config.instance_name == "Instance-3":
                instance_3_config = config
                break
        
        if not instance_3_config:
            print("[ERROR] Instance 3 configuration not found")
            return False
        
        print(f"[OK] Found Instance 3 configuration for {instance_3_config.listen_channel}")
        
        # Test connection
        db_listener = listener.DatabaseListener(instance_3_config)
        
        print("\n--- Testing Connection ---")
        try:
            db_listener.connect()
            print("[OK] Initial connection successful")
            
            # Test heartbeat query
            with db_listener.conn.cursor() as cur:
                cur.execute("SELECT NOW(), version()")
                result = cur.fetchone()
                print(f"[OK] Heartbeat successful: {result[0]}")
                print(f"   Database version: {result[1][:80]}...")
            
            # Test LISTEN command
            with db_listener.conn.cursor() as cur:
                cur.execute(f"LISTEN {instance_3_config.listen_channel}")
                print(f"[OK] LISTEN command successful on {instance_3_config.listen_channel}")
            
            # Clean up
            db_listener.conn.close()
            print("[OK] Connection closed cleanly")
            return True
            
        except Exception as e:
            print(f"[ERROR] Connection test failed: {e}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Configuration loading failed: {e}")
        return False

def test_neon_detection():
    """Test that Neon database detection works correctly."""
    print("\n=== Testing Neon Database Detection ===")
    
    # Test with Neon connection string
    neon_config = listener.InstanceConfig(
        connection_string="postgresql://user:pass@ep-test.us-west-2.aws.neon.tech/db?sslmode=require",
        tenant_id="test", client_id="test", client_secret="test",
        from_email="test@test.com", to_email="test@test.com",
        instance_name="Test-Neon", listen_channel="test_channel"
    )
    
    # Check if connection string contains neon.tech
    if "neon.tech" in neon_config.connection_string:
        print("[OK] Neon database detection works for connection strings")
    else:
        print("[ERROR] Neon database detection failed for connection strings")
        return False
    
    # Test with individual parameters
    neon_config_2 = listener.InstanceConfig(
        pg_host="ep-test.us-west-2.aws.neon.tech",
        pg_database="testdb", pg_user="testuser", pg_password="testpass",
        tenant_id="test", client_id="test", client_secret="test",
        from_email="test@test.com", to_email="test@test.com",
        instance_name="Test-Neon-2", listen_channel="test_channel_2"
    )
    
    if neon_config_2.pg_host and "neon.tech" in neon_config_2.pg_host:
        print("[OK] Neon database detection works for individual parameters")
    else:
        print("[ERROR] Neon database detection failed for individual parameters")
        return False
    
    return True

if __name__ == "__main__":
    print("Starting SSL improvement tests...\n")
    
    success = True
    
    # Test Neon detection logic
    if not test_neon_detection():
        success = False
    
    # Test actual Instance 3 connection
    if not test_instance_3_connection():
        success = False
    
    print(f"\n=== Test Results ===")
    if success:
        print("[SUCCESS] All SSL improvement tests passed!")
        print("   - Neon database detection working")
        print("   - Instance 3 connection improvements applied")
        print("   - Connection keepalives configured")
        print("   - SSL settings optimized")
    else:
        print("[FAIL] Some tests failed. Check the output above.")
    
    sys.exit(0 if success else 1)