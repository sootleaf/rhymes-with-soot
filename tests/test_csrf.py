"""Identity-bound CSRF protection tests."""
from tests.helpers import extract_csrf, login, make_user


def _get_token(client):
    """Fetch a page and return (token, csrf_cookie_value)."""
    resp = client.get("/t/page")
    token = extract_csrf(resp.get_data(as_text=True))
    cookie = client.get_cookie(client.application.config["CSRF_COOKIE"])
    return token, (cookie.value if cookie else None)


def test_valid_token_passes(client):
    token, _ = _get_token(client)
    resp = client.post("/t/echo", data={"csrf_token": token})
    assert resp.status_code == 200


def test_missing_token_rejected(client):
    resp = client.post("/t/echo", data={})
    assert resp.status_code == 400


def test_token_mismatch_rejected(client):
    _, _ = _get_token(client)
    resp = client.post("/t/echo", data={"csrf_token": "f" * 32})
    assert resp.status_code == 400


def test_token_via_header(client):
    token, _ = _get_token(client)
    resp = client.post("/t/echo", headers={"X-CSRF-Token": token})
    assert resp.status_code == 200


def test_identity_mismatch_rejected(client):
    """A token whose cookie is bound to one identity is rejected under another.

    Logging in normally re-issues the CSRF cookie on identity change, so to
    isolate the identity-binding check we keep Alice's cookie in place and
    swap only the session cookie to Bob.
    """
    from rhymes_with_soot.auth.session import sign_session

    app = client.application
    make_user(app, "alice", "pw-alice")
    make_user(app, "bob", "pw-bob")

    # Alice logs in; her page issues a CSRF cookie bound to "alice".
    login(client, "alice", "pw-alice")
    alice_token, _ = _get_token(client)

    # Swap the session to Bob without re-issuing the CSRF cookie.
    client.set_cookie(
        client.application.config["SESSION_COOKIE"],
        sign_session("bob", 3600),
        domain="localhost",
    )

    # Replay: token matches the cookie, but the cookie's identity (alice)
    # differs from the session identity (bob) -> rejected.
    resp = client.post("/t/echo", data={"csrf_token": alice_token})
    assert resp.status_code == 400


def test_anonymous_token_rejected_after_login(client):
    """A token issued while anonymous is not replayable after logging in."""
    make_user(client.application, "alice", "pw-alice")
    anon_token, _ = _get_token(client)
    login(client, "alice", "pw-alice")
    resp = client.post("/t/echo", data={"csrf_token": anon_token})
    assert resp.status_code == 400
