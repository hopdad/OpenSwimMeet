"""
Tests for OpenSwimMeet - HY3 parser, database, seeding, utils, and enhanced features.
50+ comprehensive test cases.
"""
import pytest
import sys
import os
import tempfile
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hy3_parser import time_to_seconds, seconds_to_time_str, parse_hy3_file
from src.utils import calculate_age, format_time_input, validate_usas_id, format_meet_date
from src.database import (
    init_db, open_meet_db, get_or_insert_swimmer, get_or_insert_team,
    get_event_id, insert_or_update_entry, get_meet_setting, set_meet_setting,
    is_meet_completed, mark_meet_complete,
    save_result, calculate_places, assign_points,
    get_team_scores, validate_meet, get_meet_stats,
    save_undo_point, get_undo_history, undo_last_action,
    create_backup, list_backups,
    check_in_swimmer, check_out_swimmer, get_check_in_status,
    add_announcement, get_announcements, mark_announcement_displayed,
    get_validation_rule, check_records,
    create_relay_team, get_relay_teams, update_relay_team, delete_relay_team,
    set_relay_legs, get_relay_legs, save_relay_result,
    calculate_relay_places, assign_relay_points, get_team_swimmers,
    SCORING_TABLES, DQ_CODES, SCHEMA_VERSION,
)
from src.seeding import apply_seeding, get_heat_sheet, apply_relay_seeding, get_relay_heat_sheet


class DBWrapper:
    """Wrapper around sqlite3.Connection that also stores db_path."""
    def __init__(self, conn, db_path):
        self._conn = conn
        self.db_path = db_path
    def __getattr__(self, name):
        return getattr(self._conn, name)


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    conn = init_db(db_path)
    wrapper = DBWrapper(conn, db_path)
    yield wrapper
    conn.close()
    os.unlink(db_path)


@pytest.fixture
def populated_db(db):
    """Create a database with sample data."""
    cursor = db.cursor()

    # Create events
    events = [
        (1, 'Boys 50 Free', 50, 'FREE', 'M'),
        (2, 'Girls 50 Free', 50, 'FREE', 'F'),
        (3, 'Boys 100 Back', 100, 'BACK', 'M'),
        (4, 'Girls 100 Breast', 100, 'BREAST', 'F'),
    ]
    for num, name, dist, stroke, gender in events:
        cursor.execute(
            "INSERT INTO events (number, name, distance, stroke, gender) VALUES (?,?,?,?,?)",
            (num, name, dist, stroke, gender))

    # Create teams and swimmers
    team1_id = get_or_insert_team(db, 'SHRK', 'Sharks SC')
    team2_id = get_or_insert_team(db, 'DOLP', 'Dolphins AC')

    swimmers = [
        ('Smith, John', 'SHRK', 'Sharks SC', 15, 'M'),
        ('Doe, Jane', 'SHRK', 'Sharks SC', 14, 'F'),
        ('Brown, Mike', 'DOLP', 'Dolphins AC', 16, 'M'),
        ('Wilson, Amy', 'DOLP', 'Dolphins AC', 15, 'F'),
        ('Lee, Tom', 'SHRK', 'Sharks SC', 13, 'M'),
        ('Garcia, Sara', 'DOLP', 'Dolphins AC', 14, 'F'),
    ]
    swimmer_ids = []
    for name, tc, tn, age, gender in swimmers:
        sid = get_or_insert_swimmer(db, name, tc, tn, age=age, gender=gender)
        swimmer_ids.append(sid)

    # Create entries
    entries_data = [
        (swimmer_ids[0], 1, 24.50),  # Smith -> Boys 50 Free
        (swimmer_ids[2], 1, 25.10),  # Brown -> Boys 50 Free
        (swimmer_ids[4], 1, 26.30),  # Lee -> Boys 50 Free
        (swimmer_ids[1], 2, 28.00),  # Doe -> Girls 50 Free
        (swimmer_ids[3], 2, 27.50),  # Wilson -> Girls 50 Free
        (swimmer_ids[5], 2, 29.10),  # Garcia -> Girls 50 Free
    ]
    for sid, eid, seed in entries_data:
        insert_or_update_entry(db, sid, eid, seed)

    set_meet_setting(db, 'meet_name', 'Test Meet')
    set_meet_setting(db, 'meet_date', '2026-02-07')
    set_meet_setting(db, 'course', 'SCY')
    set_meet_setting(db, 'lanes', '6')
    set_meet_setting(db, 'scoring_type', 'dual')

    db.commit()
    db.swimmer_ids = swimmer_ids
    return db


# ─── Time Conversion Tests ────────────────────────────────────────────

class TestTimeConversion:
    def test_time_to_seconds_simple(self):
        assert time_to_seconds("23.45") == 23.45
        assert time_to_seconds("59.99") == 59.99

    def test_time_to_seconds_minutes(self):
        assert time_to_seconds("1:23.45") == 83.45
        assert time_to_seconds("2:15.67") == 135.67

    def test_time_to_seconds_hours(self):
        assert time_to_seconds("1:05:23.45") == 3923.45

    def test_time_to_seconds_nt(self):
        assert time_to_seconds("NT") is None
        assert time_to_seconds("nt") is None
        assert time_to_seconds("") is None
        assert time_to_seconds("  ") is None

    def test_time_to_seconds_invalid(self):
        assert time_to_seconds("abc") is None
        assert time_to_seconds("1:2:3:4") is None

    def test_seconds_to_time_str(self):
        assert seconds_to_time_str(23.45) == "23.45"
        assert seconds_to_time_str(83.45) == "1:23.45"
        assert seconds_to_time_str(None) == "NT"

    def test_seconds_to_time_str_zero(self):
        assert seconds_to_time_str(0.0) == "0.00"

    def test_roundtrip_conversion(self):
        times = ["1:23.45", "59.99", "2:15.67"]
        for time_str in times:
            seconds = time_to_seconds(time_str)
            converted = seconds_to_time_str(seconds)
            assert abs(time_to_seconds(converted) - time_to_seconds(time_str)) < 0.01


