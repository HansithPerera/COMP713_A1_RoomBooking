"""Application logic: input validation and business rules.

No HTTP objects and no SQL here. Problems are reported by raising one of the
custom exceptions below; main.py turns each one into an HTTP status code.
"""
from datetime import date, datetime

# Business rules
OPENING_HOUR = 8       # earliest start hour (08:00)
CLOSING_HOUR = 22      # latest end hour (22:00)
MAX_NAME_LENGTH = 50


class ValidationError(Exception):
    """The client sent invalid input (mapped to HTTP 400)."""


class NotFoundError(Exception):
    """The requested room or booking does not exist (mapped to HTTP 404)."""


class ConflictError(Exception):
    """The booking overlaps an existing booking (mapped to HTTP 409)."""


def parse_date(value) -> date:
    """Check that value is a real calendar date written as YYYY-MM-DD."""
    if not isinstance(value, str):
        raise ValidationError("date is required in YYYY-MM-DD format")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError("date must be a valid date in YYYY-MM-DD format")
    # strptime also accepts "2026-9-5"; insist on the exact zero-padded form
    if parsed.isoformat() != value:
        raise ValidationError("date must be a valid date in YYYY-MM-DD format")
    return parsed


def _require_int(payload: dict, field: str) -> int:
    """Return payload[field] if it is a whole number, else raise."""
    value = payload.get(field)
    # bool is a subclass of int in Python, so reject True/False explicitly
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{field} is required and must be a whole number")
    return value


def validate_booking(payload) -> dict:
    """Validate a new-booking request body and return the cleaned values."""
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")

    room_id = _require_int(payload, "room_id")

    name = payload.get("booker_name")
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("booker_name is required")
    name = name.strip()
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationError(
            f"booker_name must be at most {MAX_NAME_LENGTH} characters"
        )

    booking_date = parse_date(payload.get("date"))
    if booking_date < date.today():
        raise ValidationError("date cannot be in the past")

    start_hour = _require_int(payload, "start_hour")
    end_hour = _require_int(payload, "end_hour")
    if start_hour < OPENING_HOUR or end_hour > CLOSING_HOUR:
        raise ValidationError(
            f"Bookings must be between {OPENING_HOUR}:00 and {CLOSING_HOUR}:00"
        )
    if end_hour <= start_hour:
        raise ValidationError("end_hour must be later than start_hour")

    return {
        "room_id": room_id,
        "booker_name": name,
        "date": booking_date.isoformat(),
        "start_hour": start_hour,
        "end_hour": end_hour,
    }
