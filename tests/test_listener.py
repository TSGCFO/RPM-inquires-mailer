import importlib
import json
import os
import pytest


def reload_listener():
    return importlib.reload(importlib.import_module("listener"))


def setup_env(monkeypatch):
    envs = {
        "PGHOST": "h1",
        "PGDATABASE": "d1",
        "PGUSER": "u1",
        "PGPASSWORD": "p1",
        "PGHOST2": "h2",
        "PGDATABASE2": "d2",
        "PGUSER2": "u2",
        "PGPASSWORD2": "p2",
        "TENANT_ID": "tid",
        "CLIENT_ID": "cid",
        "CLIENT_SECRET": "sec",
        "FROM_EMAIL": "f1@example.com",
        "TO_EMAIL": "t1@example.com",
        "FROM_EMAIL2": "f2@example.com",
        "TO_EMAIL2": "t2@example.com",
    }
    for k, v in envs.items():
        monkeypatch.setenv(k, v)


def make_response(token):
    class Resp:
        def raise_for_status(self):
            pass
        def json(self):
            return {"access_token": token, "expires_in": 3600}
    return Resp()


def test_graph_token_caching(monkeypatch):
    setup_env(monkeypatch)
    listener = reload_listener()
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
    setup_env(monkeypatch)
    listener = reload_listener()
    sent = {}
    def fake_post(url, headers=None, json=None, timeout=0):
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

    listener.send_email(record, "from@example.com", "to@example.com")

    assert sent['headers']['Authorization'] == "Bearer tok"
    assert sent['payload']['message']['subject'] == "🆕 New Inquiry Received"
    assert "Foo" in sent['payload']['message']['body']['content']
