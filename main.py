"""HTTP layer only: routes, status codes and error handlers.

No SQL and no business rules here; those live in service.py / repository.py.
"""
import sqlite3
from typing import Any

from fastapi import Body, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

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


@app.exception_handler(service.ConflictError)
def handle_conflict(request: Request, exc: service.ConflictError):
    return error_response(409, str(exc))


@app.exception_handler(sqlite3.Error)
def handle_database_error(request: Request, exc: sqlite3.Error):
    # Log the real cause on the server console only; the client gets a
    # generic message so internal details (paths, SQL) are never leaked.
    print(f"[error] database error on {request.method} {request.url.path}: "
          f"{type(exc).__name__}: {exc}")
    return error_response(503, "Database unavailable, please try again later")


@app.exception_handler(RequestValidationError)
def handle_bad_request(request: Request, exc: RequestValidationError):
    # FastAPI raises this for malformed JSON or a non-numeric id in the URL.
    # By default it returns 422 in its own format; we use 400 + our shape.
    first = exc.errors()[0]
    where = ".".join(str(part) for part in first["loc"])
    return error_response(400, f"Invalid request ({where}): {first['msg']}")


@app.exception_handler(StarletteHTTPException)
def handle_http_error(request: Request, exc: StarletteHTTPException):
    # e.g. 404 for an unknown URL or 405 for a wrong HTTP method
    return error_response(exc.status_code, str(exc.detail))


@app.exception_handler(Exception)
def handle_unexpected_error(request: Request, exc: Exception):
    print(f"[error] unexpected error on {request.method} {request.url.path}: "
          f"{type(exc).__name__}: {exc}")
    return error_response(500, "Internal server error")


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


@app.delete("/api/bookings/{booking_id}", status_code=204)
def cancel_booking(booking_id: int):
    service.cancel_booking(booking_id)
    return Response(status_code=204)  # 204 No Content: success, empty body