# ─── HY3 Parser Tests ─────────────────────────────────────────────────

class TestHY3Parser:
    def test_parse_sample_file(self):
        sample_path = Path(__file__).parent.parent / 'resources' / 'sample_data' / 'SAMPLE.hy3'
        if not sample_path.exists():
            pytest.skip("Sample file not found")
        result = parse_hy3_file(str(sample_path))
        assert 'swimmers' in result
        assert 'entries' in result
        assert len(result['swimmers']) > 0
        assert len(result['entries']) > 0

    def test_parse_nonexistent_file(self):
        result = parse_hy3_file('/nonexistent/file.hy3')
        assert result['swimmers'] == []
        assert 'errors' in result

    def test_parse_result_structure(self):
        sample_path = Path(__file__).parent.parent / 'resources' / 'sample_data' / 'SAMPLE.hy3'
        if not sample_path.exists():
            pytest.skip("Sample file not found")
        result = parse_hy3_file(str(sample_path))
        if result['swimmers']:
            swimmer = result['swimmers'][0]
            assert 'name' in swimmer
            assert 'team_code' in swimmer
            assert 'team_name' in swimmer


# ─── Utils Tests ───────────────────────────────────────────────────────

class TestUtils:
    def test_calculate_age_before_birthday(self):
        age = calculate_age('20080515', '2024-01-15')
        assert age == 15

    def test_calculate_age_after_birthday(self):
        age = calculate_age('20080515', '2024-06-15')
        assert age == 16

    def test_calculate_age_yyyymmdd_format(self):
        age = calculate_age('20100301', '20240301')
        assert age == 14

    def test_calculate_age_invalid(self):
        assert calculate_age('invalid', '2024-01-01') == 0

    def test_validate_usas_id_valid(self):
        assert validate_usas_id('123456789012') is True
        assert validate_usas_id('1234567890') is True
        assert validate_usas_id('12345678901234') is True

    def test_validate_usas_id_invalid(self):
        assert validate_usas_id('abc123') is False
        assert validate_usas_id('123') is False

    def test_validate_usas_id_empty(self):
        assert validate_usas_id('') is True
        assert validate_usas_id(None) is True

    def test_format_meet_date(self):
        result = format_meet_date('2024-06-15')
        assert 'June' in result
        assert '15' in result

    def test_format_meet_date_yyyymmdd(self):
        result = format_meet_date('20240615')
        assert 'June' in result


# ─── Database Schema Tests ─────────────────────────────────────────────

class TestDatabaseSchema:
    def test_init_db_creates_all_tables(self, db):
        cursor = db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = sorted([row[0] for row in cursor.fetchall()])

        expected = sorted([
            'schema_version', 'teams', 'events', 'swimmers', 'entries',
            'heats', 'heat_assignments', 'results', 'relay_teams',
            'relay_splits', 'records', 'validation_rules', 'undo_log',
            'announcements', 'meet_settings'
        ])
        for table in expected:
            assert table in tables, f"Missing table: {table}"

    def test_schema_version(self, db):
        cursor = db.cursor()
        cursor.execute("SELECT MAX(version) FROM schema_version")
        version = cursor.fetchone()[0]
        assert version == SCHEMA_VERSION

    def test_default_validation_rules(self, db):
        val = get_validation_rule(db, 'max_individual_entries')
        assert val == '3'
        val = get_validation_rule(db, 'enforce_gender_match')
        assert val == '1'

    def test_teams_enhanced_columns(self, db):
        cursor = db.cursor()
        cursor.execute("PRAGMA table_info(teams)")
        columns = [row[1] for row in cursor.fetchall()]
        assert 'team_color2' in columns
        assert 'coach_name' in columns
        assert 'coach_email' in columns

    def test_swimmers_enhanced_columns(self, db):
        cursor = db.cursor()
        cursor.execute("PRAGMA table_info(swimmers)")
        columns = [row[1] for row in cursor.fetchall()]
        assert 'checked_in' in columns
        assert 'is_relay_only' in columns
        assert 'photo_path' in columns

    def test_results_enhanced_columns(self, db):
        cursor = db.cursor()
        cursor.execute("PRAGMA table_info(results)")
        columns = [row[1] for row in cursor.fetchall()]
        assert 'dq_code' in columns
        assert 'reaction_time' in columns
        assert 'is_personal_best' in columns
        assert 'is_record' in columns


# ─── Database CRUD Tests ──────────────────────────────────────────────

