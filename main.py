"""HTTP layer: routes only. Business rules live in service.py (Stage 2)."""
from fastapi import FastAPI

import repository
from db import init_db

app = FastAPI(title="Room Booking API")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/rooms")
def list_rooms():
    print("[api] GET /api/rooms")
    return repository.find_all_rooms()
