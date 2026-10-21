"""SQLite engine + scoped session. WAL enabled."""
import logging
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session

logger = logging.getLogger("rhymes_with_soot")

engine = None
Session = None


def _set_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
    finally:
        cursor.close()


def init_db(app):
    """Create the engine, session, and tables.
    Call after blueprints are registered so site models are on Base."""
    global engine, Session

    db_dir = os.path.dirname(app.config["DB_PATH"])
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{app.config['DB_PATH']}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    event.listen(engine, "connect", _set_sqlite_pragmas)
    Session = scoped_session(sessionmaker(bind=engine))

    from rhymes_with_soot.models import Base
    Base.metadata.create_all(engine)

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        Session.remove()


def get_session():
    return Session()
