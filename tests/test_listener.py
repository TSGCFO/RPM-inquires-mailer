import os
import builtins
import types
import json
import pytest

# Ensure required environment variables are set before importing the module
for _var in [
    "PGHOST",
    "PGDATABASE",
    "PGUSER",
    "PGPASSWORD",
    "TENANT_ID",
    "CLIENT_ID",
    "CLIENT_SECRET",
    "FROM_EMAIL",
    "TO_EMAIL",
]:
    os.environ.setdefault(_var, f"test-{_var.lower()}")

import listener


def make_response(token):
    class Resp:
        def raise_for_status(self):
            pass
        def json(self):
            return {"access_token": token, "expires_in": 3600}
    return Resp()


def test_graph_token_caching(monkeypatch):
    calls = []
    tokens = ["token1", "token2"]
    def fake_post(url, data=None, timeout=0):
        calls.append(1)
        return make_response(tokens[len(calls)-1])
    monkeypatch.setattr(listener.requests, "post", fake_post)
    current = [0]
    monkeypatch.setattr(listener.time, "time", lambda: current[0])
    listener._token = {"val": None, "exp": 0}

    current[0] = 0
    assert listener.graph_token() == "token1"
    assert len(calls) == 1

    current[0] = 100
    assert listener.graph_token() == "token1"
    assert len(calls) == 1

    current[0] = listener._token["exp"] - 10
    assert listener.graph_token() == "token2"
    assert len(calls) == 2


def test_send_email_builds_payload(monkeypatch):
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
    monkeypatch.setattr(listener, "graph_token", lambda: "tok")
    # prevent database setup during import (already imported, but ensure no connect)
    monkeypatch.setattr(listener.psycopg, "connect", lambda *a, **kw: None)

    record = {
        "name": "Foo",
        "email": "foo@example.com",
        "message": "Hi"
    }

    listener.send_email(record, "sender@test", "recipient@test")

    assert sent['headers']['Authorization'] == "Bearer tok"
    assert sent['url'].endswith("/users/sender@test/sendMail")
    assert sent['payload']['message']['subject'] == "🆕 New Inquiry Received"
    assert sent['payload']['message']['toRecipients'][0]['emailAddress']['address'] == "recipient@test"
    assert "Foo" in sent['payload']['message']['body']['content']


def test_listen_for_db_calls_send_email(monkeypatch):
    payload = {"id": 1, "name": "Test"}
    fake_cfg = {
        "host": "h",
        "dbname": "db",
        "user": "u",
        "password": "p",
    }

    class FakeNotify:
        def __init__(self, payload):
            self.payload = json.dumps(payload)

    class FakeCursor:
        def execute(self, *a, **kw):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()
        def notifies(self):
            yield FakeNotify(payload)

    def fake_connect(*args, **kwargs):
        assert kwargs["host"] == fake_cfg["host"]
        assert kwargs["dbname"] == fake_cfg["dbname"]
        assert kwargs["user"] == fake_cfg["user"]
        assert kwargs["password"] == fake_cfg["password"]
        assert kwargs.get("autocommit") is True
        return FakeConn()

    monkeypatch.setattr(listener.psycopg, "connect", fake_connect)
    captured = {}

    def fake_send_email(record, from_addr, to_addr):
        captured["record"] = record
        captured["from"] = from_addr
        captured["to"] = to_addr

    monkeypatch.setattr(listener, "send_email", fake_send_email)

    listener.listen_for_db(fake_cfg, "sender@test", "recipient@test")

    assert captured["record"] == payload
    assert captured["from"] == "sender@test"
    assert captured["to"] == "recipient@test"
