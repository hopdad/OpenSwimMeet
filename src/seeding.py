"""
Seeding algorithms for swim meets.
Implements circle seeding (standard USA Swimming) and straight seeding.
"""
import sqlite3
from typing import List, Tuple

def apply_seeding(conn: sqlite3.Connection, event_id: int, method: str = 'circle', lanes: int = 6) -> int:
    """
    Seed an event and create heat assignments.
    
    Args:
        conn: Database connection
        event_id: Event to seed
        method: 'circle' (standard) or 'straight' (fastest to slowest)
        lanes: Number of lanes (typically 6 or 8)
    
    Returns:
        Number of heats created
    """
    cursor = conn.cursor()

    # Check if this is a relay event
    cursor.execute("SELECT is_relay FROM events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    if row and row[0]:
        return apply_relay_seeding(conn, event_id, method, lanes)

    # Get all entries for this event, ordered by seed time (fastest first, NT last)
    cursor.execute("""
        SELECT e.id, e.swimmer_id, e.seed_time, s.name
        FROM entries e
        JOIN swimmers s ON e.swimmer_id = s.id
        WHERE e.event_id = ?
        ORDER BY
            CASE WHEN e.seed_time IS NULL THEN 1 ELSE 0 END,
            e.seed_time ASC
    """, (event_id,))
    
    entries = cursor.fetchall()
    
    if not entries:
        return 0
    
    # Clear existing heats for this event
    cursor.execute("DELETE FROM heats WHERE event_id = ?", (event_id,))
    cursor.execute("""
        DELETE FROM heat_assignments 
        WHERE heat_id IN (SELECT id FROM heats WHERE event_id = ?)
    """, (event_id,))
    
    # Calculate number of heats needed
    num_entries = len(entries)
    num_heats = (num_entries + lanes - 1) // lanes  # Ceiling division
    
    if method == 'straight':
        heat_assignments = _straight_seeding(entries, num_heats, lanes)
    else:  # circle seeding (default)
        heat_assignments = _circle_seeding(entries, num_heats, lanes)
    
    # Create heats and assignments
    for heat_num in range(1, num_heats + 1):
        cursor.execute(
            "INSERT INTO heats (event_id, heat_number) VALUES (?, ?)",
            (event_id, heat_num)
        )
        heat_id = cursor.lastrowid
        
        # Insert lane assignments for this heat
        for lane, entry_id in heat_assignments[heat_num - 1]:
            if entry_id is not None:  # Skip empty lanes
                cursor.execute(
                    "INSERT INTO heat_assignments (entry_id, heat_id, lane) VALUES (?, ?, ?)",
                    (entry_id, heat_id, lane)
                )
    
    conn.commit()
    return num_heats

def _straight_seeding(entries: List[Tuple], num_heats: int, lanes: int) -> List[List[Tuple[int, int]]]:
    """
    Straight seeding: Fastest swimmers in last heat, middle lanes.
    
    Returns: List of heats, each heat is list of (lane, entry_id) tuples.
    """
    heat_assignments = [[] for _ in range(num_heats)]
    entry_idx = 0
    
    for heat_num in range(num_heats):
        heat_entries = []
        entries_in_heat = min(lanes, len(entries) - entry_idx)
        
        # Fill lanes from outside to inside (1, 2, lanes-1, lanes, 3, lanes-2, ...)
        lane_order = _get_lane_order(lanes, entries_in_heat)
        
        for lane in lane_order:
            if entry_idx < len(entries):
                entry_id = entries[entry_idx][0]  # Get entry ID
                heat_entries.append((lane, entry_id))
                entry_idx += 1
        
        heat_assignments[heat_num] = heat_entries
    
    return heat_assignments

def _circle_seeding(entries: List[Tuple], num_heats: int, lanes: int) -> List[List[Tuple[int, int]]]:
    """
    Circle seeding: Fastest swimmers in last heat, middle lanes.
    Then work backwards placing alternating swimmers.
    
    This is the standard USA Swimming seeding method.
    
    Returns: List of heats, each heat is list of (lane, entry_id) tuples.
    """
    heat_assignments = [[] for _ in range(num_heats)]
    
    # Separate entries with times from NT entries
    timed_entries = [e for e in entries if e[2] is not None]
    nt_entries = [e for e in entries if e[2] is None]
    
    # Seed timed entries with circle seeding
    if timed_entries:
        heat_assignments = _circle_seed_timed(timed_entries, num_heats, lanes)
    
    # Add NT entries to remaining spots (first heats, outside lanes)
    if nt_entries:
        heat_assignments = _add_nt_entries(heat_assignments, nt_entries, num_heats, lanes)
    
    return heat_assignments

def _circle_seed_timed(entries: List[Tuple], num_heats: int, lanes: int) -> List[List[Tuple[int, int]]]:
    """Circle seed entries with seed times."""
    heat_assignments = [[] for _ in range(num_heats)]
    
    # Start with last heat, middle lanes
    current_heat = num_heats - 1
    lane_order = _get_lane_order(lanes, min(len(entries), lanes))
    lane_idx = 0
    
    for entry in entries:
        entry_id = entry[0]
        
        # Get next lane
        if lane_idx >= len(lane_order):
            # Move to previous heat
            current_heat -= 1
            lane_idx = 0
            if current_heat < 0:
                current_heat = 0
            lane_order = _get_lane_order(lanes, min(len(entries) - len(heat_assignments[current_heat]) * lanes, lanes))
        
        lane = lane_order[lane_idx]
        heat_assignments[current_heat].append((lane, entry_id))
        lane_idx += 1
    
    return heat_assignments

def _add_nt_entries(heat_assignments: List[List[Tuple[int, int]]], nt_entries: List[Tuple], 
                    num_heats: int, lanes: int) -> List[List[Tuple[int, int]]]:
    """Add NT (no time) entries to remaining open lanes."""
    # Find open lanes starting from first heat
    for entry in nt_entries:
        entry_id = entry[0]
        placed = False
        
        for heat_num in range(num_heats):
            if len(heat_assignments[heat_num]) < lanes:
                # Find next open lane
                used_lanes = {lane for lane, _ in heat_assignments[heat_num]}
                for lane in range(1, lanes + 1):
                    if lane not in used_lanes:
                        heat_assignments[heat_num].append((lane, entry_id))
                        placed = True
                        break
            if placed:
                break
    
    return heat_assignments

def _get_lane_order(total_lanes: int, swimmers_in_heat: int) -> List[int]:
    """
    Get lane assignment order (middle lanes first).
    For 6 lanes: [4, 3, 5, 2, 6, 1]
    For 8 lanes: [4, 5, 3, 6, 2, 7, 1, 8]
    """
    if total_lanes == 6:
        base_order = [4, 3, 5, 2, 6, 1]
    elif total_lanes == 8:
        base_order = [4, 5, 3, 6, 2, 7, 1, 8]
    else:
        # General algorithm for any lane count
        middle = (total_lanes + 1) // 2
        base_order = []
        for i in range(total_lanes):
            if i % 2 == 0:
                base_order.append(middle + i // 2)
            else:
                base_order.append(middle - (i // 2 + 1))
    
    # Only return lanes needed for this heat
    return base_order[:swimmers_in_heat]

def apply_relay_seeding(conn: sqlite3.Connection, event_id: int,
                        method: str = 'circle', lanes: int = 6) -> int:
    """
    Seed a relay event using relay_teams table.

    Args:
        conn: Database connection
        event_id: Relay event to seed
        method: 'circle' or 'straight'
        lanes: Number of lanes

    Returns:
        Number of heats created
    """
    cursor = conn.cursor()

    # Get all relay teams for this event, ordered by seed time
    cursor.execute("""
        SELECT id, seed_time
        FROM relay_teams
        WHERE event_id = ?
        ORDER BY
            CASE WHEN seed_time IS NULL THEN 1 ELSE 0 END,
            seed_time ASC
    """, (event_id,))

    relay_entries = cursor.fetchall()
    if not relay_entries:
        return 0

    # Clear existing heats for this event
    cursor.execute("DELETE FROM heats WHERE event_id = ?", (event_id,))

    num_entries = len(relay_entries)
    num_heats = (num_entries + lanes - 1) // lanes

    # Build entries in same format as individual: (relay_team_id, None, seed_time, '')
    entries = [(rt_id, None, seed_time, '') for rt_id, seed_time in relay_entries]

    if method == 'straight':
        heat_assignments = _straight_seeding(entries, num_heats, lanes)
    else:
        heat_assignments = _circle_seeding(entries, num_heats, lanes)

    # Create heats and assign relay teams to lanes
    for heat_num in range(1, num_heats + 1):
        cursor.execute(
            "INSERT INTO heats (event_id, heat_number) VALUES (?, ?)",
            (event_id, heat_num)
        )
        heat_id = cursor.lastrowid

        for lane, relay_team_id in heat_assignments[heat_num - 1]:
            if relay_team_id is not None:
                cursor.execute(
                    "UPDATE relay_teams SET heat_id = ?, lane = ? WHERE id = ?",
                    (heat_id, lane, relay_team_id)
                )

    conn.commit()
    return num_heats


def get_relay_heat_sheet(conn: sqlite3.Connection, event_id: int) -> List[dict]:
    """
    Get heat sheet data for a relay event.

    Returns list of dicts with heat/lane info for relay teams.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT h.heat_number, rt.lane, t.team_code, t.team_name,
               rt.relay_letter, rt.seed_time, rt.id
        FROM relay_teams rt
        JOIN heats h ON rt.heat_id = h.id
        JOIN teams t ON rt.team_id = t.id
        WHERE rt.event_id = ? AND rt.heat_id IS NOT NULL
        ORDER BY h.heat_number, rt.lane
    """, (event_id,))

    results = []
    for row in cursor.fetchall():
        from src.hy3_parser import seconds_to_time_str
        results.append({
            'heat': row[0],
            'lane': row[1],
            'team_code': row[2],
            'team_name': row[3],
            'relay_letter': row[4],
            'name': f"{row[2]} '{row[4]}'",
            'seed_time': seconds_to_time_str(row[5]),
            'relay_team_id': row[6],
        })
    return results


def get_heat_sheet(conn: sqlite3.Connection, event_id: int) -> List[dict]:
    """
    Get heat sheet data for an event.
    
    Returns list of dicts with heat/lane info for display or printing.
    """
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            h.heat_number,
            ha.lane,
            s.name,
            t.team_code,
            e.seed_time
        FROM heat_assignments ha
        JOIN heats h ON ha.heat_id = h.id
        JOIN entries e ON ha.entry_id = e.id
        JOIN swimmers s ON e.swimmer_id = s.id
        JOIN teams t ON s.team_id = t.id
        WHERE h.event_id = ?
        ORDER BY h.heat_number, ha.lane
    """, (event_id,))
    
    results = []
    for row in cursor.fetchall():
        from src.hy3_parser import seconds_to_time_str
        results.append({
            'heat': row[0],
            'lane': row[1],
            'name': row[2],
            'team': row[3],
            'seed_time': seconds_to_time_str(row[4])
        })
    
    return results