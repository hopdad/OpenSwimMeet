"""
HY3/SDIF Exporter for Hy-Tek compatibility.
Exports meet data to SDIF format for interchange with Hy-Tek software.
"""
import sqlite3
from datetime import datetime
from src.hy3_parser import seconds_to_time_str

def export_to_hy3(conn: sqlite3.Connection, output_path: str, team_code: str = None) -> bool:
    """
    Export meet entries to HY3/SDIF format.
    
    Args:
        conn: Database connection
        output_path: Path to output .hy3 file
        team_code: If specified, only export this team's entries
    
    Returns:
        True if successful, False otherwise
    """
    try:
        cursor = conn.cursor()
        
        # Get meet info
        meet_name = _get_setting(conn, 'meet_name', 'Swim Meet')
        meet_date = _get_setting(conn, 'meet_date', datetime.now().strftime('%Y%m%d'))
        course_code = _get_setting(conn, 'course', 'SCY')
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # Write A1 - Meet header
            f.write(_format_a1_record(meet_name, meet_date, course_code))
            
            # Get teams
            if team_code:
                cursor.execute("SELECT * FROM teams WHERE team_code = ?", (team_code,))
            else:
                cursor.execute("SELECT * FROM teams ORDER BY team_code")
            
            teams = cursor.fetchall()
            
            for team in teams:
                team_id, t_code, t_name, t_short, t_color = team
                
                # Write C1 - Team record
                f.write(_format_c1_record(t_code, t_name))
                
                # Get swimmers for this team
                cursor.execute("""
                    SELECT DISTINCT s.id, s.name, s.usas_id, s.gender, s.date_of_birth, s.age
                    FROM swimmers s
                    WHERE s.team_id = ?
                    ORDER BY s.name
                """, (team_id,))
                
                swimmers = cursor.fetchall()
                
                for swimmer in swimmers:
                    swimmer_id, name, usas_id, gender, dob, age = swimmer
                    
                    # Get entries for this swimmer
                    cursor.execute("""
                        SELECT ev.number, ev.distance, ev.stroke, e.seed_time
                        FROM entries e
                        JOIN events ev ON e.event_id = ev.id
                        WHERE e.swimmer_id = ?
                        ORDER BY ev.number
                    """, (swimmer_id,))
                    
                    entries = cursor.fetchall()
                    
                    for entry in entries:
                        event_num, distance, stroke, seed_time = entry
                        
                        # Write D0 - Individual entry
                        f.write(_format_d0_record(
                            name, usas_id, gender, dob, age,
                            event_num, distance, stroke, seed_time
                        ))
            
            # Write Z0 - End of file marker
            f.write("Z001\n")
        
        return True
        
    except Exception as e:
        print(f"Error exporting to HY3: {e}")
        return False

def _get_setting(conn: sqlite3.Connection, key: str, default: str) -> str:
    """Get meet setting or return default."""
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM meet_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    return row[0] if row else default

def _format_a1_record(meet_name: str, meet_date: str, course: str) -> str:
    """
    Format A1 (meet header) record.
    
    A1 Format (positions 1-based):
    01-02: 'A1'
    03-03: Org code (blank)
    04-11: Future (blank)
    12-41: Meet name
    42-47: Meet address (blank)
    ... etc
    """
    # Simplified A1 record
    record = "A1"
    record += " " * 9  # Positions 3-11
    record += meet_name[:30].ljust(30)  # Meet name
    record += " " * 100  # Rest of record
    return record + "\n"

def _format_c1_record(team_code: str, team_name: str) -> str:
    """
    Format C1 (team) record.
    
    C1 Format (positions 1-based):
    01-02: 'C1'
    03-11: Future (blank)
    12-17: Team code
    18-47: Team name
    ... etc
    """
    record = "C1"
    record += " " * 9  # Positions 3-11
    record += team_code[:6].ljust(6)  # Positions 12-17
    record += team_name[:30].ljust(30)  # Positions 18-47
    record += " " * 100  # Rest of record
    return record + "\n"

def _format_d0_record(name: str, usas_id: str, gender: str, dob: str, age: int,
                      event_num: int, distance: int, stroke: str, seed_time: float) -> str:
    """
    Format D0 (individual entry) record.
    
    D0 Format (positions 1-based):
    01-02: 'D0'
    03-11: Future (blank)
    12-39: Swimmer name (Last, First)
    40-51: USAS ID
    52-55: Citizen code (blank)
    56-63: Birth date (YYYYMMDD)
    64-65: Age
    66-66: Gender (M/F)
    67-67: Event gender (M/F/X)
    68-71: Distance
    72-72: Stroke code
    73-76: Event number
    77-80: Age group (blank)
    81-88: Future (blank)
    89-96: Seed time (M:SS.HH)
    """
    record = "D0"
    record += " " * 9  # Positions 3-11
    
    # Format name (Last, First)
    name_parts = name.split(',') if ',' in name else name.split()
    if len(name_parts) >= 2 and ',' in name:
        formatted_name = name[:28]  # Already in Last, First format
    elif len(name_parts) >= 2:
        formatted_name = f"{name_parts[-1]}, {' '.join(name_parts[:-1])}"[:28]
    else:
        formatted_name = name[:28]
    
    record += formatted_name.ljust(28)  # Positions 12-39
    record += (usas_id or "")[:12].ljust(12)  # Positions 40-51
    record += " " * 4  # Positions 52-55
    record += (dob or "")[:8].ljust(8)  # Positions 56-63
    record += str(age).zfill(2)[:2]  # Positions 64-65
    record += (gender or "U")[:1]  # Position 66
    record += (gender or "U")[:1]  # Position 67 (event gender, same as swimmer)
    record += str(distance).zfill(4)[:4]  # Positions 68-71
    
    # Stroke code: 1=Free, 2=Back, 3=Breast, 4=Fly, 5=IM
    stroke_map = {'FREE': '1', 'BACK': '2', 'BREAST': '3', 'FLY': '4', 'IM': '5'}
    stroke_code = stroke_map.get(stroke.upper(), '1')
    record += stroke_code  # Position 72
    
    record += str(event_num).zfill(4)[:4]  # Positions 73-76
    record += " " * 4  # Positions 77-80 (age group)
    record += " " * 8  # Positions 81-88
    
    # Format seed time
    if seed_time:
        time_str = seconds_to_time_str(seed_time)
        # Convert to format: M:SS.HH (8 characters)
        if ':' in time_str:
            mins, secs = time_str.split(':')
            time_formatted = f"{int(mins):1d}:{float(secs):05.2f}"
        else:
            time_formatted = f"0:{float(time_str):05.2f}"
    else:
        time_formatted = "NT"
    
    record += time_formatted.rjust(8)  # Positions 89-96
    
    return record + "\n"