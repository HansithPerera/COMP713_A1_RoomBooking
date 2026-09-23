"""Database connection and schema setup (data-persistence layer)."""
import os
import sqlite3
from contextlib import contextmanager

# Configurable so the marker (or a failure demo) can point to another file.
DB_PATH = os.environ.get("BOOKING_DB_PATH", "booking.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT    NOT NULL UNIQUE,
    capacity  INTEGER NOT NULL CHECK (capacity > 0)
);

CREATE TABLE IF NOT EXISTS bookings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id     INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    booker_name TEXT    NOT NULL,
    date        TEXT    NOT NULL,              -- YYYY-MM-DD
    start_hour  INTEGER NOT NULL CHECK (start_hour BETWEEN 8 AND 21),
    end_hour    INTEGER NOT NULL CHECK (end_hour BETWEEN 9 AND 22),
    CHECK (end_hour > start_hour)
);
"""

SEED_ROOMS = [("Study Room A", 4), ("Study Room B", 6), ("Seminar Room", 20)]


@contextmanager
def get_connection():
    """Open a short-lived connection for one unit of work.

    Usage: `with get_connection() as conn: ...`
    Commits if the block succeeds, rolls back if it raises, and always
    closes the connection so no file handles are left open.
    """
    # timeout=5: wait up to 5 s if another client holds the write lock
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")  # SQLite needs this for FKs
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables and seed rooms if the database is empty."""
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO rooms (name, capacity) VALUES (?, ?)", SEED_ROOMS
            )
    print(f"[db] initialised database at {DB_PATH}")
