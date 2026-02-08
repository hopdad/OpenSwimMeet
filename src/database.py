"""
Database module for OpenSwimMeet.
Complete schema with 15 tables supporting results, relays, records, scoring, validation,
undo/redo, backups, and schema versioning.
"""
import sqlite3
import shutil
import json
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime

# Current schema version
SCHEMA_VERSION = 2

# Default scoring tables
SCORING_TABLES = {
    'dual': {
        'individual': [5, 3, 1],
        'relay': [7, 0],
        'description': 'Dual meet (5-3-1 individual, 7-0 relay)'
    },
    'invitational': {
        'individual': [20, 17, 16, 15, 14, 13, 12, 11, 9, 7, 6, 5, 4, 3, 2, 1],
        'relay': [40, 34, 32, 30, 28, 26, 24, 22, 18, 14, 12, 10, 8, 6, 4, 2],
        'description': 'Invitational (20-17-16 individual, 40-34-32 relay)'
    },
    'championship': {
        'individual': [32, 28, 27, 26, 25, 24, 23, 22, 18, 14, 13, 12, 11, 10, 9, 8],
        'relay': [64, 56, 54, 52, 50, 48, 46, 44, 36, 28, 26, 24, 22, 20, 18, 16],
        'description': 'Championship (32-28-27 individual, 64-56-54 relay)'
    }
}

# DQ codes
DQ_CODES = {
    'FA': 'False start',
    'IM': 'Illegal motion at start',
    'NS': 'No show',
    'FL': 'Stroke infraction - Fly',
    'BK': 'Stroke infraction - Back',
    'BR': 'Stroke infraction - Breast',
    'FR': 'Stroke infraction - Free',
    'TN': 'Turn violation',
    'FN': 'Finish violation',
    'OT': 'Other',
}

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
    """Initialize a new meet database with complete schema (15 tables)."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # 1. Schema version table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT DEFAULT (datetime('now')),
        description TEXT
    )
    """)

    # 2. Teams table (enhanced with colors, contacts)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_code TEXT UNIQUE NOT NULL,
        team_name TEXT NOT NULL,
        team_short_name TEXT,
        team_color TEXT DEFAULT '#0066CC',
        team_color2 TEXT DEFAULT '#FFFFFF',
        coach_name TEXT,
        coach_email TEXT,
        coach_phone TEXT,
        address TEXT,
        notes TEXT
    )
    """)

    # 3. Events table
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
        course TEXT DEFAULT 'SCY' CHECK(course IN ('SCY', 'SCM', 'LCM')),
        event_fee REAL DEFAULT 0
    )
    """)

    # 4. Swimmers table (enhanced with check-in, photo, relay-only)
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
        is_relay_only INTEGER DEFAULT 0,
        checked_in INTEGER DEFAULT 0,
        check_in_time TEXT,
        photo_path TEXT,
        email TEXT,
        phone TEXT,
        FOREIGN KEY(team_id) REFERENCES teams(id)
    )
    """)

    # 5. Entries table
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

    # 6. Heats table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS heats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        heat_number INTEGER NOT NULL,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
        UNIQUE(event_id, heat_number)
    )
    """)

    # 7. Heat assignments table
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

    # 8. Results table (enhanced with DQ codes, reaction times, records)
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
        dq_code TEXT,
        dq_description TEXT,
        ns INTEGER DEFAULT 0,
        reaction_time REAL,
        is_personal_best INTEGER DEFAULT 0,
        is_record INTEGER DEFAULT 0,
        record_type TEXT,
        FOREIGN KEY(entry_id) REFERENCES entries(id) ON DELETE CASCADE,
        FOREIGN KEY(heat_id) REFERENCES heats(id) ON DELETE CASCADE
    )
    """)

    # 9. Relay teams table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS relay_teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        team_id INTEGER NOT NULL,
        relay_letter TEXT DEFAULT 'A',
        seed_time REAL,
        finish_time REAL,
        place INTEGER,
        points REAL DEFAULT 0,
        dq INTEGER DEFAULT 0,
        dq_code TEXT,
        heat_id INTEGER,
        lane INTEGER,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
        FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE,
        FOREIGN KEY(heat_id) REFERENCES heats(id) ON DELETE SET NULL
    )
    """)

    # 10. Relay splits table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS relay_splits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        relay_team_id INTEGER NOT NULL,
        leg_number INTEGER NOT NULL CHECK(leg_number BETWEEN 1 AND 4),
        swimmer_id INTEGER NOT NULL,
        split_time REAL,
        order_position INTEGER NOT NULL,
        FOREIGN KEY(relay_team_id) REFERENCES relay_teams(id) ON DELETE CASCADE,
        FOREIGN KEY(swimmer_id) REFERENCES swimmers(id) ON DELETE CASCADE,
        UNIQUE(relay_team_id, order_position)
    )
    """)

    # 11. Records table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_type TEXT NOT NULL CHECK(record_type IN ('pool', 'team', 'meet', 'age_group', 'league')),
        event_id INTEGER NOT NULL,
        swimmer_name TEXT NOT NULL,
        team_code TEXT,
        time REAL NOT NULL,
        date_set TEXT,
        age_group TEXT,
        course TEXT DEFAULT 'SCY',
        notes TEXT,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    )
    """)

    # 12. Validation rules table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS validation_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_name TEXT UNIQUE NOT NULL,
        rule_value TEXT NOT NULL,
        enabled INTEGER DEFAULT 1,
        description TEXT
    )
    """)

    # 13. Undo log table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS undo_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,
        table_name TEXT NOT NULL,
        record_id INTEGER,
        old_data TEXT,
        new_data TEXT,
        timestamp TEXT DEFAULT (datetime('now')),
        description TEXT
    )
    """)

    # 14. Meet announcements table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,
        priority INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        displayed INTEGER DEFAULT 0,
        event_id INTEGER,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE SET NULL
    )
    """)

    # 15. Meet settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meet_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Insert default validation rules
    default_rules = [
        ('max_individual_entries', '3', 'Maximum individual entries per swimmer'),
        ('max_relay_entries', '3', 'Maximum relay entries per swimmer'),
        ('enforce_gender_match', '1', 'Require swimmer gender to match event gender'),
        ('enforce_age_match', '1', 'Require swimmer age to be within event age range'),
        ('require_seed_time', '0', 'Require seed time for all entries'),
        ('allow_exhibition', '1', 'Allow exhibition/non-scoring entries'),
    ]
    for rule_name, rule_value, desc in default_rules:
        cursor.execute("""
            INSERT OR IGNORE INTO validation_rules (rule_name, rule_value, description)
            VALUES (?, ?, ?)
        """, (rule_name, rule_value, desc))

    # Record schema version
    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (version, description)
        VALUES (?, ?)
    """, (SCHEMA_VERSION, 'Full 15-table schema with results, relays, records, scoring, validation'))

    conn.commit()
    return conn


