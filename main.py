"""HTTP layer only: routes, status codes and error handlers.

No SQL and no business rules here; those live in service.py / repository.py.
"""
from typing import Any

from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse

import service
from db import init_db

app = FastAPI(title="Room Booking API")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


# ---------------------------------------------------------------------------
# Error handlers: turn service exceptions into {"error": "..."} responses
# ---------------------------------------------------------------------------

def error_response(status_code: int, message: str) -> JSONResponse:
    """Every error the API returns has the same JSON shape."""
    return JSONResponse(status_code=status_code, content={"error": message})


@app.exception_handler(service.ValidationError)
def handle_validation_error(request: Request, exc: service.ValidationError):
    return error_response(400, str(exc))


@app.exception_handler(service.NotFoundError)
def handle_not_found(request: Request, exc: service.NotFoundError):
    return error_response(404, str(exc))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/rooms")
def list_rooms():
    print("[api] GET /api/rooms")
    return service.list_rooms()


@app.get("/api/rooms/{room_id}/bookings")
def list_bookings(room_id: int, date: str | None = None):
    # date comes from the query string: ?date=YYYY-MM-DD
    return service.get_bookings(room_id, date)


@app.post("/api/bookings", status_code=201)
def create_booking(payload: Any = Body(default=None)):
    # The raw JSON body is passed to the service, which does all validation
    return service.create_booking(payload)
