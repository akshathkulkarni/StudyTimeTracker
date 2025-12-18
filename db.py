from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

DB_FILE = Path(__file__).resolve().parent.parent / "study_logs.db"


@dataclass
class StudyEntry:
    date_iso: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    category: str
    duration_minutes: int


def _get_conn(db_path: Path = DB_FILE) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Path = DB_FILE) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _get_conn(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS study_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                study_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                category TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def insert_entries(entries: Iterable[StudyEntry], db_path: Path = DB_FILE) -> None:
    rows = [
        (e.date_iso, e.start_time, e.end_time, e.category, e.duration_minutes)
        for e in entries
    ]
    if not rows:
        return
    with _get_conn(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO study_logs (study_date, start_time, end_time, category, duration_minutes)
            VALUES (?, ?, ?, ?, ?);
            """,
            rows,
        )


def delete_entries_for_date(date_iso: str, db_path: Path = DB_FILE) -> None:
    with _get_conn(db_path) as conn:
        conn.execute(
            """
            DELETE FROM study_logs
            WHERE study_date = ?;
            """,
            (date_iso,),
        )


def fetch_entries(date_iso: str, db_path: Path = DB_FILE) -> List[StudyEntry]:
    with _get_conn(db_path) as conn:
        cur = conn.execute(
            """
            SELECT study_date, start_time, end_time, category, duration_minutes
            FROM study_logs
            WHERE study_date = ?
            ORDER BY start_time ASC;
            """,
            (date_iso,),
        )
        rows = cur.fetchall()
    return [
        StudyEntry(
            date_iso=row[0],
            start_time=row[1],
            end_time=row[2],
            category=row[3],
            duration_minutes=row[4],
        )
        for row in rows
    ]