def open_meet_db(db_path: str) -> sqlite3.Connection:
    """Open an existing meet database, applying migrations if needed."""
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Meet database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(conn)
    return conn


def _apply_migrations(conn: sqlite3.Connection):
    """Apply database schema migrations if needed."""
    cursor = conn.cursor()

    # Check if schema_version table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
    if not cursor.fetchone():
        # Old database - run full migration from v1 to current
        _migrate_v1_to_v2(conn)
        return

    # Get current version
    cursor.execute("SELECT MAX(version) FROM schema_version")
    row = cursor.fetchone()
    current_version = row[0] if row and row[0] else 0

    if current_version < 2:
        _migrate_v1_to_v2(conn)


def _migrate_v1_to_v2(conn: sqlite3.Connection):
    """Migrate from schema v1 (basic 8 tables) to v2 (full 15 tables)."""
    cursor = conn.cursor()

    # Add schema_version table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT DEFAULT (datetime('now')),
        description TEXT
    )
    """)

    # Add missing columns to teams
    _add_column_if_missing(cursor, 'teams', 'team_color2', "TEXT DEFAULT '#FFFFFF'")
    _add_column_if_missing(cursor, 'teams', 'coach_name', 'TEXT')
    _add_column_if_missing(cursor, 'teams', 'coach_email', 'TEXT')
    _add_column_if_missing(cursor, 'teams', 'coach_phone', 'TEXT')
    _add_column_if_missing(cursor, 'teams', 'address', 'TEXT')
    _add_column_if_missing(cursor, 'teams', 'notes', 'TEXT')

    # Add missing columns to swimmers
    _add_column_if_missing(cursor, 'swimmers', 'is_relay_only', 'INTEGER DEFAULT 0')
    _add_column_if_missing(cursor, 'swimmers', 'checked_in', 'INTEGER DEFAULT 0')
    _add_column_if_missing(cursor, 'swimmers', 'check_in_time', 'TEXT')
    _add_column_if_missing(cursor, 'swimmers', 'photo_path', 'TEXT')
    _add_column_if_missing(cursor, 'swimmers', 'email', 'TEXT')
    _add_column_if_missing(cursor, 'swimmers', 'phone', 'TEXT')

    # Add missing columns to events
    _add_column_if_missing(cursor, 'events', 'event_fee', 'REAL DEFAULT 0')

    # Add missing columns to results
    _add_column_if_missing(cursor, 'results', 'dq_code', 'TEXT')
    _add_column_if_missing(cursor, 'results', 'dq_description', 'TEXT')
    _add_column_if_missing(cursor, 'results', 'reaction_time', 'REAL')
    _add_column_if_missing(cursor, 'results', 'is_personal_best', 'INTEGER DEFAULT 0')
    _add_column_if_missing(cursor, 'results', 'is_record', 'INTEGER DEFAULT 0')
    _add_column_if_missing(cursor, 'results', 'record_type', 'TEXT')

    # Create new tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS relay_teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        team_id INTEGER NOT NULL,
        relay_letter TEXT DEFAULT 'A',
        seed_time REAL,
        finish_time REAL,
        place INTEGER,
        points REAL DEFAULT 0,
        dq INTEGER DEFAULT 0,
        dq_code TEXT,
        heat_id INTEGER,
        lane INTEGER,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
        FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE,
        FOREIGN KEY(heat_id) REFERENCES heats(id) ON DELETE SET NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS relay_splits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        relay_team_id INTEGER NOT NULL,
        leg_number INTEGER NOT NULL CHECK(leg_number BETWEEN 1 AND 4),
        swimmer_id INTEGER NOT NULL,
        split_time REAL,
        order_position INTEGER NOT NULL,
        FOREIGN KEY(relay_team_id) REFERENCES relay_teams(id) ON DELETE CASCADE,
        FOREIGN KEY(swimmer_id) REFERENCES swimmers(id) ON DELETE CASCADE,
        UNIQUE(relay_team_id, order_position)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_type TEXT NOT NULL CHECK(record_type IN ('pool', 'team', 'meet', 'age_group', 'league')),
        event_id INTEGER NOT NULL,
        swimmer_name TEXT NOT NULL,
        team_code TEXT,
        time REAL NOT NULL,
        date_set TEXT,
        age_group TEXT,
        course TEXT DEFAULT 'SCY',
        notes TEXT,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS validation_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_name TEXT UNIQUE NOT NULL,
        rule_value TEXT NOT NULL,
        enabled INTEGER DEFAULT 1,
        description TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS undo_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,
        table_name TEXT NOT NULL,
        record_id INTEGER,
        old_data TEXT,
        new_data TEXT,
        timestamp TEXT DEFAULT (datetime('now')),
        description TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,
        priority INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        displayed INTEGER DEFAULT 0,
        event_id INTEGER,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE SET NULL
    )
    """)

    # Insert default validation rules
    default_rules = [
        ('max_individual_entries', '3', 'Maximum individual entries per swimmer'),
        ('max_relay_entries', '3', 'Maximum relay entries per swimmer'),
        ('enforce_gender_match', '1', 'Require swimmer gender to match event gender'),
        ('enforce_age_match', '1', 'Require swimmer age to be within event age range'),
        ('require_seed_time', '0', 'Require seed time for all entries'),
        ('allow_exhibition', '1', 'Allow exhibition/non-scoring entries'),
    ]
    for rule_name, rule_value, desc in default_rules:
        cursor.execute("""
            INSERT OR IGNORE INTO validation_rules (rule_name, rule_value, description)
            VALUES (?, ?, ?)
        """, (rule_name, rule_value, desc))

    # Record migration
    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (version, description)
        VALUES (?, ?)
    """, (SCHEMA_VERSION, 'Migration from v1 to v2: added relays, records, validation, undo, announcements'))

    conn.commit()


def _add_column_if_missing(cursor, table: str, column: str, col_type: str):
    """Add a column to a table if it doesn't already exist."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


