import builtins
import types
import json
import pytest

import listener


def make_response(token, status_code=200):
    class Resp:
        def __init__(self):
            self.status_code = status_code
        def raise_for_status(self):
            pass
        def json(self):
            return {"access_token": token, "expires_in": 3600}
    return Resp()


def create_test_config(instance_name="Test-Instance", connection_string=None):
    """Create a test InstanceConfig for testing."""
    return listener.InstanceConfig(
        connection_string=connection_string,
        pg_host="localhost" if not connection_string else None,
        pg_database="test_db" if not connection_string else None,
        pg_user="test_user" if not connection_string else None,
        pg_password="test_pass" if not connection_string else None,
        tenant_id="test-tenant-id",
        client_id="test-client-id",
        client_secret="test-client-secret",
        from_email="test@example.com",
        to_email="recipient@example.com",
        instance_name=instance_name,
        listen_channel="test_channel"
    )


def test_graph_token_caching_per_tenant(monkeypatch):
    calls = []
    tokens = ["token1", "token2", "token3"]
    def fake_post(url, data=None, timeout=0):
        calls.append(1)
        return make_response(tokens[len(calls)-1])
    monkeypatch.setattr(listener.requests, "post", fake_post)
    current = [0]
    monkeypatch.setattr(listener.time, "time", lambda: current[0])
    listener._tokens.clear()  # Clear token cache

    config1 = create_test_config("Instance-1")
    config1.tenant_id = "tenant1"
    config2 = create_test_config("Instance-2")
    config2.tenant_id = "tenant2"

    current[0] = 0
    # First call for tenant1
    assert listener.graph_token(config1) == "token1"
    assert len(calls) == 1

    # Second call for tenant1 (should use cache)
    current[0] = 100
    assert listener.graph_token(config1) == "token1"
    assert len(calls) == 1

    # First call for tenant2 (should make new request)
    assert listener.graph_token(config2) == "token2"
    assert len(calls) == 2

    # Token expiry for tenant1
    current[0] = listener._tokens["tenant1"]["exp"] - 10
    assert listener.graph_token(config1) == "token3"
    assert len(calls) == 3


def test_database_listener_send_email(monkeypatch):
    sent = {}
    def fake_post(url, headers=None, json=None, timeout=0):
        sent['url'] = url
        sent['headers'] = headers
        sent['payload'] = json
        class Resp:
            def __init__(self):
                self.status_code = 202
            def raise_for_status(self):
                pass
        return Resp()
    monkeypatch.setattr(listener.requests, "post", fake_post)
    monkeypatch.setattr(listener, "graph_token", lambda config: "test-token")

    config = create_test_config()
    db_listener = listener.DatabaseListener(config)
    
    record = {
        "id": "123",
        "name": "John Doe",
        "email": "john@example.com",
        "message": "Test inquiry"
    }

    db_listener.send_email(record)

    assert sent['headers']['Authorization'] == "Bearer test-token"
    assert sent['payload']['message']['subject'] == "🆕 New Inquiry Received"
    assert "John Doe" in sent['payload']['message']['body']['content']
    assert sent['payload']['message']['toRecipients'][0]['emailAddress']['address'] == config.to_email
    assert sent['url'] == f"https://graph.microsoft.com/v1.0/users/{config.from_email}/sendMail"


def test_load_instance_configs_single_instance(monkeypatch):
    # Mock environment variables for instance 1 only
    env_vars = {
        "PGHOST": "localhost",
        "PGDATABASE": "db1",
        "PGUSER": "user1",
        "PGPASSWORD": "pass1",
        "TENANT_ID": "tenant1",
        "CLIENT_ID": "client1",
        "CLIENT_SECRET": "secret1",
        "FROM_EMAIL": "from1@example.com",
        "TO_EMAIL": "to1@example.com"
    }
    monkeypatch.setattr("os.getenv", lambda key, default=None: env_vars.get(key, default))

    configs = listener.load_instance_configs()
    
    assert len(configs) == 1
    assert configs[0].instance_name == "Instance-1"
    assert configs[0].pg_database == "db1"
    assert configs[0].from_email == "from1@example.com"


def test_load_instance_configs_dual_instance(monkeypatch):
    # Mock environment variables for both instances
    env_vars = {
        # Instance 1
        "PGHOST": "localhost",
        "PGDATABASE": "db1",
        "PGUSER": "user1",
        "PGPASSWORD": "pass1",
        "TENANT_ID": "tenant1",
        "CLIENT_ID": "client1",
        "CLIENT_SECRET": "secret1",
        "FROM_EMAIL": "from1@example.com",
        "TO_EMAIL": "to1@example.com",
        # Instance 2
        "PGHOST_2": "localhost2",
        "PGDATABASE_2": "db2",
        "PGUSER_2": "user2",
        "PGPASSWORD_2": "pass2",
        "TENANT_ID_2": "tenant2",
        "CLIENT_ID_2": "client2",
        "CLIENT_SECRET_2": "secret2",
        "FROM_EMAIL_2": "from2@example.com",
        "TO_EMAIL_2": "to2@example.com"
    }
    monkeypatch.setattr("os.getenv", lambda key, default=None: env_vars.get(key, default))

    configs = listener.load_instance_configs()
    
    assert len(configs) == 2
    assert configs[0].instance_name == "Instance-1"
    assert configs[1].instance_name == "Instance-2"
    assert configs[0].pg_database == "db1"
    assert configs[1].pg_database == "db2"
    assert configs[0].from_email == "from1@example.com"
    assert configs[1].from_email == "from2@example.com"


