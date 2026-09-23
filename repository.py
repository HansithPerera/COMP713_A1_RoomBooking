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


def insert_booking(booking: dict) -> dict:
    """Insert a booking and return it with its new id."""
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO bookings (room_id, booker_name, date, start_hour, end_hour) "
            "VALUES (?, ?, ?, ?, ?)",
            (booking["room_id"], booking["booker_name"], booking["date"],
             booking["start_hour"], booking["end_hour"]),
        )
        new_id = cursor.lastrowid
    return {"id": new_id, **booking}
