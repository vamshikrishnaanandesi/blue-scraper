"""Simple SQLite storage for tracking downloaded chapters.

Provides helpers to initialize the DB and record/query download records.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

_DB_PATH: Optional[str] = None


def init_db(db_path: str) -> None:
    """Initialize the database file and create tables if needed.

    db_path: full path to sqlite file. Directory will be created if missing.
    """
    global _DB_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    _DB_PATH = db_path
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series TEXT NOT NULL,
                chapter_num REAL NOT NULL,
                chapter_id TEXT,
                url TEXT,
                out_path TEXT,
                status TEXT,
                size INTEGER,
                downloaded_at TEXT,
                UNIQUE(series, chapter_num)
            )
            """
        )
        conn.commit()


@contextmanager
def _get_conn():
    if not _DB_PATH:
        raise RuntimeError("DB not initialized. Call init_db(path) first.")
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    try:
        yield conn
    finally:
        conn.close()


def record_download(series: str, chapter_num: float, chapter_id: Optional[str], url: Optional[str], out_path: str, status: str = "completed", size: Optional[int] = None) -> None:
    """Insert or update a download record.

    status: e.g., 'completed', 'failed', 'skipped', 'dry-run'
    size: bytes (optional)
    """
    now = datetime.utcnow().isoformat() + "Z"
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO downloads (series, chapter_num, chapter_id, url, out_path, status, size, downloaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(series, chapter_num) DO UPDATE SET
              chapter_id=excluded.chapter_id,
              url=excluded.url,
              out_path=excluded.out_path,
              status=excluded.status,
              size=excluded.size,
              downloaded_at=excluded.downloaded_at
            """,
            (series, chapter_num, chapter_id, url, out_path, status, size, now),
        )
        conn.commit()


def was_downloaded(series: str, chapter_num: float) -> bool:
    """Return True if the chapter is recorded as completed and has non-zero size."""
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT status, size FROM downloads WHERE series = ? AND chapter_num = ? LIMIT 1",
            (series, chapter_num),
        )
        row = cur.fetchone()
        if not row:
            return False
        status, size = row
        if status == "completed" and size and size > 0:
            return True
        return False


def get_all_downloads(series: Optional[str] = None):
    """Return all download records as tuples. Useful for debugging/inspection."""
    with _get_conn() as conn:
        cur = conn.cursor()
        if series:
            cur.execute("SELECT * FROM downloads WHERE series = ? ORDER BY chapter_num", (series,))
        else:
            cur.execute("SELECT * FROM downloads ORDER BY series, chapter_num")
        return cur.fetchall()