class TestDatabaseCRUD:
    def test_get_or_insert_team(self, db):
        team_id = get_or_insert_team(db, 'TEST', 'Test Team')
        assert team_id > 0
        # Insert same team again should return same ID
        team_id2 = get_or_insert_team(db, 'TEST', 'Test Team')
        assert team_id == team_id2

    def test_get_or_insert_swimmer(self, db):
        sid = get_or_insert_swimmer(db, 'Test Swimmer', 'TST', 'Test Team', age=15, gender='M')
        assert sid > 0

    def test_get_or_insert_swimmer_by_usas(self, db):
        sid1 = get_or_insert_swimmer(db, 'Swimmer A', 'TST', usas_id='123456789012', age=15, gender='M')
        sid2 = get_or_insert_swimmer(db, 'Swimmer A Updated', 'TST', usas_id='123456789012', age=16, gender='M')
        assert sid1 == sid2  # Same swimmer via USAS ID

    def test_insert_or_update_entry(self, db):
        cursor = db.cursor()
        cursor.execute("INSERT INTO events (number, name, distance, stroke, gender) VALUES (1,'50 Free',50,'FREE','M')")
        event_id = cursor.lastrowid
        sid = get_or_insert_swimmer(db, 'Test', 'TST', age=15, gender='M')
        insert_or_update_entry(db, sid, event_id, 25.50)
        cursor.execute("SELECT seed_time FROM entries WHERE swimmer_id = ? AND event_id = ?", (sid, event_id))
        assert cursor.fetchone()[0] == 25.50
        # Update
        insert_or_update_entry(db, sid, event_id, 24.00)
        cursor.execute("SELECT seed_time FROM entries WHERE swimmer_id = ? AND event_id = ?", (sid, event_id))
        assert cursor.fetchone()[0] == 24.00

    def test_get_event_id(self, db):
        cursor = db.cursor()
        cursor.execute("INSERT INTO events (number, name, distance, stroke, gender) VALUES (99,'Test',50,'FREE','M')")
        db.commit()
        eid = get_event_id(db, 99)
        assert eid is not None
        assert get_event_id(db, 999) is None


# ─── Meet Settings Tests ──────────────────────────────────────────────

class TestMeetSettings:
    def test_set_and_get(self, db):
        set_meet_setting(db, 'test_key', 'test_value')
        assert get_meet_setting(db, 'test_key') == 'test_value'

    def test_get_default(self, db):
        assert get_meet_setting(db, 'nonexistent', 'default') == 'default'

    def test_meet_completion(self, db):
        assert is_meet_completed(db) is False
        mark_meet_complete(db, True)
        assert is_meet_completed(db) is True
        mark_meet_complete(db, False)
        assert is_meet_completed(db) is False


# ─── Seeding Tests ─────────────────────────────────────────────────────

class TestSeeding:
    def test_circle_seeding(self, populated_db):
        event_id = get_event_id(populated_db, 1)
        num_heats = apply_seeding(populated_db, event_id, method='circle', lanes=6)
        assert num_heats == 1  # 3 swimmers fits in 1 heat of 6

        cursor = populated_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM heat_assignments")
        assert cursor.fetchone()[0] == 3

    def test_straight_seeding(self, populated_db):
        event_id = get_event_id(populated_db, 1)
        num_heats = apply_seeding(populated_db, event_id, method='straight', lanes=6)
        assert num_heats >= 1

    def test_seeding_empty_event(self, populated_db):
        event_id = get_event_id(populated_db, 3)  # Boys 100 Back - no entries
        num_heats = apply_seeding(populated_db, event_id, lanes=6)
        assert num_heats == 0

    def test_get_heat_sheet(self, populated_db):
        event_id = get_event_id(populated_db, 1)
        apply_seeding(populated_db, event_id, lanes=6)
        sheet = get_heat_sheet(populated_db, event_id)
        assert len(sheet) == 3
        assert 'heat' in sheet[0]
        assert 'lane' in sheet[0]
        assert 'name' in sheet[0]

    def test_multiple_heats(self, db):
        cursor = db.cursor()
        cursor.execute("INSERT INTO events (number, name, distance, stroke, gender) VALUES (1,'50 Free',50,'FREE','M')")
        event_id = cursor.lastrowid
        for i in range(15):
            sid = get_or_insert_swimmer(db, f"Swimmer {i}", "TST", age=15, gender='M')
            insert_or_update_entry(db, sid, event_id, 25.0 + i * 0.1)
        num_heats = apply_seeding(db, event_id, lanes=6)
        assert num_heats == 3  # 15 swimmers / 6 lanes = 3 heats


# ─── Results Tests ─────────────────────────────────────────────────────

