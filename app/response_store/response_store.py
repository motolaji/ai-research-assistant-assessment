import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            sources TEXT NOT NULL,
            researcher TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_response(db_path: Path, trace_id: str, question: str, answer: str, sources: list[str], researcher: str | None) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO queries (trace_id, question, answer, sources, researcher, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (trace_id, question, answer, json.dumps(sources), researcher, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def get_responses(db_path: Path, limit: int = 10) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM queries ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r, sources=json.loads(r["sources"])) for r in rows]


def get_response_by_trace(db_path: Path, trace_id: str) -> dict | None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM queries WHERE trace_id = ?", (trace_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row, sources=json.loads(row["sources"]))