# ─── Core CRUD Functions ───────────────────────────────────────────────

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


# ─── Meet Settings ─────────────────────────────────────────────────────

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


# ─── Results Functions ─────────────────────────────────────────────────

def save_result(conn: sqlite3.Connection, entry_id: int, heat_id: int, lane: int,
                finish_time: Optional[float] = None, dq: bool = False,
                dq_code: str = None, ns: bool = False,
                reaction_time: Optional[float] = None) -> int:
    """Save a result for a heat/lane assignment."""
    cursor = conn.cursor()

    # Check if result already exists
    cursor.execute(
        "SELECT id FROM results WHERE entry_id = ? AND heat_id = ?",
        (entry_id, heat_id)
    )
    existing = cursor.fetchone()

    dq_desc = DQ_CODES.get(dq_code, '') if dq_code else None

    if existing:
        cursor.execute("""
            UPDATE results SET finish_time = ?, dq = ?, dq_code = ?, dq_description = ?,
                   ns = ?, reaction_time = ?
            WHERE id = ?
        """, (finish_time, int(dq), dq_code, dq_desc, int(ns), reaction_time, existing[0]))
        result_id = existing[0]
    else:
        cursor.execute("""
            INSERT INTO results (entry_id, heat_id, lane, finish_time, dq, dq_code,
                   dq_description, ns, reaction_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (entry_id, heat_id, lane, finish_time, int(dq), dq_code, dq_desc,
              int(ns), reaction_time))
        result_id = cursor.lastrowid

    conn.commit()
    return result_id


def calculate_places(conn: sqlite3.Connection, event_id: int):
    """Calculate places for all heats in an event based on finish times."""
    cursor = conn.cursor()

    # Get all results for this event, ordered by finish time
    cursor.execute("""
        SELECT r.id, r.finish_time, r.dq, r.ns
        FROM results r
        JOIN heats h ON r.heat_id = h.id
        WHERE h.event_id = ?
        ORDER BY
            CASE WHEN r.dq = 1 OR r.ns = 1 OR r.finish_time IS NULL THEN 1 ELSE 0 END,
            r.finish_time ASC
    """, (event_id,))

    results = cursor.fetchall()
    place = 1
    for result_id, finish_time, dq, ns in results:
        if dq or ns or finish_time is None:
            cursor.execute("UPDATE results SET place = NULL WHERE id = ?", (result_id,))
        else:
            cursor.execute("UPDATE results SET place = ? WHERE id = ?", (place, result_id))
            place += 1

    conn.commit()


def assign_points(conn: sqlite3.Connection, event_id: int, scoring_type: str = 'dual'):
    """Assign points to results based on place and scoring type."""
    scoring = SCORING_TABLES.get(scoring_type, SCORING_TABLES['dual'])
    cursor = conn.cursor()

    # Check if event is relay
    cursor.execute("SELECT is_relay FROM events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    is_relay = row[0] if row else 0

    point_table = scoring['relay'] if is_relay else scoring['individual']

    # Get placed results
    cursor.execute("""
        SELECT r.id, r.place
        FROM results r
        JOIN heats h ON r.heat_id = h.id
        WHERE h.event_id = ? AND r.place IS NOT NULL
        ORDER BY r.place
    """, (event_id,))

    for result_id, place in cursor.fetchall():
        points = point_table[place - 1] if place <= len(point_table) else 0
        cursor.execute("UPDATE results SET points = ? WHERE id = ?", (points, result_id))

    conn.commit()


def check_records(conn: sqlite3.Connection, event_id: int) -> List[Dict]:
    """Check if any results in an event broke existing records."""
    cursor = conn.cursor()
    broken_records = []

    # Get existing records for this event
    cursor.execute("SELECT id, record_type, time FROM records WHERE event_id = ?", (event_id,))
    existing_records = cursor.fetchall()

    # Get results
    cursor.execute("""
        SELECT r.id, r.finish_time, s.name, t.team_code
        FROM results r
        JOIN entries e ON r.entry_id = e.id
        JOIN swimmers s ON e.swimmer_id = s.id
        JOIN teams t ON s.team_id = t.id
        JOIN heats h ON r.heat_id = h.id
        WHERE h.event_id = ? AND r.finish_time IS NOT NULL AND r.dq = 0
        ORDER BY r.finish_time
    """, (event_id,))

    results = cursor.fetchall()
    if not results:
        return broken_records

    fastest_id, fastest_time, fastest_name, fastest_team = results[0]

    for record_id, record_type, record_time in existing_records:
        if fastest_time < record_time:
            broken_records.append({
                'record_type': record_type,
                'old_time': record_time,
                'new_time': fastest_time,
                'swimmer_name': fastest_name,
                'team_code': fastest_team,
                'result_id': fastest_id,
            })
            # Update the record
            cursor.execute("""
                UPDATE records SET time = ?, swimmer_name = ?, team_code = ?, date_set = ?
                WHERE id = ?
            """, (fastest_time, fastest_name, fastest_team,
                  datetime.now().strftime('%Y-%m-%d'), record_id))
            # Mark result as record
            cursor.execute("""
                UPDATE results SET is_record = 1, record_type = ? WHERE id = ?
            """, (record_type, fastest_id))

    conn.commit()
    return broken_records


# ─── Team Scoring ──────────────────────────────────────────────────────

def get_team_scores(conn: sqlite3.Connection, scoring_type: str = 'dual') -> List[Dict]:
    """
    Calculate team scores across all events.

    Returns list of dicts sorted by total score descending:
        [{'team_code': 'SHARKS', 'team_name': 'Sharks SC',
          'boys': 50, 'girls': 45, 'total': 95}, ...]
    """
    cursor = conn.cursor()

    # Get all teams
    cursor.execute("SELECT id, team_code, team_name FROM teams ORDER BY team_code")
    teams = cursor.fetchall()

    scores = []
    for team_id, team_code, team_name in teams:
        # Get points for boys (M)
        cursor.execute("""
            SELECT COALESCE(SUM(r.points), 0)
            FROM results r
            JOIN entries e ON r.entry_id = e.id
            JOIN swimmers s ON e.swimmer_id = s.id
            WHERE s.team_id = ? AND s.gender = 'M' AND s.is_non_scoring = 0
        """, (team_id,))
        boys = cursor.fetchone()[0]

        # Get points for girls (F)
        cursor.execute("""
            SELECT COALESCE(SUM(r.points), 0)
            FROM results r
            JOIN entries e ON r.entry_id = e.id
            JOIN swimmers s ON e.swimmer_id = s.id
            WHERE s.team_id = ? AND s.gender = 'F' AND s.is_non_scoring = 0
        """, (team_id,))
        girls = cursor.fetchone()[0]

        # Get relay points
        cursor.execute("""
            SELECT COALESCE(SUM(rt.points), 0)
            FROM relay_teams rt
            WHERE rt.team_id = ?
        """, (team_id,))
        relay = cursor.fetchone()[0]

        total = boys + girls + relay
        if total > 0 or True:  # Include all teams
            scores.append({
                'team_code': team_code,
                'team_name': team_name,
                'boys': boys,
                'girls': girls,
                'relay': relay,
                'total': total,
            })

    scores.sort(key=lambda x: x['total'], reverse=True)
    return scores


# ─── Validation Engine ─────────────────────────────────────────────────

def get_validation_rule(conn: sqlite3.Connection, rule_name: str) -> Optional[str]:
    """Get a validation rule value."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT rule_value FROM validation_rules WHERE rule_name = ? AND enabled = 1",
        (rule_name,)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def validate_meet(conn: sqlite3.Connection) -> List[str]:
    """
    Validate meet data against configured rules.

    Returns list of violation strings (empty = all valid).
    """
    violations = []
    cursor = conn.cursor()

    # Check max individual entries
    max_entries_str = get_validation_rule(conn, 'max_individual_entries')
    if max_entries_str:
        max_entries = int(max_entries_str)
        cursor.execute("""
            SELECT s.name, COUNT(e.id) as entry_count
            FROM entries e
            JOIN swimmers s ON e.swimmer_id = s.id
            JOIN events ev ON e.event_id = ev.id
            WHERE ev.is_relay = 0
            GROUP BY e.swimmer_id
            HAVING entry_count > ?
        """, (max_entries,))
        for name, count in cursor.fetchall():
            violations.append(f"{name} has {count} individual entries (max: {max_entries})")

    # Check gender matching
    enforce_gender = get_validation_rule(conn, 'enforce_gender_match')
    if enforce_gender == '1':
        cursor.execute("""
            SELECT s.name, s.gender, ev.gender as event_gender, ev.number
            FROM entries e
            JOIN swimmers s ON e.swimmer_id = s.id
            JOIN events ev ON e.event_id = ev.id
            WHERE ev.gender NOT IN ('X', 'Mixed')
              AND s.gender IS NOT NULL
              AND s.gender != ev.gender
        """)
        for name, swimmer_gender, event_gender, event_num in cursor.fetchall():
            violations.append(
                f"{name} ({swimmer_gender}) entered in Event {event_num} ({event_gender})"
            )

    # Check age matching
    enforce_age = get_validation_rule(conn, 'enforce_age_match')
    if enforce_age == '1':
        cursor.execute("""
            SELECT s.name, s.age, ev.min_age, ev.max_age, ev.number
            FROM entries e
            JOIN swimmers s ON e.swimmer_id = s.id
            JOIN events ev ON e.event_id = ev.id
            WHERE ev.min_age IS NOT NULL AND ev.max_age IS NOT NULL
              AND s.age IS NOT NULL AND s.age > 0
              AND (s.age < ev.min_age OR s.age > ev.max_age)
        """)
        for name, age, min_age, max_age, event_num in cursor.fetchall():
            violations.append(
                f"{name} (age {age}) entered in Event {event_num} (ages {min_age}-{max_age})"
            )

    # Check seed times required
    require_seed = get_validation_rule(conn, 'require_seed_time')
    if require_seed == '1':
        cursor.execute("""
            SELECT s.name, ev.number
            FROM entries e
            JOIN swimmers s ON e.swimmer_id = s.id
            JOIN events ev ON e.event_id = ev.id
            WHERE e.seed_time IS NULL
        """)
        for name, event_num in cursor.fetchall():
            violations.append(f"{name} has no seed time in Event {event_num}")

    return violations


# ─── Meet Statistics ───────────────────────────────────────────────────

def get_meet_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Get comprehensive meet statistics.

    Returns dict with meet overview stats.
    """
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM swimmers")
    total_swimmers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM swimmers WHERE checked_in = 1")
    checked_in = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM events")
    total_events = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM events WHERE is_relay = 0")
    individual_events = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM events WHERE is_relay = 1")
    relay_events = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM entries")
    total_entries = cursor.fetchone()[0]

    # Events seeded (have heats)
    cursor.execute("SELECT COUNT(DISTINCT event_id) FROM heats")
    events_seeded = cursor.fetchone()[0]

    # Events with results
    cursor.execute("""
        SELECT COUNT(DISTINCT h.event_id)
        FROM results r
        JOIN heats h ON r.heat_id = h.id
        WHERE r.finish_time IS NOT NULL
    """)
    events_with_results = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM teams")
    total_teams = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM results WHERE finish_time IS NOT NULL")
    total_results = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM results WHERE dq = 1")
    total_dqs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM results WHERE ns = 1")
    total_ns = cursor.fetchone()[0]

    return {
        'total_swimmers': total_swimmers,
        'checked_in': checked_in,
        'total_events': total_events,
        'individual_events': individual_events,
        'relay_events': relay_events,
        'total_entries': total_entries,
        'events_seeded': events_seeded,
        'events_with_results': events_with_results,
        'total_teams': total_teams,
        'total_results': total_results,
        'total_dqs': total_dqs,
        'total_ns': total_ns,
    }


# ─── Undo/Redo System ─────────────────────────────────────────────────

MAX_UNDO_ENTRIES = 50

def save_undo_point(conn: sqlite3.Connection, action: str, table_name: str,
                    record_id: int = None, old_data: dict = None,
                    new_data: dict = None, description: str = None):
    """
    Save an undo point for reversible operations.

    Args:
        action: 'insert', 'update', or 'delete'
        table_name: Table that was modified
        record_id: ID of the affected record
        old_data: Data before the change (for update/delete)
        new_data: Data after the change (for insert/update)
        description: Human-readable description
    """
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO undo_log (action, table_name, record_id, old_data, new_data, description)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (action, table_name, record_id,
          json.dumps(old_data) if old_data else None,
          json.dumps(new_data) if new_data else None,
          description))

    # Trim old entries to keep only last MAX_UNDO_ENTRIES
    cursor.execute("""
        DELETE FROM undo_log WHERE id NOT IN (
            SELECT id FROM undo_log ORDER BY id DESC LIMIT ?
        )
    """, (MAX_UNDO_ENTRIES,))

    conn.commit()


def get_undo_history(conn: sqlite3.Connection, limit: int = 20) -> List[Dict]:
    """Get recent undo history entries."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, action, table_name, record_id, old_data, new_data, timestamp, description
        FROM undo_log
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    history = []
    for row in cursor.fetchall():
        history.append({
            'id': row[0],
            'action': row[1],
            'table_name': row[2],
            'record_id': row[3],
            'old_data': json.loads(row[4]) if row[4] else None,
            'new_data': json.loads(row[5]) if row[5] else None,
            'timestamp': row[6],
            'description': row[7],
        })
    return history


def undo_last_action(conn: sqlite3.Connection) -> Optional[str]:
    """
    Undo the most recent action.

    Returns description of what was undone, or None if nothing to undo.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id, action, table_name, record_id, old_data FROM undo_log ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()

    if not row:
        return None

    undo_id, action, table_name, record_id, old_data_json = row
    old_data = json.loads(old_data_json) if old_data_json else {}

    if action == 'insert' and record_id:
        cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (record_id,))
        desc = f"Undid insert into {table_name}"
    elif action == 'delete' and old_data:
        columns = ', '.join(old_data.keys())
        placeholders = ', '.join(['?'] * len(old_data))
        cursor.execute(
            f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})",
            list(old_data.values())
        )
        desc = f"Undid delete from {table_name}"
    elif action == 'update' and record_id and old_data:
        set_clause = ', '.join(f"{k} = ?" for k in old_data.keys() if k != 'id')
        values = [v for k, v in old_data.items() if k != 'id']
        values.append(record_id)
        cursor.execute(
            f"UPDATE {table_name} SET {set_clause} WHERE id = ?",
            values
        )
        desc = f"Undid update to {table_name}"
    else:
        desc = None

    # Remove the undo entry
    cursor.execute("DELETE FROM undo_log WHERE id = ?", (undo_id,))
    conn.commit()

    return desc


# ─── Backup System ─────────────────────────────────────────────────────

MAX_BACKUPS = 20

def create_backup(db_path: str, backup_dir: str = None) -> Optional[str]:
    """
    Create a backup of the meet database.

    Args:
        db_path: Path to the database file
        backup_dir: Directory for backups (default: ~/Documents/OpenSwimMeet/Backups)

    Returns:
        Path to backup file, or None on failure
    """
    try:
        if not Path(db_path).exists():
            return None

        if backup_dir is None:
            backup_dir = str(Path.home() / 'Documents' / 'OpenSwimMeet' / 'Backups')

        Path(backup_dir).mkdir(parents=True, exist_ok=True)

        db_name = Path(db_path).stem
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{db_name}_backup_{timestamp}.db"
        backup_path = str(Path(backup_dir) / backup_name)

        shutil.copy2(db_path, backup_path)

        # Rotate old backups
        _rotate_backups(backup_dir, db_name, MAX_BACKUPS)

        return backup_path

    except Exception as e:
        print(f"Backup failed: {e}")
        return None


def _rotate_backups(backup_dir: str, db_name: str, max_backups: int):
    """Remove old backups beyond the maximum count."""
    backup_path = Path(backup_dir)
    backups = sorted(
        backup_path.glob(f"{db_name}_backup_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    for old_backup in backups[max_backups:]:
        old_backup.unlink()


def list_backups(db_path: str, backup_dir: str = None) -> List[Dict]:
    """List available backups for a database."""
    if backup_dir is None:
        backup_dir = str(Path.home() / 'Documents' / 'OpenSwimMeet' / 'Backups')

    backup_path = Path(backup_dir)
    if not backup_path.exists():
        return []

    db_name = Path(db_path).stem
    backups = []

    for f in sorted(backup_path.glob(f"{db_name}_backup_*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
        backups.append({
            'path': str(f),
            'name': f.name,
            'size': f.stat().st_size,
            'modified': datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        })

    return backups


def restore_backup(backup_path: str, db_path: str) -> bool:
    """Restore a database from backup."""
    try:
        if not Path(backup_path).exists():
            return False
        # Create a backup of current state before restoring
        create_backup(db_path)
        shutil.copy2(backup_path, db_path)
        return True
    except Exception as e:
        print(f"Restore failed: {e}")
        return False


# ─── Announcements ─────────────────────────────────────────────────────

def add_announcement(conn: sqlite3.Connection, message: str, priority: int = 0,
                     event_id: int = None) -> int:
    """Add a meet announcement."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO announcements (message, priority, event_id) VALUES (?, ?, ?)",
        (message, priority, event_id)
    )
    conn.commit()
    return cursor.lastrowid


