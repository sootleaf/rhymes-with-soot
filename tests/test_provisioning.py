"""User provisioning tests."""
import json

from werkzeug.security import check_password_hash

from rhymes_with_soot.db import get_session
from rhymes_with_soot.models import User
from rhymes_with_soot.provisioning import provision_users


def _users(app):
    session = get_session()
    return {u.username: u for u in session.query(User).all()}


def test_provisions_new_users(app):
    with open(app.config["USERS_FILE"], "w") as f:
        json.dump({"alice": "pw-alice", "bob": "pw-bob"}, f)
    provision_users(app)
    users = _users(app)
    assert set(users) == {"alice", "bob"}
    # Passwords are stored hashed, not plaintext.
    assert users["alice"].password_hash != "pw-alice"
    assert check_password_hash(users["alice"].password_hash, "pw-alice")


def test_idempotent_on_rerun(app):
    with open(app.config["USERS_FILE"], "w") as f:
        json.dump({"alice": "pw-alice"}, f)
    provision_users(app)
    provision_users(app)
    users = _users(app)
    assert set(users) == {"alice"}


def test_existing_users_not_overwritten(app):
    with open(app.config["USERS_FILE"], "w") as f:
        json.dump({"alice": "first-password"}, f)
    provision_users(app)

    with open(app.config["USERS_FILE"], "w") as f:
        json.dump({"alice": "second-password"}, f)
    provision_users(app)

    alice = _users(app)["alice"]
    # The original hash wins; the second password must not authenticate.
    assert check_password_hash(alice.password_hash, "first-password")
    assert not check_password_hash(alice.password_hash, "second-password")


def test_missing_file_creates_empty(app):
    import os

    os.remove(app.config["USERS_FILE"])
    provision_users(app)  # must not raise
    with open(app.config["USERS_FILE"]) as f:
        assert json.load(f) == {}


def test_malformed_json_does_not_crash(app):
    with open(app.config["USERS_FILE"], "w") as f:
        f.write("{not valid json")
    provision_users(app)  # must not raise
    assert _users(app) == {}
