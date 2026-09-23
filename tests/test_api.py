"""API tests: each test gets its own fresh temporary SQLite database.

Run from the project folder with:  pytest -v
"""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import db
import main
import repository
import service

TOMORROW = (date.today() + timedelta(days=1)).isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient talking to the app, backed by a new empty database."""
    db_file = str(tmp_path / "test_booking.db")
    # db.DB_PATH is read from BOOKING_DB_PATH when db.py is first imported,
    # so we point both at the temp file. get_connection() uses db.DB_PATH.
    monkeypatch.setenv("BOOKING_DB_PATH", db_file)
    monkeypatch.setattr(db, "DB_PATH", db_file)
    # Entering the "with" block runs the lifespan startup (creates + seeds DB)
    with TestClient(main.app) as test_client:
        yield test_client


def booking(**changes) -> dict:
    """A valid booking body; keyword arguments override single fields."""
    body = {
        "room_id": 1,
        "booker_name": "Alice",
        "date": TOMORROW,
        "start_hour": 10,
        "end_hour": 12,
    }
    body.update(changes)
    return body


# ---------------------------------------------------------------- rooms

def test_list_rooms_returns_200_and_seeded_rooms(client):
    response = client.get("/api/rooms")
    assert response.status_code == 200
    rooms = response.json()
    assert len(rooms) == 3
    assert rooms[0] == {"id": 1, "name": "Study Room A", "capacity": 4}


# ---------------------------------------------------------------- create

def test_create_booking_returns_201_with_booking(client):
    response = client.post("/api/bookings", json=booking())
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["booker_name"] == "Alice"
    assert body["start_hour"] == 10 and body["end_hour"] == 12


def test_booker_name_is_trimmed_and_50_chars_allowed(client):
    name = "x" * 50
    response = client.post("/api/bookings", json=booking(booker_name=f"  {name}  "))
    assert response.status_code == 201
    assert response.json()["booker_name"] == name


@pytest.mark.parametrize(
    "changes",
    [
        {"booker_name": ""},                    # blank name
        {"booker_name": "   "},                 # whitespace-only name
        {"booker_name": None},                  # missing name
        {"booker_name": "x" * 51},              # name too long
        {"date": "25-12-2030"},                 # wrong date format
        {"date": "2030-02-30"},                 # impossible date
        {"date": YESTERDAY},                    # date in the past
        {"start_hour": 7, "end_hour": 9},       # starts before 08:00
        {"start_hour": 21, "end_hour": 23},     # ends after 22:00
        {"start_hour": 12, "end_hour": 12},     # end == start
        {"start_hour": 14, "end_hour": 12},     # end before start
        {"start_hour": 10.5},                   # not a whole number
        {"room_id": "one"},                     # room_id not a number
    ],
)
def test_invalid_booking_returns_400(client, changes):
    response = client.post("/api/bookings", json=booking(**changes))
    assert response.status_code == 400
    assert "error" in response.json()


def test_missing_body_field_returns_400(client):
    body = booking()
    del body["end_hour"]
    response = client.post("/api/bookings", json=body)
    assert response.status_code == 400
    assert "end_hour" in response.json()["error"]


def test_malformed_json_returns_400(client):
    response = client.post(
        "/api/bookings",
        content="{not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert "error" in response.json()


def test_create_booking_for_unknown_room_returns_404(client):
    response = client.post("/api/bookings", json=booking(room_id=999))
    assert response.status_code == 404
    assert response.json() == {"error": "Room 999 not found"}


# ---------------------------------------------------------------- overlap

@pytest.mark.parametrize(
    "start, end",
    [(10, 12), (11, 13), (9, 11), (9, 13), (10, 11)],
)
def test_overlapping_booking_returns_409(client, start, end):
    assert client.post("/api/bookings", json=booking()).status_code == 201
    response = client.post(
        "/api/bookings",
        json=booking(booker_name="Bob", start_hour=start, end_hour=end),
    )
    assert response.status_code == 409
    assert "error" in response.json()


def test_adjacent_bookings_are_allowed(client):
    first = client.post("/api/bookings", json=booking(start_hour=10, end_hour=12))
    second = client.post("/api/bookings", json=booking(start_hour=12, end_hour=14))
    assert first.status_code == 201
    assert second.status_code == 201


def test_same_time_in_different_room_is_allowed(client):
    assert client.post("/api/bookings", json=booking(room_id=1)).status_code == 201
    assert client.post("/api/bookings", json=booking(room_id=2)).status_code == 201


def test_concurrent_requests_cannot_double_book(client):
    """20 threads try to book the same slot at once; exactly one may win."""
    def attempt(_):
        try:
            service.create_booking(booking(room_id=3, start_hour=15, end_hour=17))
            return "created"
        except service.ConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(attempt, range(20)))

    assert results.count("created") == 1
    assert results.count("conflict") == 19


# ---------------------------------------------------------------- list bookings

def test_list_bookings_for_room_and_date(client):
    client.post("/api/bookings", json=booking(start_hour=14, end_hour=15))
    client.post("/api/bookings", json=booking(start_hour=9, end_hour=10))
    client.post("/api/bookings", json=booking(room_id=2))  # other room

    response = client.get(f"/api/rooms/1/bookings?date={TOMORROW}")
    assert response.status_code == 200
    hours = [(b["start_hour"], b["end_hour"]) for b in response.json()]
    assert hours == [(9, 10), (14, 15)]  # only room 1, sorted by start


def test_list_bookings_unknown_room_returns_404(client):
    response = client.get(f"/api/rooms/999/bookings?date={TOMORROW}")
    assert response.status_code == 404
    assert "error" in response.json()


@pytest.mark.parametrize("query", ["?date=not-a-date", "?date=2030-13-01", ""])
def test_list_bookings_invalid_date_returns_400(client, query):
    response = client.get(f"/api/rooms/1/bookings{query}")
    assert response.status_code == 400
    assert "error" in response.json()


# ---------------------------------------------------------------- delete

def test_delete_booking_returns_204(client):
    booking_id = client.post("/api/bookings", json=booking()).json()["id"]
    response = client.delete(f"/api/bookings/{booking_id}")
    assert response.status_code == 204
    assert response.content == b""
    remaining = client.get(f"/api/rooms/1/bookings?date={TOMORROW}").json()
    assert remaining == []


def test_delete_unknown_booking_returns_404(client):
    response = client.delete("/api/bookings/999")
    assert response.status_code == 404
    assert response.json() == {"error": "Booking 999 not found"}


def test_delete_then_rebook_same_slot_succeeds(client):
    booking_id = client.post("/api/bookings", json=booking()).json()["id"]
    assert client.post("/api/bookings", json=booking()).status_code == 409
    assert client.delete(f"/api/bookings/{booking_id}").status_code == 204
    assert client.post("/api/bookings", json=booking()).status_code == 201


# ---------------------------------------------------------------- errors

def test_database_unavailable_returns_503(client, monkeypatch):
    def broken_connection():
        raise sqlite3.OperationalError("unable to open database file")

    # repository.py imported get_connection by name, so patch it there
    monkeypatch.setattr(repository, "get_connection", broken_connection)

    response = client.get("/api/rooms")
    assert response.status_code == 503
    # generic message only: the real sqlite error is not leaked to the client
    assert response.json() == {"error": "Database unavailable, please try again later"}


def test_unknown_route_uses_json_error_shape(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert "error" in response.json()


def test_client_page_is_served_at_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "<title>Room Booking</title>" in response.text