def get_announcements(conn: sqlite3.Connection, undisplayed_only: bool = False) -> List[Dict]:
    """Get meet announcements ordered by priority then time."""
    cursor = conn.cursor()
    query = "SELECT id, message, priority, created_at, displayed, event_id FROM announcements"
    if undisplayed_only:
        query += " WHERE displayed = 0"
    query += " ORDER BY priority DESC, created_at DESC"

    cursor.execute(query)
    return [
        {'id': r[0], 'message': r[1], 'priority': r[2],
         'created_at': r[3], 'displayed': r[4], 'event_id': r[5]}
        for r in cursor.fetchall()
    ]


def mark_announcement_displayed(conn: sqlite3.Connection, announcement_id: int):
    """Mark an announcement as displayed."""
    conn.execute("UPDATE announcements SET displayed = 1 WHERE id = ?", (announcement_id,))
    conn.commit()


# ─── Relay Management ─────────────────────────────────────────────────

def create_relay_team(conn: sqlite3.Connection, event_id: int, team_id: int,
                      relay_letter: str = 'A', seed_time: float = None) -> int:
    """
    Create a relay team entry for a relay event.

    Args:
        event_id: Must be a relay event (is_relay=1)
        team_id: Team that this relay belongs to
        relay_letter: A, B, C etc. for multiple relays per team
        seed_time: Seed time in seconds

    Returns:
        relay_team_id
    """
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO relay_teams (event_id, team_id, relay_letter, seed_time)
           VALUES (?, ?, ?, ?)""",
        (event_id, team_id, relay_letter, seed_time)
    )
    conn.commit()
    return cursor.lastrowid


def get_relay_teams(conn: sqlite3.Connection, event_id: int = None,
                    team_id: int = None) -> List[Dict]:
    """
    Get relay teams, optionally filtered by event and/or team.

    Returns list of dicts with relay team info including leg swimmers.
    """
    cursor = conn.cursor()
    query = """
        SELECT rt.id, rt.event_id, ev.number, ev.name, rt.team_id, t.team_code,
               t.team_name, rt.relay_letter, rt.seed_time, rt.finish_time,
               rt.place, rt.points, rt.dq, rt.dq_code, rt.heat_id, rt.lane
        FROM relay_teams rt
        JOIN events ev ON rt.event_id = ev.id
        JOIN teams t ON rt.team_id = t.id
        WHERE 1=1
    """
    params = []
    if event_id is not None:
        query += " AND rt.event_id = ?"
        params.append(event_id)
    if team_id is not None:
        query += " AND rt.team_id = ?"
        params.append(team_id)
    query += " ORDER BY ev.number, t.team_code, rt.relay_letter"

    cursor.execute(query, params)
    relay_teams = []
    for row in cursor.fetchall():
        rt = {
            'id': row[0], 'event_id': row[1], 'event_number': row[2],
            'event_name': row[3], 'team_id': row[4], 'team_code': row[5],
            'team_name': row[6], 'relay_letter': row[7], 'seed_time': row[8],
            'finish_time': row[9], 'place': row[10], 'points': row[11],
            'dq': row[12], 'dq_code': row[13], 'heat_id': row[14], 'lane': row[15],
        }
        # Fetch legs
        rt['legs'] = get_relay_legs(conn, row[0])
        relay_teams.append(rt)
    return relay_teams


def update_relay_team(conn: sqlite3.Connection, relay_team_id: int,
                      seed_time: float = None, relay_letter: str = None):
    """Update relay team seed time or letter."""
    cursor = conn.cursor()
    if seed_time is not None:
        cursor.execute("UPDATE relay_teams SET seed_time = ? WHERE id = ?",
                       (seed_time, relay_team_id))
    if relay_letter is not None:
        cursor.execute("UPDATE relay_teams SET relay_letter = ? WHERE id = ?",
                       (relay_letter, relay_team_id))
    conn.commit()


def delete_relay_team(conn: sqlite3.Connection, relay_team_id: int):
    """Delete a relay team and its leg assignments."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM relay_splits WHERE relay_team_id = ?", (relay_team_id,))
    cursor.execute("DELETE FROM relay_teams WHERE id = ?", (relay_team_id,))
    conn.commit()