def test_connection_string_support(monkeypatch):
    """Test that InstanceConfig properly handles connection strings."""
    connection_string = "postgresql://user:pass@host:5432/dbname?sslmode=require"
    config = create_test_config(connection_string=connection_string)
    
    assert config.connection_string == connection_string
    assert config.pg_host is None
    assert config.pg_database is None
    assert config.pg_user is None
    assert config.pg_password is None


def test_individual_db_variables_support(monkeypatch):
    """Test that InstanceConfig properly handles individual database variables."""
    config = create_test_config()  # No connection string
    
    assert config.connection_string is None
    assert config.pg_host == "localhost"
    assert config.pg_database == "test_db"
    assert config.pg_user == "test_user"
    assert config.pg_password == "test_pass"


def test_load_instance_configs_with_connection_strings(monkeypatch):
    """Test loading configurations with DATABASE_URL connection strings."""
    env_vars = {
        # Instance 1 with connection string
        "DATABASE_URL": "postgresql://user:pass@host:5432/db1?sslmode=require",
        "TENANT_ID": "tenant1",
        "CLIENT_ID": "client1", 
        "CLIENT_SECRET": "secret1",
        "FROM_EMAIL": "from1@example.com",
        "TO_EMAIL": "to1@example.com",
        # Instance 2 with connection string
        "DATABASE_URL_2": "postgresql://user:pass@host:5432/db2?sslmode=require",
        "TENANT_ID_2": "tenant2",
        "CLIENT_ID_2": "client2",
        "CLIENT_SECRET_2": "secret2", 
        "FROM_EMAIL_2": "from2@example.com",
        "TO_EMAIL_2": "to2@example.com"
    }
    monkeypatch.setattr("os.getenv", lambda key, default=None: env_vars.get(key, default))

    configs = listener.load_instance_configs()
    
    assert len(configs) == 2
    assert configs[0].connection_string == "postgresql://user:pass@host:5432/db1?sslmode=require"
    assert configs[1].connection_string == "postgresql://user:pass@host:5432/db2?sslmode=require"
    assert configs[0].listen_channel == "new_record_channel"
    assert configs[1].listen_channel == "quote_request_channel"


def test_unique_notification_channels(monkeypatch):
    """Test that instances use unique notification channels."""
    env_vars = {
        # Instance 1
        "DATABASE_URL": "postgresql://user:pass@host:5432/db1?sslmode=require",
        "TENANT_ID": "tenant1",
        "CLIENT_ID": "client1",
        "CLIENT_SECRET": "secret1",
        "FROM_EMAIL": "from1@example.com", 
        "TO_EMAIL": "to1@example.com",
        # Instance 2
        "DATABASE_URL_2": "postgresql://user:pass@host:5432/db2?sslmode=require",
        "TENANT_ID_2": "tenant2",
        "CLIENT_ID_2": "client2",
        "CLIENT_SECRET_2": "secret2",
        "FROM_EMAIL_2": "from2@example.com",
        "TO_EMAIL_2": "to2@example.com"
    }
    monkeypatch.setattr("os.getenv", lambda key, default=None: env_vars.get(key, default))

    configs = listener.load_instance_configs()
    
    # Verify unique channels to prevent cross-database interference
    assert configs[0].listen_channel != configs[1].listen_channel
    assert configs[0].listen_channel == "new_record_channel"  # Instance 1
    assert configs[1].listen_channel == "quote_request_channel"  # Instance 2


def test_quote_request_email_formatting(monkeypatch):
    """Test that quote_requests are formatted correctly for email."""
    sent = {}
    def fake_post(url, headers=None, json=None, timeout=0):
        sent['url'] = url
        sent['headers'] = headers
        sent['payload'] = json
        class Resp:
            def __init__(self):
                self.status_code = 202
            def raise_for_status(self):
                pass
        return Resp()
    monkeypatch.setattr(listener.requests, "post", fake_post)
    monkeypatch.setattr(listener, "graph_token", lambda config: "test-token")

    # Create Instance 2 config (quote_requests)
    config = create_test_config("Instance-2")
    db_listener = listener.DatabaseListener(config)
    
    # Quote request record with company and service fields
    quote_record = {
        "id": "456",
        "name": "Jane Doe",
        "email": "jane@company.com",
        "phone": "555-0123",
        "company": "Test Company",
        "service": "Shipping Service",
        "message": "Need quote for shipping",
        "consent": True,
        "current_shipments": "10 per month",
        "expected_shipments": "20 per month"
    }

    db_listener.send_email(quote_record)

    assert sent['payload']['message']['subject'] == "🆕 New Quote Request Received"
    body_content = sent['payload']['message']['body']['content']
    assert "New Quote Request Received" in body_content
    assert "Test Company" in body_content
    assert "Shipping Service" in body_content
    assert "10 per month" in body_content


def test_instance_2_database_listener_initialization():
    """Test that Instance 2 uses correct table and channel configuration."""
    config = create_test_config("Instance-2")
    config.listen_channel = "quote_request_channel"
    
    listener_instance = listener.DatabaseListener(config)
    
    assert listener_instance.config.instance_name == "Instance-2"
    assert listener_instance.config.listen_channel == "quote_request_channel"
