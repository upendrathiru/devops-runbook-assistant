"""
Storage & audit logging.

Uses SQLite for the demo/prototype so the whole project runs with zero
external services. The schema and query patterns are intentionally
PostgreSQL-compatible (standard SQL, no SQLite-only features) so migrating
to Postgres in production is a driver swap, not a redesign — see
docs/ARCHITECTURE.md.
"""
import sqlite3
import uuid
import csv
import io
from datetime import datetime, timezone
from contextlib import contextmanager

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS queries (
    query_id TEXT PRIMARY KEY,
    session_id TEXT,
    user_id TEXT,
    question TEXT,
    answer TEXT,
    sources TEXT,
    latency_ms INTEGER,
    created_at TEXT,
    feedback TEXT
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def create_session(user_id: str) -> str:
    session_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, user_id, created_at) VALUES (?, ?, ?)",
            (session_id, user_id, datetime.now(timezone.utc).isoformat()),
        )
    return session_id


def log_query(session_id, user_id, question, answer, sources, latency_ms) -> str:
    query_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO queries
               (query_id, session_id, user_id, question, answer, sources, latency_ms, created_at, feedback)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
            (query_id, session_id, user_id, question, answer, sources, latency_ms,
             datetime.now(timezone.utc).isoformat()),
        )
    return query_id


def set_feedback(query_id: str, feedback: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("UPDATE queries SET feedback = ? WHERE query_id = ?", (feedback, query_id))
        return cur.rowcount > 0


def get_session_history(session_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM queries WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_metrics():
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM queries").fetchone()["c"]
        avg_latency = conn.execute("SELECT AVG(latency_ms) a FROM queries").fetchone()["a"] or 0
        helpful = conn.execute("SELECT COUNT(*) c FROM queries WHERE feedback = 'up'").fetchone()["c"]
        not_helpful = conn.execute("SELECT COUNT(*) c FROM queries WHERE feedback = 'down'").fetchone()["c"]
        failed = conn.execute(
            "SELECT COUNT(*) c FROM queries WHERE answer LIKE '%not sure%'"
        ).fetchone()["c"]
        return {
            "total_queries": total,
            "avg_latency_ms": round(avg_latency, 1),
            "feedback_helpful": helpful,
            "feedback_not_helpful": not_helpful,
            "queries_with_no_answer": failed,
        }


def export_logs_csv() -> str:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT query_id, session_id, user_id, question, answer, feedback, created_at FROM queries "
            "ORDER BY created_at ASC"
        ).fetchall()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["query_id", "session_id", "user_id", "question", "answer", "feedback", "timestamp"])
    for r in rows:
        writer.writerow([r["query_id"], r["session_id"], r["user_id"], r["question"],
                          r["answer"], r["feedback"], r["created_at"]])
    return buf.getvalue()