class TestResults:
    def test_save_result(self, populated_db):
        event_id = get_event_id(populated_db, 1)
        apply_seeding(populated_db, event_id, lanes=6)

        cursor = populated_db.cursor()
        cursor.execute("""
            SELECT ha.entry_id, ha.heat_id, ha.lane
            FROM heat_assignments ha
            JOIN heats h ON ha.heat_id = h.id
            WHERE h.event_id = ?
            LIMIT 1
        """, (event_id,))
        entry_id, heat_id, lane = cursor.fetchone()

        result_id = save_result(populated_db, entry_id, heat_id, lane, finish_time=24.30)
        assert result_id > 0

        cursor.execute("SELECT finish_time FROM results WHERE id = ?", (result_id,))
        assert cursor.fetchone()[0] == 24.30

    def test_save_result_dq(self, populated_db):
        event_id = get_event_id(populated_db, 1)
        apply_seeding(populated_db, event_id, lanes=6)

        cursor = populated_db.cursor()
        cursor.execute("""
            SELECT ha.entry_id, ha.heat_id, ha.lane
            FROM heat_assignments ha JOIN heats h ON ha.heat_id = h.id
            WHERE h.event_id = ? LIMIT 1
        """, (event_id,))
        entry_id, heat_id, lane = cursor.fetchone()

        save_result(populated_db, entry_id, heat_id, lane, dq=True, dq_code='FA')
        cursor.execute("SELECT dq, dq_code, dq_description FROM results WHERE entry_id = ?", (entry_id,))
        row = cursor.fetchone()
        assert row[0] == 1
        assert row[1] == 'FA'
        assert row[2] == 'False start'

    def test_calculate_places(self, populated_db):
        event_id = get_event_id(populated_db, 1)
        apply_seeding(populated_db, event_id, lanes=6)

        cursor = populated_db.cursor()
        cursor.execute("""
            SELECT ha.entry_id, ha.heat_id, ha.lane
            FROM heat_assignments ha JOIN heats h ON ha.heat_id = h.id
            WHERE h.event_id = ? ORDER BY ha.lane
        """, (event_id,))
        assignments = cursor.fetchall()

        times = [24.30, 25.10, 26.50]
        for i, (entry_id, heat_id, lane) in enumerate(assignments):
            save_result(populated_db, entry_id, heat_id, lane, finish_time=times[i])

        calculate_places(populated_db, event_id)

        cursor.execute("""
            SELECT r.place FROM results r
            JOIN heats h ON r.heat_id = h.id
            WHERE h.event_id = ? AND r.place IS NOT NULL
            ORDER BY r.place
        """, (event_id,))
        places = [r[0] for r in cursor.fetchall()]
        assert places == [1, 2, 3]

    def test_assign_points_dual(self, populated_db):
        event_id = get_event_id(populated_db, 1)
        apply_seeding(populated_db, event_id, lanes=6)

        cursor = populated_db.cursor()
        cursor.execute("""
            SELECT ha.entry_id, ha.heat_id, ha.lane
            FROM heat_assignments ha JOIN heats h ON ha.heat_id = h.id
            WHERE h.event_id = ? ORDER BY ha.lane
        """, (event_id,))
        assignments = cursor.fetchall()

        for i, (entry_id, heat_id, lane) in enumerate(assignments):
            save_result(populated_db, entry_id, heat_id, lane, finish_time=24.0 + i)

        calculate_places(populated_db, event_id)
        assign_points(populated_db, event_id, 'dual')

        cursor.execute("""
            SELECT r.points FROM results r
            JOIN heats h ON r.heat_id = h.id
            WHERE h.event_id = ?
            ORDER BY r.place
        """, (event_id,))
        points = [r[0] for r in cursor.fetchall()]
        assert points == [5, 3, 1]  # Dual scoring: 5-3-1


# ─── Team Scoring Tests ───────────────────────────────────────────────

class TestTeamScoring:
    def test_get_team_scores_empty(self, populated_db):
        scores = get_team_scores(populated_db, 'dual')
        assert isinstance(scores, list)
        assert len(scores) == 2  # Two teams
        assert all(s['total'] == 0 for s in scores)

    def test_get_team_scores_with_results(self, populated_db):
        event_id = get_event_id(populated_db, 1)
        apply_seeding(populated_db, event_id, lanes=6)

        cursor = populated_db.cursor()
        cursor.execute("""
            SELECT ha.entry_id, ha.heat_id, ha.lane
            FROM heat_assignments ha JOIN heats h ON ha.heat_id = h.id
            WHERE h.event_id = ? ORDER BY ha.lane
        """, (event_id,))

        for i, (entry_id, heat_id, lane) in enumerate(cursor.fetchall()):
            save_result(populated_db, entry_id, heat_id, lane, finish_time=24.0 + i)

        calculate_places(populated_db, event_id)
        assign_points(populated_db, event_id, 'dual')

        scores = get_team_scores(populated_db, 'dual')
        total_points = sum(s['total'] for s in scores)
        assert total_points == 9  # 5 + 3 + 1

    def test_scoring_tables_exist(self):
        assert 'dual' in SCORING_TABLES
        assert 'invitational' in SCORING_TABLES
        assert 'championship' in SCORING_TABLES


# ─── Validation Tests ─────────────────────────────────────────────────

class TestValidation:
    def test_validate_clean_meet(self, populated_db):
        violations = validate_meet(populated_db)
        assert isinstance(violations, list)
        assert len(violations) == 0  # No violations in properly set up meet

    def test_validate_max_entries(self, db):
        cursor = db.cursor()
        for i in range(1, 6):
            cursor.execute(
                "INSERT INTO events (number, name, distance, stroke, gender) VALUES (?,?,50,'FREE','M')",
                (i, f'Event {i}'))
        db.commit()

        sid = get_or_insert_swimmer(db, 'Over-Entered', 'TST', age=15, gender='M')
        for i in range(1, 5):
            eid = get_event_id(db, i)
            insert_or_update_entry(db, sid, eid, 25.0)

        violations = validate_meet(db)
        assert any('4 individual entries' in v for v in violations)

    def test_validate_gender_mismatch(self, populated_db):
        # Male swimmer entered in female event
        event_id = get_event_id(populated_db, 2)  # Girls event
        sid = populated_db.swimmer_ids[0]  # Male swimmer
        insert_or_update_entry(populated_db, sid, event_id, 28.0)

        violations = validate_meet(populated_db)
        assert any('(M)' in v and 'Event 2' in v for v in violations)