def set_relay_legs(conn: sqlite3.Connection, relay_team_id: int,
                   legs: List[Dict]):
    """
    Set the swimmers for a relay team.

    Args:
        relay_team_id: The relay team to set legs for
        legs: List of dicts with keys: leg_number (1-4), swimmer_id, order_position (1-4)
              Example: [{'leg_number': 1, 'swimmer_id': 5, 'order_position': 1}, ...]
    """
    cursor = conn.cursor()
    # Clear existing legs
    cursor.execute("DELETE FROM relay_splits WHERE relay_team_id = ?", (relay_team_id,))

    for leg in legs:
        cursor.execute(
            """INSERT INTO relay_splits (relay_team_id, leg_number, swimmer_id,
                   split_time, order_position)
               VALUES (?, ?, ?, ?, ?)""",
            (relay_team_id, leg['leg_number'], leg['swimmer_id'],
             leg.get('split_time'), leg['order_position'])
        )
    conn.commit()


def get_relay_legs(conn: sqlite3.Connection, relay_team_id: int) -> List[Dict]:
    """Get the leg assignments for a relay team."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT rs.id, rs.leg_number, rs.swimmer_id, s.name, rs.split_time,
               rs.order_position
        FROM relay_splits rs
        JOIN swimmers s ON rs.swimmer_id = s.id
        WHERE rs.relay_team_id = ?
        ORDER BY rs.order_position
    """, (relay_team_id,))

    return [
        {'id': r[0], 'leg_number': r[1], 'swimmer_id': r[2],
         'swimmer_name': r[3], 'split_time': r[4], 'order_position': r[5]}
        for r in cursor.fetchall()
    ]


