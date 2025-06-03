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

    listener.send_email(record)

    assert sent['headers']['Authorization'] == "Bearer tok"
    assert sent['payload']['message']['subject'] == "🆕 New Inquiry Received"
    assert "Foo" in sent['payload']['message']['body']['content']