# ─── Meet Statistics Tests ─────────────────────────────────────────────

class TestMeetStats:
    def test_get_meet_stats(self, populated_db):
        stats = get_meet_stats(populated_db)
        assert stats['total_swimmers'] == 6
        assert stats['total_events'] == 4
        assert stats['total_teams'] == 2
        assert stats['total_entries'] == 6

    def test_stats_after_seeding(self, populated_db):
        event_id = get_event_id(populated_db, 1)
        apply_seeding(populated_db, event_id, lanes=6)
        stats = get_meet_stats(populated_db)
        assert stats['events_seeded'] == 1


# ─── Undo/Redo Tests ──────────────────────────────────────────────────

class TestUndoRedo:
    def test_save_undo_point(self, db):
        save_undo_point(db, 'insert', 'swimmers', 1,
                        new_data={'name': 'Test'}, description='Added test swimmer')
        history = get_undo_history(db, limit=5)
        assert len(history) == 1
        assert history[0]['action'] == 'insert'
        assert history[0]['description'] == 'Added test swimmer'

    def test_undo_insert(self, db):
        sid = get_or_insert_swimmer(db, 'Undo Test', 'TST', age=15, gender='M')
        save_undo_point(db, 'insert', 'swimmers', sid, description='Added swimmer')

        result = undo_last_action(db)
        assert result is not None
        assert 'Undid insert' in result

        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM swimmers WHERE id = ?", (sid,))
        assert cursor.fetchone()[0] == 0

    def test_undo_empty(self, db):
        result = undo_last_action(db)
        assert result is None

    def test_undo_history_limit(self, db):
        for i in range(10):
            save_undo_point(db, 'insert', 'test', i, description=f'Action {i}')
        history = get_undo_history(db, limit=5)
        assert len(history) == 5


# ─── Backup Tests ─────────────────────────────────────────────────────

