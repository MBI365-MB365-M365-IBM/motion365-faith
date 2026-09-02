import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("MOTION365_DB", "/app/data/motion365.db")

def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS registry (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            data TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

def get_registry():
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT data, updated_at FROM registry WHERE id = 1"
        ).fetchone()

        if row is None:
            data = {
                "worlds": [],
                "ecosystems": [],
                "portals": [],
                "nodes": [],
                "connections": [],
                "motions": [],
                "features": []
            }
            updated_at = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO registry (id, data, updated_at) VALUES (1, ?, ?)",
                (json.dumps(data), updated_at)
            )
            conn.commit()
        else:
            data = json.loads(row[0])
            updated_at = row[1]

        return {"registry": data, "updated_at": updated_at}
    finally:
        conn.close()

def put_registry(data):
    if not isinstance(data, dict):
        raise ValueError("registry must be an object")

    normalized = {
        "worlds": data.get("worlds", []),
        "ecosystems": data.get("ecosystems", []),
        "portals": data.get("portals", []),
        "nodes": data.get("nodes", []),
        "connections": data.get("connections", []),
        "motions": data.get("motions", []),
        "features": data.get("features", [])
    }

    updated_at = datetime.now(timezone.utc).isoformat()

    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO registry (id, data, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (json.dumps(normalized), updated_at)
        )
        conn.commit()
    finally:
        conn.close()

    return {"registry": normalized, "updated_at": updated_at}