def save_relay_result(conn: sqlite3.Connection, relay_team_id: int,
                      finish_time: float = None, dq: bool = False,
                      dq_code: str = None, splits: List[Dict] = None) -> int:
    """
    Save result for a relay team.

    Args:
        relay_team_id: The relay team
        finish_time: Final time in seconds
        dq: Whether the relay was DQ'd
        dq_code: DQ code if applicable
        splits: Optional list of dicts with leg split times:
                [{'order_position': 1, 'split_time': 25.30}, ...]

    Returns:
        relay_team_id
    """
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE relay_teams SET finish_time = ?, dq = ?, dq_code = ?
        WHERE id = ?
    """, (finish_time, int(dq), dq_code, relay_team_id))

    # Update split times if provided
    if splits:
        for split in splits:
            cursor.execute("""
                UPDATE relay_splits SET split_time = ?
                WHERE relay_team_id = ? AND order_position = ?
            """, (split['split_time'], relay_team_id, split['order_position']))

    conn.commit()
    return relay_team_id


def calculate_relay_places(conn: sqlite3.Connection, event_id: int):
    """Calculate places for relay teams in an event."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, finish_time, dq
        FROM relay_teams
        WHERE event_id = ?
        ORDER BY
            CASE WHEN dq = 1 OR finish_time IS NULL THEN 1 ELSE 0 END,
            finish_time ASC
    """, (event_id,))

    place = 1
    for rt_id, finish_time, dq in cursor.fetchall():
        if dq or finish_time is None:
            cursor.execute("UPDATE relay_teams SET place = NULL WHERE id = ?", (rt_id,))
        else:
            cursor.execute("UPDATE relay_teams SET place = ? WHERE id = ?", (place, rt_id))
            place += 1
    conn.commit()


def assign_relay_points(conn: sqlite3.Connection, event_id: int,
                        scoring_type: str = 'dual'):
    """Assign points to relay teams based on place and scoring type."""
    scoring = SCORING_TABLES.get(scoring_type, SCORING_TABLES['dual'])
    point_table = scoring['relay']

    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, place FROM relay_teams
        WHERE event_id = ? AND place IS NOT NULL
        ORDER BY place
    """, (event_id,))

    for rt_id, place in cursor.fetchall():
        points = point_table[place - 1] if place <= len(point_table) else 0
        cursor.execute("UPDATE relay_teams SET points = ? WHERE id = ?", (points, rt_id))
    conn.commit()


