"""
Tests for HY3 parser and other core functionality.
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.hy3_parser import time_to_seconds, seconds_to_time_str, parse_hy3_file
from src.utils import calculate_age, format_time_input, validate_usas_id


class TestTimeConversion:
    """Test time conversion functions."""
    
    def test_time_to_seconds_simple(self):
        """Test simple time conversion."""
        assert time_to_seconds("23.45") == 23.45
        assert time_to_seconds("59.99") == 59.99
    
    def test_time_to_seconds_minutes(self):
        """Test minute:second conversion."""
        assert time_to_seconds("1:23.45") == 83.45
        assert time_to_seconds("2:15.67") == 135.67
    
    def test_time_to_seconds_hours(self):
        """Test hour:minute:second conversion."""
        assert time_to_seconds("1:05:23.45") == 3923.45
    
    def test_time_to_seconds_nt(self):
        """Test NT (no time) handling."""
        assert time_to_seconds("NT") is None
        assert time_to_seconds("nt") is None
        assert time_to_seconds("") is None
        assert time_to_seconds("  ") is None
    
    def test_time_to_seconds_invalid(self):
        """Test invalid input handling."""
        assert time_to_seconds("abc") is None
        assert time_to_seconds("1:2:3:4") is None
    
    def test_seconds_to_time_str(self):
        """Test seconds to time string conversion."""
        assert seconds_to_time_str(23.45) == "23.45"
        assert seconds_to_time_str(83.45) == "1:23.45"
        assert seconds_to_time_str(None) == "NT"
    
    def test_roundtrip_conversion(self):
        """Test roundtrip conversion."""
        times = ["1:23.45", "59.99", "2:15.67"]
        for time_str in times:
            seconds = time_to_seconds(time_str)
            converted = seconds_to_time_str(seconds)
            # Convert back to check
            assert abs(time_to_seconds(converted) - time_to_seconds(time_str)) < 0.01


class TestHY3Parser:
    """Test HY3/SDIF parser."""
    
    def test_parse_sample_file(self):
        """Test parsing sample HY3 file."""
        sample_path = Path(__file__).parent.parent / 'resources' / 'sample_data' / 'SAMPLE.hy3'
        
        if not sample_path.exists():
            pytest.skip("Sample file not found")
        
        result = parse_hy3_file(str(sample_path))
        
        assert 'swimmers' in result
        assert 'entries' in result
        assert len(result['swimmers']) > 0
        assert len(result['entries']) > 0
    
    def test_parse_nonexistent_file(self):
        """Test parsing nonexistent file."""
        result = parse_hy3_file('/nonexistent/file.hy3')
        assert result['swimmers'] == []
        assert 'errors' in result


class TestUtils:
    """Test utility functions."""
    
    def test_calculate_age(self):
        """Test age calculation."""
        # Born in 2008, meet in 2024
        age = calculate_age('20080515', '2024-01-15')
        assert age == 15  # Not yet birthday
        
        age = calculate_age('20080515', '2024-06-15')
        assert age == 16  # After birthday
    
    def test_validate_usas_id(self):
        """Test USAS ID validation."""
        assert validate_usas_id('123456789012') == True  # 12 digits
        assert validate_usas_id('1234567890') == True    # 10 digits
        assert validate_usas_id('abc123') == False       # Not all digits
        assert validate_usas_id('') == True              # Empty OK
        assert validate_usas_id('123') == False          # Too short


class TestDatabase:
    """Test database functions."""
    
    def test_init_db(self):
        """Test database initialization."""
        from src.database import init_db
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        conn = init_db(db_path)
        cursor = conn.cursor()
        
        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        assert 'swimmers' in tables
        assert 'events' in tables
        assert 'entries' in tables
        assert 'teams' in tables
        assert 'heats' in tables
        
        conn.close()
        
        # Cleanup
        import os
        os.unlink(db_path)


class TestSeeding:
    """Test seeding algorithms."""
    
    def test_circle_seeding(self):
        """Test circle seeding algorithm."""
        from src.database import init_db, get_or_insert_swimmer, insert_or_update_entry
        from src.seeding import apply_seeding
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        conn = init_db(db_path)
        cursor = conn.cursor()
        
        # Create event
        cursor.execute("""
            INSERT INTO events (number, name, distance, stroke, gender)
            VALUES (1, '50 Free', 50, 'FREE', 'M')
        """)
        event_id = cursor.lastrowid
        
        # Add swimmers and entries
        for i in range(10):
            swimmer_id = get_or_insert_swimmer(
                conn, f"Swimmer {i}", "TEST", "Test Team", age=15, gender='M'
            )
            seed_time = 25.0 + i * 0.5  # 25.0, 25.5, 26.0, etc.
            insert_or_update_entry(conn, swimmer_id, event_id, seed_time)
        
        # Apply seeding
        num_heats = apply_seeding(conn, event_id, method='circle', lanes=6)
        
        assert num_heats == 2  # 10 swimmers / 6 lanes = 2 heats
        
        # Check heat assignments created
        cursor.execute("SELECT COUNT(*) FROM heat_assignments")
        count = cursor.fetchone()[0]
        assert count == 10
        
        conn.close()
        
        # Cleanup
        import os
        os.unlink(db_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])