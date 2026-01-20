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
    except ValueError:
        return None

def parse_hy3_file(file_path: str) -> dict:
    """
    Basic parser for .HY3 (Hy-Tek entries export, SDIF-based).
    Returns {'swimmers': list[dict], 'entries': list[dict]}
    - swimmers: unique by USAS ID or name+team
    - entries: {'swimmer_usas_or_name': str, 'event_num': str, 'seed_time': float|None, ...}
    Positions are 1-based from SDIF v3 spec.
    """
    swimmers = {}  # key: usas_id or name_team -> dict
    entries = []
    current_team = "Unknown Team"

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, raw_line in enumerate(f, 1):
                line = raw_line.rstrip('\r\n')  # Remove CR/LF
                if len(line) < 2:
                    continue
                record_type = line[0:2]

                if record_type == 'C1':
                    # Team record
                    team_code = line[11:17].strip()  # 12-17
                    team_name = line[17:47].strip()  # 18-47
                    current_team = team_code or team_name or current_team

                elif record_type == 'D0':
                    # Individual entry
                    name = line[11:39].strip()  # 12-39
                    usas_id = line[39:51].strip()  # 40-51
                    birth_date = line[55:63].strip()  # 56-63 (YYYYMMDD)
                    sex = line[65:66].strip()  # 66
                    distance = line[67:71].strip()  # 68-71
                    stroke = line[71:72].strip()  # 72
                    event_num = line[72:76].strip()  # 73-76
                    age_group = line[76:80].strip()  # 77-80
                    seed_str = line[88:96].strip()  # 89-96

                    seed_time = time_to_seconds(seed_str)

                    # Key for uniqueness: prefer USAS ID
                    key = usas_id if usas_id else f"{name}_{current_team}"

                    if key not in swimmers:
                        swimmers[key] = {
                            'name': name,
                            'team': current_team,
                            'usas_id': usas_id or None,
                            'sex': sex,
                            'birth_date': birth_date,
                            'age': 0,  # Placeholder; calculate later if meet date known
                        }

                    entries.append({
                        'swimmer_key': key,
                        'event_num': event_num,
                        'distance': distance,
                        'stroke': stroke,
                        'age_group': age_group,
                        'seed_time': seed_time,
                    })

        return {'swimmers': list(swimmers.values()), 'entries': entries, 'team': current_team}
    except Exception as e:
        print(f"Parse error on line {line_num}: {e}")
        return {}
