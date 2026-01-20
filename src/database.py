import sqlite3
from pathlib import Path

def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number INTEGER UNIQUE,
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
        usas_id TEXT UNIQUE,
        age INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        swimmer_id INTEGER,
        event_id INTEGER,
        seed_time REAL,
        FOREIGN KEY(swimmer_id) REFERENCES swimmers(id),
        FOREIGN KEY(event_id) REFERENCES events(id),
        UNIQUE(swimmer_id, event_id)
    )
    """)

    conn.commit()
    return conn

def open_meet_db(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)

# Helper: Get or insert swimmer (merge by USAS ID or name+team)
def get_or_insert_swimmer(conn: sqlite3.Connection, name: str, team: str, usas_id: str | None = None, age: int = 0) -> int:
    cursor = conn.cursor()
    if usas_id:
        cursor.execute("SELECT id FROM swimmers WHERE usas_id = ?", (usas_id,))
        row = cursor.fetchone()
        if row:
            # Update if details changed
            cursor.execute("UPDATE swimmers SET name = ?, team = ?, age = ? WHERE id = ?", (name, team, age, row[0]))
            conn.commit()
            return row[0]

    cursor.execute("SELECT id FROM swimmers WHERE name = ? AND team = ?", (name, team))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute("INSERT INTO swimmers (name, team, usas_id, age) VALUES (?, ?, ?, ?)", (name, team, usas_id, age))
    conn.commit()
    return cursor.lastrowid

# Get event ID by number
def get_event_id(conn: sqlite3.Connection, event_num: str) -> int | None:
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM events WHERE number = ?", (int(event_num) if event_num.isdigit() else event_num,))
    row = cursor.fetchone()
    return row[0] if row else None

# Insert or update entry
def insert_or_update_entry(conn: sqlite3.Connection, swimmer_id: int, event_id: int, seed_time: float | None):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM entries WHERE swimmer_id = ? AND event_id = ?", (swimmer_id, event_id))
    if cursor.fetchone():
        cursor.execute("UPDATE entries SET seed_time = ? WHERE swimmer_id = ? AND event_id = ?", (seed_time, swimmer_id, event_id))
    else:
        cursor.execute("INSERT INTO entries (swimmer_id, event_id, seed_time) VALUES (?, ?, ?)", (swimmer_id, event_id, seed_time))
    conn.commit()
