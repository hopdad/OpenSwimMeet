import sqlite3
from pathlib import Path

def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables (expand as needed)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number INTEGER,
        name TEXT,
        distance INTEGER,
        stroke TEXT,
        gender TEXT,
        min_age INTEGER,
        max_age INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS swimmers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        team TEXT,
        usas_id TEXT,
        age INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        swimmer_id INTEGER,
        event_id INTEGER,
        seed_time REAL,  -- seconds
        FOREIGN KEY(swimmer_id) REFERENCES swimmers(id),
        FOREIGN KEY(event_id) REFERENCES events(id)
    )
    """)

    conn.commit()
    return conn

def open_meet_db(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)
