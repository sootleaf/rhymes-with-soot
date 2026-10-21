"""Stateless signed cookie session. Valid on any worker; no server-side store."""
import time
from functools import wraps

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import request, current_app, g, redirect, url_for, abort

_serializer = None


def _get_serializer():
    global _serializer
    if _serializer is None:
        _serializer = URLSafeTimedSerializer(
            current_app.config["SECRET_KEY"],
            salt=current_app.config["ENV_PREFIX"],
        )
    return _serializer


def sign_session(username: str, max_age: int) -> str:
    payload = {"u": username, "exp": int(time.time()) + max_age}
    return _get_serializer().dumps(payload)


def verify_session(cookie_value: str, max_age: int):
    try:
        payload = _get_serializer().loads(cookie_value, max_age=max_age)
        return payload.get("u")
    except (BadSignature, SignatureExpired):
        return None


def get_current_user():
    """Load the current user from the session cookie. Returns User or None.
    Cached on ``g`` for the request."""
    if hasattr(g, "current_user"):
        return g.current_user

    from rhymes_with_soot.db import get_session
    from rhymes_with_soot.models import User

    cookie = request.cookies.get(current_app.config["SESSION_COOKIE"])
    if not cookie:
        g.current_user = None
        return None

    username = verify_session(cookie, current_app.config["SESSION_MAX_AGE"])
    if not username:
        g.current_user = None
        return None

    session = get_session()
    user = session.query(User).filter_by(username=username).first()
    g.current_user = user
    return user


def login_required(f):
    """Decorator: require an authenticated user.

    Redirects to the login page for GET requests, returns 401 for others.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if user is None:
            if request.method == "GET":
                return redirect(url_for("auth.login"))
            abort(401)
        return f(*args, **kwargs)
    return decorated
