"""User provisioning from a users.json file on startup.
Existing users are not overwritten. The file is not committed to version control."""
import json
import logging

from werkzeug.security import generate_password_hash

logger = logging.getLogger("rhymes_with_soot")


def provision_users(app):
    """Load users from the site's users.json into the database.
    Idempotent; safe under concurrent workers."""
    from rhymes_with_soot.db import get_session
    from rhymes_with_soot.models import User

    users_file = app.config["USERS_FILE"]
    try:
        with open(users_file, "r", encoding="utf-8") as f:
            users_data = json.load(f)
    except FileNotFoundError:
        # Create an empty file so the operator knows where to add accounts.
        try:
            with open(users_file, "w", encoding="utf-8") as f:
                f.write("{}\n")
            logger.warning(
                "Users file not found; created an empty one at %s. "
                "Add accounts as JSON of {\"username\": \"password\"}, e.g. "
                "{\"alice\": \"a-long-password\"}, then restart the service. "
                "Only users listed here are provisioned.",
                users_file,
            )
        except OSError as e:
            logger.error("Failed to create users file %s: %s", users_file, e)
        return
    except json.JSONDecodeError as e:
        logger.error("Failed to parse users file %s: %s", users_file, e)
        return

    from sqlalchemy.exc import IntegrityError

    session = get_session()
    try:
        for username, password in users_data.items():
            with session.no_autoflush:
                existing = session.query(User).filter_by(username=username).first()
            if existing is None:
                user = User(
                    username=username,
                    password_hash=generate_password_hash(password),
                )
                session.add(user)
                logger.info("Provisioned user: %s", username)
        session.commit()
    except IntegrityError:
        # Another worker provisioned the same user concurrently.
        session.rollback()
        logger.debug("Provisioning race: user already exists (another worker).")
    finally:
        session.close()
