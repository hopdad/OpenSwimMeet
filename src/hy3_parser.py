"""
HY3/SDIF Parser for Hy-Tek swim meet files.
SDIF = Swim Data Interchange Format (fixed-width fields)
"""

def time_to_seconds(time_str: str) -> float | None:
    """Convert Hy-Tek/SDIF time string to seconds (float). Returns None for NT/blank/invalid."""
    time_str = time_str.strip()
    if not time_str or time_str.upper() == 'NT':
        return None
    try:
        # Remove leading/trailing spaces, handle ' 1:23.45' or 'NT'
        time_str = time_str.replace(' ', '')
        if ':' in time_str:
            parts = time_str.split(':')
            if len(parts) == 2:
                mins, secs = parts
                return int(mins) * 60 + float(secs)
            elif len(parts) == 3:
                hrs, mins, secs = parts
                return int(hrs) * 3600 + int(mins) * 60 + float(secs)
        return float(time_str)
    except (ValueError, AttributeError):
        return None

def seconds_to_time_str(seconds: float | None) -> str:
    """Convert seconds to time string (M:SS.HH format)."""
    if seconds is None:
        return "NT"
    
    minutes = int(seconds // 60)
    secs = seconds % 60
    
    if minutes > 0:
        return f"{minutes}:{secs:05.2f}"
    else:
        return f"{secs:.2f}"

def parse_hy3_file(file_path: str) -> dict:
    """
    Parse .HY3 (Hy-Tek entries export, SDIF-based).
    Returns {'swimmers': list[dict], 'entries': list[dict], 'team': str}
    
    SDIF Format Reference:
    - C1: Team record (positions 12-17=code, 18-47=name)
    - D0: Individual entry (positions 12-39=name, 40-51=USAS, 56-63=DOB, 66=sex, etc.)
    - E0: Relay entry
    
    All positions are 1-based in SDIF spec, converted to 0-based for Python slicing.
    """
    swimmers = {}  # key: usas_id or name_team -> dict
    entries = []
    current_team_code = "UNKN"
    current_team_name = "Unknown Team"
    parse_errors = []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, raw_line in enumerate(f, 1):
                line = raw_line.rstrip('\r\n')
                
                # Skip empty lines
                if len(line) < 2:
                    continue
                
                record_type = line[0:2]

                try:
                    if record_type == 'C1':
                        # Team record - minimum 47 characters
                        if len(line) < 47:
                            parse_errors.append(f"Line {line_num}: C1 record too short ({len(line)} < 47)")
                            continue
                        
                        team_code = line[11:17].strip()  # Positions 12-17 (0-indexed: 11:17)
                        team_name = line[17:47].strip()  # Positions 18-47 (0-indexed: 17:47)
                        
                        if team_code:
                            current_team_code = team_code
                        if team_name:
                            current_team_name = team_name

                    elif record_type == 'D0':
                        # Individual entry - need at least 39 chars for swimmer name
                        if len(line) < 39:
                            parse_errors.append(f"Line {line_num}: D0 record too short ({len(line)} < 39)")
                            continue
                        
                        # Parse swimmer info
                        name = line[11:39].strip()  # Positions 12-39
                        usas_id = line[39:51].strip()  # Positions 40-51
                        birth_date = line[55:63].strip()  # Positions 56-63 (YYYYMMDD)
                        sex = line[65:66].strip() if len(line) > 65 else ''  # Position 66
                        
                        # Parse event info
                        distance = line[67:71].strip() if len(line) > 71 else ''  # Positions 68-71
                        stroke = line[71:72].strip() if len(line) > 71 else ''  # Position 72
                        event_num = line[72:76].strip() if len(line) > 76 else ''  # Positions 73-76
                        age_group = line[76:80].strip() if len(line) > 80 else ''  # Positions 77-80
                        seed_str = line[88:96].strip() if len(line) >= 96 else (line[88:].strip() if len(line) > 88 else '')  # Positions 89-96

                        # Convert seed time
                        seed_time = time_to_seconds(seed_str)

                        # Calculate age from birth date if available
                        age = 0
                        if birth_date and len(birth_date) == 8:
                            try:
                                from datetime import datetime
                                birth_year = int(birth_date[0:4])
                                current_year = datetime.now().year
                                age = current_year - birth_year
                            except ValueError:
                                pass

                        # Unique key: prefer USAS ID
                        key = usas_id if usas_id else f"{name}_{current_team_code}"

                        if key not in swimmers:
                            swimmers[key] = {
                                'name': name,
                                'team_code': current_team_code,
                                'team_name': current_team_name,
                                'usas_id': usas_id or None,
                                'sex': sex,
                                'birth_date': birth_date,
                                'age': age,
                            }

                        entries.append({
                            'swimmer_key': key,
                            'event_num': event_num,
                            'distance': distance,
                            'stroke': stroke,
                            'age_group': age_group,
                            'seed_time': seed_time,
                        })

                    elif record_type == 'E0':
                        # Relay entry (not yet implemented)
                        pass

                except (IndexError, ValueError) as e:
                    parse_errors.append(f"Line {line_num}: Parse error - {str(e)}")
                    continue

        result = {
            'swimmers': list(swimmers.values()),
            'entries': entries,
            'team_code': current_team_code,
            'team_name': current_team_name
        }
        
        if parse_errors:
            result['errors'] = parse_errors
            print(f"Parse completed with {len(parse_errors)} errors:")
            for error in parse_errors[:10]:  # Show first 10 errors
                print(f"  {error}")
        
        return result
        
    except Exception as e:
        return {
            'swimmers': [],
            'entries': [],
            'team_code': 'ERROR',
            'team_name': 'Error',
            'errors': [f"Fatal error: {str(e)}"]
        }