def get_team_swimmers(conn: sqlite3.Connection, team_id: int,
                      gender: str = None) -> List[Dict]:
    """Get swimmers belonging to a team, optionally filtered by gender."""
    cursor = conn.cursor()
    query = "SELECT id, name, age, gender FROM swimmers WHERE team_id = ?"
    params = [team_id]
    if gender:
        query += " AND gender = ?"
        params.append(gender)
    query += " ORDER BY name"
    cursor.execute(query, params)
    return [
        {'id': r[0], 'name': r[1], 'age': r[2], 'gender': r[3]}
        for r in cursor.fetchall()
    ]


# ─── Check-in System ──────────────────────────────────────────────────

def check_in_swimmer(conn: sqlite3.Connection, swimmer_id: int) -> bool:
    """Mark a swimmer as checked in."""
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE swimmers SET checked_in = 1, check_in_time = ? WHERE id = ?",
        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), swimmer_id)
    )
    conn.commit()
    return cursor.rowcount > 0


def check_out_swimmer(conn: sqlite3.Connection, swimmer_id: int) -> bool:
    """Mark a swimmer as checked out."""
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE swimmers SET checked_in = 0, check_in_time = NULL WHERE id = ?",
        (swimmer_id,)
    )
    conn.commit()
    return cursor.rowcount > 0


def get_check_in_status(conn: sqlite3.Connection) -> Dict:
    """Get check-in status summary."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM swimmers")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM swimmers WHERE checked_in = 1")
    checked_in = cursor.fetchone()[0]
    return {
        'total': total,
        'checked_in': checked_in,
        'not_checked_in': total - checked_in,
    }
