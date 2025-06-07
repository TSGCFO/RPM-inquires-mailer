import builtins
import types
import json
import pytest

import listener


def make_response(token):
    class Resp:
        def raise_for_status(self):
            pass
        def json(self):
            return {"access_token": token, "expires_in": 3600}
    return Resp()


def create_test_config(instance_name="Test-Instance"):
    """Create a test InstanceConfig for testing."""
    return listener.InstanceConfig(
        pg_host="localhost",
        pg_database="test_db",
        pg_user="test_user",
        pg_password="test_pass",
        tenant_id="test-tenant-id",
        client_id="test-client-id",
        client_secret="test-client-secret",
        from_email="test@example.com",
        to_email="recipient@example.com",
        instance_name=instance_name
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
