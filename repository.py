"""Data access only: parameterised SQL, no HTTP or validation logic.

Every query uses ? placeholders so user input is never pasted into SQL
(this prevents SQL injection).
"""
from db import get_connection


def find_all_rooms() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, capacity FROM rooms ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def find_room_by_id(room_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, capacity FROM rooms WHERE id = ?", (room_id,)
        ).fetchone()
    return dict(row) if row else None


def find_bookings(room_id: int, booking_date: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, room_id, booker_name, date, start_hour, end_hour "
            "FROM bookings "
            "WHERE room_id = ? AND date = ? ORDER BY start_hour",
            (room_id, booking_date),
        ).fetchall()
    return [dict(r) for r in rows]


def insert_booking_if_free(booking: dict) -> dict | None:
    """Insert the booking unless it overlaps an existing one.

    Returns the new booking (with its id), or None if the slot is taken.

    Concurrency: several clients (browsers, API tools) share one database.
    If we checked for overlaps and inserted in two separate steps, two
    clients could both see the slot as free and both insert = double booking.
    "BEGIN IMMEDIATE" takes SQLite's write lock *before* the check, so a
    second client's transaction waits until ours commits, and its overlap
    check then sees our booking. Check + insert happen as one atomic unit.
    """
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")

        # Two time ranges overlap when each starts before the other ends.
        # Adjacent bookings (10-12 and 12-14) do NOT overlap.
        clash = conn.execute(
            "SELECT id FROM bookings "
            "WHERE room_id = ? AND date = ? AND start_hour < ? AND end_hour > ?",
            (booking["room_id"], booking["date"],
             booking["end_hour"], booking["start_hour"]),
        ).fetchone()
        if clash:
            return None  # leaving the with-block ends the transaction

        cursor = conn.execute(
            "INSERT INTO bookings (room_id, booker_name, date, start_hour, end_hour) "
            "VALUES (?, ?, ?, ?, ?)",
            (booking["room_id"], booking["booker_name"], booking["date"],
             booking["start_hour"], booking["end_hour"]),
        )
        new_id = cursor.lastrowid
    return {"id": new_id, **booking}