class TestBackup:
    def test_create_backup(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_path = create_backup(db.db_path, backup_dir=tmpdir)
            assert backup_path is not None
            assert Path(backup_path).exists()

    def test_list_backups(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            create_backup(db.db_path, backup_dir=tmpdir)
            create_backup(db.db_path, backup_dir=tmpdir)
            backups = list_backups(db.db_path, backup_dir=tmpdir)
            assert len(backups) >= 1

    def test_backup_nonexistent(self):
        result = create_backup('/nonexistent/db.db')
        assert result is None


# ─── Check-in Tests ────────────────────────────────────────────────────

class TestCheckIn:
    def test_check_in_swimmer(self, populated_db):
        sid = populated_db.swimmer_ids[0]
        assert check_in_swimmer(populated_db, sid) is True

        cursor = populated_db.cursor()
        cursor.execute("SELECT checked_in, check_in_time FROM swimmers WHERE id = ?", (sid,))
        row = cursor.fetchone()
        assert row[0] == 1
        assert row[1] is not None

    def test_check_out_swimmer(self, populated_db):
        sid = populated_db.swimmer_ids[0]
        check_in_swimmer(populated_db, sid)
        check_out_swimmer(populated_db, sid)

        cursor = populated_db.cursor()
        cursor.execute("SELECT checked_in FROM swimmers WHERE id = ?", (sid,))
        assert cursor.fetchone()[0] == 0

    def test_check_in_status(self, populated_db):
        check_in_swimmer(populated_db, populated_db.swimmer_ids[0])
        check_in_swimmer(populated_db, populated_db.swimmer_ids[1])

        status = get_check_in_status(populated_db)
        assert status['total'] == 6
        assert status['checked_in'] == 2
        assert status['not_checked_in'] == 4


# ─── Announcements Tests ──────────────────────────────────────────────

class TestAnnouncements:
    def test_add_announcement(self, db):
        aid = add_announcement(db, 'Test announcement', priority=1)
        assert aid > 0

    def test_get_announcements(self, db):
        add_announcement(db, 'Low priority', priority=0)
        add_announcement(db, 'High priority', priority=5)
        anns = get_announcements(db)
        assert len(anns) == 2
        assert anns[0]['priority'] >= anns[1]['priority']  # Sorted by priority desc

    def test_mark_displayed(self, db):
        aid = add_announcement(db, 'Display test')
        mark_announcement_displayed(db, aid)
        anns = get_announcements(db, undisplayed_only=True)
        assert len(anns) == 0


# ─── Records Tests ─────────────────────────────────────────────────────

class TestRecords:
    def test_check_records_no_records(self, populated_db):
        event_id = get_event_id(populated_db, 1)
        apply_seeding(populated_db, event_id, lanes=6)
        broken = check_records(populated_db, event_id)
        assert broken == []

    def test_check_records_broken(self, populated_db):
        event_id = get_event_id(populated_db, 1)
        apply_seeding(populated_db, event_id, lanes=6)

        # Add a pool record
        cursor = populated_db.cursor()
        cursor.execute("""
            INSERT INTO records (record_type, event_id, swimmer_name, team_code, time, course)
            VALUES ('pool', ?, 'Old Record', 'OLD', 30.00, 'SCY')
        """, (event_id,))
        populated_db.commit()

        # Enter results faster than record
        cursor.execute("""
            SELECT ha.entry_id, ha.heat_id, ha.lane
            FROM heat_assignments ha JOIN heats h ON ha.heat_id = h.id
            WHERE h.event_id = ? LIMIT 1
        """, (event_id,))
        entry_id, heat_id, lane = cursor.fetchone()
        save_result(populated_db, entry_id, heat_id, lane, finish_time=24.50)

        broken = check_records(populated_db, event_id)
        assert len(broken) == 1
        assert broken[0]['record_type'] == 'pool'
        assert broken[0]['new_time'] == 24.50


# ─── DQ Codes Tests ───────────────────────────────────────────────────

class TestDQCodes:
    def test_dq_codes_defined(self):
        assert 'FA' in DQ_CODES
        assert 'NS' in DQ_CODES
        assert DQ_CODES['FA'] == 'False start'

    def test_all_dq_codes_have_descriptions(self):
        for code, desc in DQ_CODES.items():
            assert isinstance(code, str) and len(code) == 2
            assert isinstance(desc, str) and len(desc) > 0


# ─── Relay Fixture ────────────────────────────────────────────────────

@pytest.fixture
def relay_db(populated_db):
    """Extend populated_db with relay events and teams."""
    cursor = populated_db.cursor()

    # Add relay events
    cursor.execute(
        "INSERT INTO events (number, name, distance, stroke, gender, is_relay) VALUES (?,?,?,?,?,?)",
        (5, 'Boys 200 Free Relay', 200, 'FREE', 'M', 1))
    relay_event_id = cursor.lastrowid

    cursor.execute(
        "INSERT INTO events (number, name, distance, stroke, gender, is_relay) VALUES (?,?,?,?,?,?)",
        (6, 'Girls 200 Medley Relay', 200, 'IM', 'F', 1))

    # Get team IDs
    cursor.execute("SELECT id FROM teams WHERE team_code = 'SHRK'")
    shrk_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM teams WHERE team_code = 'DOLP'")
    dolp_id = cursor.fetchone()[0]

    populated_db.commit()
    populated_db.relay_event_id = relay_event_id
    populated_db.shrk_id = shrk_id
    populated_db.dolp_id = dolp_id
    return populated_db


# ─── Relay CRUD Tests ─────────────────────────────────────────────────

class TestRelayCRUD:
    def test_create_relay_team(self, relay_db):
        rt_id = create_relay_team(relay_db, relay_db.relay_event_id,
                                   relay_db.shrk_id, relay_letter='A', seed_time=95.50)
        assert rt_id > 0

        rts = get_relay_teams(relay_db, event_id=relay_db.relay_event_id)
        assert len(rts) == 1
        assert rts[0]['team_code'] == 'SHRK'
        assert rts[0]['relay_letter'] == 'A'
        assert rts[0]['seed_time'] == 95.50

    def test_create_multiple_relay_teams(self, relay_db):
        create_relay_team(relay_db, relay_db.relay_event_id, relay_db.shrk_id, 'A', 95.50)
        create_relay_team(relay_db, relay_db.relay_event_id, relay_db.shrk_id, 'B', 102.00)
        create_relay_team(relay_db, relay_db.relay_event_id, relay_db.dolp_id, 'A', 97.20)

        rts = get_relay_teams(relay_db, event_id=relay_db.relay_event_id)
        assert len(rts) == 3

    def test_get_relay_teams_by_team(self, relay_db):
        create_relay_team(relay_db, relay_db.relay_event_id, relay_db.shrk_id, 'A')
        create_relay_team(relay_db, relay_db.relay_event_id, relay_db.dolp_id, 'A')

        rts = get_relay_teams(relay_db, team_id=relay_db.shrk_id)
        assert len(rts) == 1
        assert rts[0]['team_code'] == 'SHRK'

    def test_update_relay_team(self, relay_db):
        rt_id = create_relay_team(relay_db, relay_db.relay_event_id,
                                   relay_db.shrk_id, 'A', 95.50)
        update_relay_team(relay_db, rt_id, seed_time=93.00, relay_letter='B')

        rts = get_relay_teams(relay_db, event_id=relay_db.relay_event_id)
        assert rts[0]['seed_time'] == 93.00
        assert rts[0]['relay_letter'] == 'B'

    def test_delete_relay_team(self, relay_db):
        rt_id = create_relay_team(relay_db, relay_db.relay_event_id,
                                   relay_db.shrk_id, 'A')
        delete_relay_team(relay_db, rt_id)

        rts = get_relay_teams(relay_db, event_id=relay_db.relay_event_id)
        assert len(rts) == 0


# ─── Relay Legs Tests ─────────────────────────────────────────────────

class TestRelayLegs:
    def test_set_and_get_legs(self, relay_db):
        rt_id = create_relay_team(relay_db, relay_db.relay_event_id,
                                   relay_db.shrk_id, 'A')
        sids = relay_db.swimmer_ids
        # Use SHRK swimmers: Smith (0), Doe (1), Lee (4)
        legs = [
            {'leg_number': 1, 'swimmer_id': sids[0], 'order_position': 1},
            {'leg_number': 2, 'swimmer_id': sids[1], 'order_position': 2},
            {'leg_number': 3, 'swimmer_id': sids[4], 'order_position': 3},
        ]
        set_relay_legs(relay_db, rt_id, legs)

        result = get_relay_legs(relay_db, rt_id)
        assert len(result) == 3
        assert result[0]['swimmer_name'] == 'Smith, John'
        assert result[0]['order_position'] == 1
        assert result[1]['order_position'] == 2

    def test_replace_legs(self, relay_db):
        rt_id = create_relay_team(relay_db, relay_db.relay_event_id,
                                   relay_db.shrk_id, 'A')
        sids = relay_db.swimmer_ids

        # Set initial legs
        set_relay_legs(relay_db, rt_id, [
            {'leg_number': 1, 'swimmer_id': sids[0], 'order_position': 1},
        ])
        assert len(get_relay_legs(relay_db, rt_id)) == 1

        # Replace with new legs
        set_relay_legs(relay_db, rt_id, [
            {'leg_number': 1, 'swimmer_id': sids[0], 'order_position': 1},
            {'leg_number': 2, 'swimmer_id': sids[1], 'order_position': 2},
        ])
        assert len(get_relay_legs(relay_db, rt_id)) == 2

    def test_legs_with_split_times(self, relay_db):
        rt_id = create_relay_team(relay_db, relay_db.relay_event_id,
                                   relay_db.shrk_id, 'A')
        sids = relay_db.swimmer_ids
        legs = [
            {'leg_number': 1, 'swimmer_id': sids[0], 'order_position': 1, 'split_time': 24.50},
            {'leg_number': 2, 'swimmer_id': sids[1], 'order_position': 2, 'split_time': 26.30},
        ]
        set_relay_legs(relay_db, rt_id, legs)

        result = get_relay_legs(relay_db, rt_id)
        assert result[0]['split_time'] == 24.50
        assert result[1]['split_time'] == 26.30

    def test_legs_included_in_relay_teams(self, relay_db):
        """Verify get_relay_teams includes leg data."""
        rt_id = create_relay_team(relay_db, relay_db.relay_event_id,
                                   relay_db.shrk_id, 'A')
        sids = relay_db.swimmer_ids
        set_relay_legs(relay_db, rt_id, [
            {'leg_number': 1, 'swimmer_id': sids[0], 'order_position': 1},
            {'leg_number': 2, 'swimmer_id': sids[4], 'order_position': 2},
        ])

        rts = get_relay_teams(relay_db, event_id=relay_db.relay_event_id)
        assert len(rts[0]['legs']) == 2

    def test_delete_relay_clears_legs(self, relay_db):
        rt_id = create_relay_team(relay_db, relay_db.relay_event_id,
                                   relay_db.shrk_id, 'A')
        sids = relay_db.swimmer_ids
        set_relay_legs(relay_db, rt_id, [
            {'leg_number': 1, 'swimmer_id': sids[0], 'order_position': 1},
        ])
        delete_relay_team(relay_db, rt_id)

        cursor = relay_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM relay_splits WHERE relay_team_id = ?", (rt_id,))
        assert cursor.fetchone()[0] == 0


# ─── Relay Results Tests ──────────────────────────────────────────────

class TestRelayResults:
    def test_save_relay_result(self, relay_db):
        rt_id = create_relay_team(relay_db, relay_db.relay_event_id,
                                   relay_db.shrk_id, 'A', seed_time=95.50)
        save_relay_result(relay_db, rt_id, finish_time=94.20)

        rts = get_relay_teams(relay_db, event_id=relay_db.relay_event_id)
        assert rts[0]['finish_time'] == 94.20
        assert rts[0]['dq'] == 0

    def test_save_relay_result_dq(self, relay_db):
        rt_id = create_relay_team(relay_db, relay_db.relay_event_id,
                                   relay_db.shrk_id, 'A')
        save_relay_result(relay_db, rt_id, dq=True, dq_code='FA')

        rts = get_relay_teams(relay_db, event_id=relay_db.relay_event_id)
        assert rts[0]['dq'] == 1
        assert rts[0]['dq_code'] == 'FA'

    def test_save_relay_result_with_splits(self, relay_db):
        rt_id = create_relay_team(relay_db, relay_db.relay_event_id,
                                   relay_db.shrk_id, 'A')
        sids = relay_db.swimmer_ids
        set_relay_legs(relay_db, rt_id, [
            {'leg_number': 1, 'swimmer_id': sids[0], 'order_position': 1},
            {'leg_number': 2, 'swimmer_id': sids[4], 'order_position': 2},
        ])

        save_relay_result(relay_db, rt_id, finish_time=50.00,
                         splits=[
                             {'order_position': 1, 'split_time': 24.50},
                             {'order_position': 2, 'split_time': 25.50},
                         ])

        legs = get_relay_legs(relay_db, rt_id)
        assert legs[0]['split_time'] == 24.50
        assert legs[1]['split_time'] == 25.50

    def test_calculate_relay_places(self, relay_db):
        eid = relay_db.relay_event_id
        rt1 = create_relay_team(relay_db, eid, relay_db.shrk_id, 'A')
        rt2 = create_relay_team(relay_db, eid, relay_db.dolp_id, 'A')
        rt3 = create_relay_team(relay_db, eid, relay_db.shrk_id, 'B')

        save_relay_result(relay_db, rt1, finish_time=95.00)
        save_relay_result(relay_db, rt2, finish_time=97.50)
        save_relay_result(relay_db, rt3, dq=True, dq_code='FA')

        calculate_relay_places(relay_db, eid)

        rts = get_relay_teams(relay_db, event_id=eid)
        places = {r['id']: r['place'] for r in rts}
        assert places[rt1] == 1
        assert places[rt2] == 2
        assert places[rt3] is None  # DQ'd

    def test_assign_relay_points_dual(self, relay_db):
        eid = relay_db.relay_event_id
        rt1 = create_relay_team(relay_db, eid, relay_db.shrk_id, 'A')
        rt2 = create_relay_team(relay_db, eid, relay_db.dolp_id, 'A')

        save_relay_result(relay_db, rt1, finish_time=95.00)
        save_relay_result(relay_db, rt2, finish_time=97.50)

        calculate_relay_places(relay_db, eid)
        assign_relay_points(relay_db, eid, 'dual')

        rts = get_relay_teams(relay_db, event_id=eid)
        points = {r['id']: r['points'] for r in rts}
        # Dual relay scoring: [7, 0]
        assert points[rt1] == 7
        assert points[rt2] == 0

    def test_relay_points_in_team_scores(self, relay_db):
        """Relay points should appear in team scores."""
        eid = relay_db.relay_event_id
        rt1 = create_relay_team(relay_db, eid, relay_db.shrk_id, 'A')
        rt2 = create_relay_team(relay_db, eid, relay_db.dolp_id, 'A')

        save_relay_result(relay_db, rt1, finish_time=95.00)
        save_relay_result(relay_db, rt2, finish_time=97.50)

        calculate_relay_places(relay_db, eid)
        assign_relay_points(relay_db, eid, 'dual')

        scores = get_team_scores(relay_db, 'dual')
        shrk_score = next(s for s in scores if s['team_code'] == 'SHRK')
        assert shrk_score['relay'] == 7


# ─── Relay Seeding Tests ─────────────────────────────────────────────

class TestRelaySeeding:
    def test_seed_relay_event(self, relay_db):
        eid = relay_db.relay_event_id
        create_relay_team(relay_db, eid, relay_db.shrk_id, 'A', 95.00)
        create_relay_team(relay_db, eid, relay_db.dolp_id, 'A', 97.50)
        create_relay_team(relay_db, eid, relay_db.shrk_id, 'B', 102.00)

        num_heats = apply_relay_seeding(relay_db, eid, lanes=6)
        assert num_heats == 1  # 3 relay teams fit in 1 heat

        # Check assignments
        rts = get_relay_teams(relay_db, event_id=eid)
        for rt in rts:
            assert rt['heat_id'] is not None
            assert rt['lane'] is not None

    def test_seed_relay_via_apply_seeding(self, relay_db):
        """apply_seeding should detect relay event and route to relay seeding."""
        eid = relay_db.relay_event_id
        create_relay_team(relay_db, eid, relay_db.shrk_id, 'A', 95.00)
        create_relay_team(relay_db, eid, relay_db.dolp_id, 'A', 97.50)

        num_heats = apply_seeding(relay_db, eid, lanes=6)
        assert num_heats == 1

    def test_relay_seeding_empty_event(self, relay_db):
        eid = relay_db.relay_event_id
        num_heats = apply_relay_seeding(relay_db, eid, lanes=6)
        assert num_heats == 0

    def test_relay_heat_sheet(self, relay_db):
        eid = relay_db.relay_event_id
        create_relay_team(relay_db, eid, relay_db.shrk_id, 'A', 95.00)
        create_relay_team(relay_db, eid, relay_db.dolp_id, 'A', 97.50)

        apply_relay_seeding(relay_db, eid, lanes=6)

        sheet = get_relay_heat_sheet(relay_db, eid)
        assert len(sheet) == 2
        assert 'heat' in sheet[0]
        assert 'lane' in sheet[0]
        assert 'team_code' in sheet[0]
        assert 'relay_letter' in sheet[0]

    def test_relay_multiple_heats(self, relay_db):
        eid = relay_db.relay_event_id
        # Create 8 relay teams to force multiple heats with 6 lanes
        for i, (tid, letter) in enumerate([
            (relay_db.shrk_id, 'A'), (relay_db.shrk_id, 'B'),
            (relay_db.shrk_id, 'C'), (relay_db.shrk_id, 'D'),
            (relay_db.dolp_id, 'A'), (relay_db.dolp_id, 'B'),
            (relay_db.dolp_id, 'C'), (relay_db.dolp_id, 'D'),
        ]):
            create_relay_team(relay_db, eid, tid, letter, 90.0 + i)

        num_heats = apply_relay_seeding(relay_db, eid, lanes=6)
        assert num_heats == 2  # 8 teams / 6 lanes = 2 heats


# ─── Get Team Swimmers Test ──────────────────────────────────────────

class TestGetTeamSwimmers:
    def test_get_team_swimmers(self, relay_db):
        swimmers = get_team_swimmers(relay_db, relay_db.shrk_id)
        assert len(swimmers) == 3  # Smith, Doe, Lee
        assert all('name' in s for s in swimmers)

    def test_get_team_swimmers_by_gender(self, relay_db):
        males = get_team_swimmers(relay_db, relay_db.shrk_id, gender='M')
        assert len(males) == 2  # Smith, Lee
        assert all(s['gender'] == 'M' for s in males)

        females = get_team_swimmers(relay_db, relay_db.shrk_id, gender='F')
        assert len(females) == 1  # Doe


# ─── Migration Tests ──────────────────────────────────────────────────

class TestMigration:
    def test_open_new_db_with_migrations(self):
        """Test that opening a freshly-created db applies no redundant migrations."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        conn = init_db(db_path)
        conn.close()

        conn = open_meet_db(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(version) FROM schema_version")
        assert cursor.fetchone()[0] == SCHEMA_VERSION
        conn.close()
        os.unlink(db_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
