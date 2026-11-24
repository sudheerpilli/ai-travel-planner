"""
Storage Service for TripWise.
Persists saved itineraries using SQLite with shareable links and full JSON data storage.
"""

from __future__ import annotations
import json
import os
import sqlite3
import uuid
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "trips.db")


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_trips (
                id TEXT PRIMARY KEY,
                destination TEXT NOT NULL,
                start_location TEXT,
                start_date TEXT,
                end_date TEXT,
                travelers INTEGER,
                currency TEXT,
                total_cost REAL,
                trip_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
    conn.close()


def save_trip(trip_data: dict) -> str:
    init_db()
    conn = get_db()
    trip_id = str(uuid.uuid4())[:8]  # Clean 8-char shareable ID
    now = datetime.now().isoformat()

    destination = trip_data.get("destination", "Unknown Destination")
    start_loc = trip_data.get("start_location", "")
    start_date = trip_data.get("start_date", "")
    end_date = trip_data.get("end_date", "")
    travelers = trip_data.get("travelers", 1)
    currency = trip_data.get("currency", "INR")
    total_cost = trip_data.get("budget_analysis", {}).get("total_estimated_trip_cost", 0.0)

    # Attach the assigned ID inside the stored data
    trip_data["trip_id"] = trip_id
    trip_data["saved_at"] = now

    with conn:
        conn.execute("""
            INSERT INTO saved_trips (
                id, destination, start_location, start_date, end_date,
                travelers, currency, total_cost, trip_data, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trip_id, destination, start_loc, start_date, end_date,
            travelers, currency, total_cost, json.dumps(trip_data), now, now
        ))
    conn.close()
    return trip_id


def get_trip(trip_id: str) -> dict | None:
    init_db()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM saved_trips WHERE id = ?", (trip_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    data = json.loads(row["trip_data"])
    data["trip_id"] = row["id"]
    data["created_at"] = row["created_at"]
    return data


def list_saved_trips() -> list[dict]:
    init_db()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, destination, start_location, start_date, end_date, travelers, currency, total_cost, created_at FROM saved_trips ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_trip(trip_id: str) -> bool:
    init_db()
    conn = get_db()
    with conn:
        cur = conn.execute("DELETE FROM saved_trips WHERE id = ?", (trip_id,))
        count = cur.rowcount
    conn.close()
    return count > 0


def update_trip(trip_id: str, trip_data: dict) -> bool:
    init_db()
    conn = get_db()
    now = datetime.now().isoformat()
    trip_data["trip_id"] = trip_id
    trip_data["updated_at"] = now
    with conn:
        cur = conn.execute("""
            UPDATE saved_trips SET
                destination = ?,
                start_location = ?,
                start_date = ?,
                end_date = ?,
                travelers = ?,
                currency = ?,
                total_cost = ?,
                trip_data = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            trip_data.get("destination", ""),
            trip_data.get("start_location", ""),
            trip_data.get("start_date", ""),
            trip_data.get("end_date", ""),
            trip_data.get("travelers", 1),
            trip_data.get("currency", "INR"),
            trip_data.get("budget_analysis", {}).get("total_estimated_trip_cost", 0.0),
            json.dumps(trip_data),
            now,
            trip_id
        ))
        count = cur.rowcount
    conn.close()
    return count > 0

