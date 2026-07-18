"""Flask auth routes on app.server (auth.routes).

Uses a bare Flask app with only the auth routes registered, pointed at the
isolated test database. No Dash/browser needed — Flask's test client drives it.
"""

import pytest
from flask import Flask

from auth.routes import register_auth_routes, current_user_id, COOKIE
from auth.core import create_session, signup

pytestmark = pytest.mark.usefixtures("mongo_test_db")


@pytest.fixture()
def client(monkeypatch):
    # Secure cookies aren't sent over the test client's plain http; disable for tests.
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "0")
    app = Flask(__name__)
    app.testing = True
    register_auth_routes(app)
    return app.test_client()


# ── signup ──────────────────────────────────────────────────────────────────
def test_signup_returns_user_and_sets_cookie(client):
    resp = client.post(
        "/auth/signup",
        json={"email": "tom@example.com", "password": "secret@1", "confirm": "secret@1"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["email"] == "tom@example.com"
    assert body["userId"]
    assert "password_hash" not in body
    # A session cookie was set.
    set_cookie = resp.headers.get("Set-Cookie", "")
    assert COOKIE in set_cookie
    assert "HttpOnly" in set_cookie


def test_signup_rejects_mismatched_confirm(client):
    resp = client.post(
        "/auth/signup",
        json={"email": "tom@example.com", "password": "secret@1", "confirm": "different@1"},
    )
    assert resp.status_code == 400
    assert "match" in resp.get_json()["error"].lower()


def test_signup_rejects_weak_password(client):
    resp = client.post(
        "/auth/signup",
        json={"email": "tom@example.com", "password": "weak", "confirm": "weak"},
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_signup_rejects_duplicate_email(client):
    payload = {"email": "tom@example.com", "password": "secret@1", "confirm": "secret@1"}
    client.post("/auth/signup", json=payload)
    resp = client.post("/auth/signup", json=payload)
    assert resp.status_code == 400
    assert "already exists" in resp.get_json()["error"]


# ── login ───────────────────────────────────────────────────────────────────
def _register(client, email="tom@example.com", password="secret@1"):
    return client.post(
        "/auth/signup", json={"email": email, "password": password, "confirm": password}
    )


def test_login_succeeds_and_sets_cookie(client):
    _register(client)
    client.delete_cookie(COOKIE)  # drop the signup cookie so login is a clean test
    resp = client.post("/auth/login", json={"email": "tom@example.com", "password": "secret@1"})
    assert resp.status_code == 200
    assert resp.get_json()["email"] == "tom@example.com"
    assert COOKIE in resp.headers.get("Set-Cookie", "")


def test_login_wrong_password_is_401(client):
    _register(client)
    resp = client.post("/auth/login", json={"email": "tom@example.com", "password": "nope@9"})
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "Invalid email or password."


def test_login_unknown_email_is_401(client):
    resp = client.post("/auth/login", json={"email": "nobody@example.com", "password": "secret@1"})
    assert resp.status_code == 401


# ── me ──────────────────────────────────────────────────────────────────────
def test_me_returns_user_when_authenticated(client):
    _register(client)  # signup leaves the session cookie in the client jar
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["email"] == "tom@example.com"
    assert "password_hash" not in body


def test_me_is_401_without_cookie(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


# ── logout ──────────────────────────────────────────────────────────────────
def test_logout_clears_cookie_and_invalidates_session(client):
    _register(client)
    assert client.get("/auth/me").status_code == 200      # authenticated
    logout = client.post("/auth/logout")
    assert logout.status_code == 200
    assert client.get("/auth/me").status_code == 401       # session gone


# ── current_user_id() Dash bridge ───────────────────────────────────────────
def test_current_user_id_resolves_cookie_in_request_context():
    from flask import Flask

    user, _ = signup("dash@example.com", "secret@1")
    raw = create_session(user["userId"], remember=False)

    app = Flask(__name__)
    # Simulate an incoming request carrying the session cookie.
    with app.test_request_context("/", headers={"Cookie": f"{COOKIE}={raw}"}):
        assert current_user_id() == user["userId"]


def test_current_user_id_none_without_cookie():
    from flask import Flask

    app = Flask(__name__)
    with app.test_request_context("/"):
        assert current_user_id() is None
