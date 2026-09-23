"""Data access only: parameterised SQL, no HTTP or validation logic."""
from db import get_connection


def find_all_rooms() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, capacity FROM rooms ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]
