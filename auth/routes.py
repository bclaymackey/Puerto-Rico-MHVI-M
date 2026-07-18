"""Flask auth routes, registered on the Dash app's underlying server (app.server).

Kept thin: each route parses the request, calls auth.core, and manages the session
cookie. All real logic lives in auth.core so it stays framework-agnostic and tested.

The session cookie is HttpOnly + SameSite=Lax, and Secure by default. For pure
http://localhost testing set AUTH_COOKIE_SECURE=0 (Secure cookies aren't sent over
plain http); flip it back on (the default) before deploying behind HTTPS.
"""

import os

from flask import make_response, request

from auth.core import (
    create_session,
    get_public_user,
    login,
    resolve_session,
    revoke_session,
    signup,
)

COOKIE = "session"


def _cookie_secure() -> bool:
    return os.getenv("AUTH_COOKIE_SECURE", "1") != "0"


def _set_session_cookie(resp, raw_token: str, remember: bool):
    max_age = 60 * 60 * 24 * (30 if remember else 1)
    resp.set_cookie(
        COOKIE,
        raw_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="Lax",
        max_age=max_age,
    )


def current_user_id() -> str | None:
    """Resolve the request's session cookie to a user_id (or None).

    Shared by the Dash layer so a logged-in browser transparently gets its
    account id in place of the old browser UUID.
    """
    return resolve_session(request.cookies.get(COOKIE))


def register_auth_routes(server) -> None:
    """Attach the /auth/* routes to a Flask server (typically app.server)."""

    @server.route("/auth/signup", methods=["POST"])
    def _signup():
        body = request.get_json(silent=True) or {}
        if body.get("password") != body.get("confirm"):
            return {"error": "Passwords do not match."}, 400
        user, err = signup(body.get("email", ""), body.get("password", ""))
        if err:
            return {"error": err}, 400
        remember = bool(body.get("remember"))
        raw = create_session(user["userId"], remember)
        resp = make_response(user)
        _set_session_cookie(resp, raw, remember)
        return resp

    @server.route("/auth/login", methods=["POST"])
    def _login():
        body = request.get_json(silent=True) or {}
        user, err = login(body.get("email", ""), body.get("password", ""))
        if err:
            return {"error": err}, 401
        remember = bool(body.get("remember"))
        raw = create_session(user["userId"], remember)
        resp = make_response(user)
        _set_session_cookie(resp, raw, remember)
        return resp

    @server.route("/auth/logout", methods=["POST"])
    def _logout():
        revoke_session(request.cookies.get(COOKIE))
        resp = make_response({"ok": True})
        resp.delete_cookie(COOKIE)
        return resp

    @server.route("/auth/me", methods=["GET"])
    def _me():
        user = get_public_user(current_user_id())
        if not user:
            return {"error": "Not authenticated"}, 401
        return user
