import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

@contextmanager
def get_connection(db_path: str):
    """Context manager for database connections."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize a new meet database with complete schema."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # Teams table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_code TEXT UNIQUE NOT NULL,
        team_name TEXT NOT NULL,
        team_short_name TEXT,
        team_color TEXT DEFAULT '#0066CC'
    )
    """)

    # Events table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number INTEGER UNIQUE,
        name TEXT,
        distance INTEGER,
        stroke TEXT,
        gender TEXT CHECK(gender IN ('M', 'F', 'X', 'Mixed')),
        min_age INTEGER,
        max_age INTEGER,
        is_relay INTEGER DEFAULT 0,
        course TEXT DEFAULT 'SCY' CHECK(course IN ('SCY', 'SCM', 'LCM'))
    )
    """)

    # Swimmers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS swimmers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        team_id INTEGER,
        usas_id TEXT UNIQUE,
        age INTEGER,
        gender TEXT CHECK(gender IN ('M', 'F', 'X')),
        date_of_birth TEXT,
        is_non_scoring INTEGER DEFAULT 0,
        FOREIGN KEY(team_id) REFERENCES teams(id)
    )
    """)

    # Entries table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        swimmer_id INTEGER,
        event_id INTEGER,
        seed_time REAL,
        FOREIGN KEY(swimmer_id) REFERENCES swimmers(id) ON DELETE CASCADE,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
        UNIQUE(swimmer_id, event_id)
    )
    """)

    # Heats table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS heats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        heat_number INTEGER NOT NULL,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
        UNIQUE(event_id, heat_number)
    )
    """)

    # Heat assignments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS heat_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_id INTEGER NOT NULL,
        heat_id INTEGER NOT NULL,
        lane INTEGER NOT NULL,
        FOREIGN KEY(entry_id) REFERENCES entries(id) ON DELETE CASCADE,
        FOREIGN KEY(heat_id) REFERENCES heats(id) ON DELETE CASCADE,
        UNIQUE(heat_id, lane)
    )
    """)

    # Results table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_id INTEGER NOT NULL,
        heat_id INTEGER NOT NULL,
        lane INTEGER NOT NULL,
        finish_time REAL,
        place INTEGER,
        points REAL DEFAULT 0,
        dq INTEGER DEFAULT 0,
        ns INTEGER DEFAULT 0,
        FOREIGN KEY(entry_id) REFERENCES entries(id) ON DELETE CASCADE,
        FOREIGN KEY(heat_id) REFERENCES heats(id) ON DELETE CASCADE
    )
    """)

    # Meet settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meet_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()
    return conn

def open_meet_db(db_path: str) -> sqlite3.Connection:
    """Open an existing meet database."""
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Meet database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def get_or_insert_team(conn: sqlite3.Connection, team_code: str, team_name: str) -> int:
    """Get or insert a team and return its ID."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM teams WHERE team_code = ?", (team_code,))
    row = cursor.fetchone()
    if row:
        return row[0]
    
    cursor.execute(
        "INSERT INTO teams (team_code, team_name, team_short_name) VALUES (?, ?, ?)",
        (team_code, team_name, team_name[:20])
    )
    conn.commit()
    return cursor.lastrowid

def get_or_insert_swimmer(
    conn: sqlite3.Connection, 
    name: str, 
    team_code: str,
    team_name: str = None,
    usas_id: Optional[str] = None, 
    age: int = 0,
    gender: Optional[str] = None,
    date_of_birth: Optional[str] = None
) -> int:
    """Get or insert a swimmer and return its ID."""
    cursor = conn.cursor()
    
    # Get or create team
    team_name = team_name or team_code
    team_id = get_or_insert_team(conn, team_code, team_name)
    
    # Check if swimmer exists by USAS ID
    if usas_id:
        cursor.execute("SELECT id FROM swimmers WHERE usas_id = ?", (usas_id,))
        row = cursor.fetchone()
        if row:
            # Update if details changed
            cursor.execute(
                "UPDATE swimmers SET name = ?, team_id = ?, age = ?, gender = ?, date_of_birth = ? WHERE id = ?",
                (name, team_id, age, gender, date_of_birth, row[0])
            )
            conn.commit()
            return row[0]

    # Check by name and team
    cursor.execute(
        "SELECT id FROM swimmers WHERE name = ? AND team_id = ?", 
        (name, team_id)
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    # Insert new swimmer
    cursor.execute(
        "INSERT INTO swimmers (name, team_id, usas_id, age, gender, date_of_birth) VALUES (?, ?, ?, ?, ?, ?)",
        (name, team_id, usas_id, age, gender, date_of_birth)
    )
    conn.commit()
    return cursor.lastrowid

def get_event_id(conn: sqlite3.Connection, event_num: int) -> Optional[int]:
    """Get event ID by event number."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM events WHERE number = ?", (event_num,))
    row = cursor.fetchone()
    return row[0] if row else None

def insert_or_update_entry(
    conn: sqlite3.Connection, 
    swimmer_id: int, 
    event_id: int, 
    seed_time: Optional[float]
):
    """Insert or update an entry."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM entries WHERE swimmer_id = ? AND event_id = ?", 
        (swimmer_id, event_id)
    )
    if cursor.fetchone():
        cursor.execute(
            "UPDATE entries SET seed_time = ? WHERE swimmer_id = ? AND event_id = ?",
            (seed_time, swimmer_id, event_id)
        )
    else:
        cursor.execute(
            "INSERT INTO entries (swimmer_id, event_id, seed_time) VALUES (?, ?, ?)",
            (swimmer_id, event_id, seed_time)
        )
    conn.commit()

def get_meet_setting(conn: sqlite3.Connection, key: str, default: str = None) -> Optional[str]:
    """Get a meet setting value."""
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM meet_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    return row[0] if row else default

def set_meet_setting(conn: sqlite3.Connection, key: str, value: str):
    """Set a meet setting value."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO meet_settings (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()

def is_meet_completed(conn: sqlite3.Connection) -> bool:
    """Check if meet is marked as completed."""
    return get_meet_setting(conn, "meet_completed", "0") == "1"

def mark_meet_complete(conn: sqlite3.Connection, completed: bool = True):
    """Mark meet as completed or incomplete."""
    set_meet_setting(conn, "meet_completed", "1" if completed else "0")
