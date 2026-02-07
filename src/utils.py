"""
Utility functions for OpenSwimMeet.
"""
from datetime import datetime
from typing import Optional

def calculate_age(birth_date: str, meet_date: Optional[str] = None) -> int:
    """
    Calculate age from birth date.
    
    Args:
        birth_date: Birth date in YYYYMMDD or YYYY-MM-DD format
        meet_date: Meet date (defaults to today)
    
    Returns:
        Age in years
    """
    try:
        # Parse birth date
        if len(birth_date) == 8:  # YYYYMMDD
            birth_year = int(birth_date[0:4])
            birth_month = int(birth_date[4:6])
            birth_day = int(birth_date[6:8])
        elif '-' in birth_date:  # YYYY-MM-DD
            parts = birth_date.split('-')
            birth_year = int(parts[0])
            birth_month = int(parts[1])
            birth_day = int(parts[2])
        else:
            return 0
        
        # Parse meet date or use today
        if meet_date:
            if len(meet_date) == 8:
                meet_year = int(meet_date[0:4])
                meet_month = int(meet_date[4:6])
                meet_day = int(meet_date[6:8])
            elif '-' in meet_date:
                parts = meet_date.split('-')
                meet_year = int(parts[0])
                meet_month = int(parts[1])
                meet_day = int(parts[2])
            else:
                now = datetime.now()
                meet_year = now.year
                meet_month = now.month
                meet_day = now.day
        else:
            now = datetime.now()
            meet_year = now.year
            meet_month = now.month
            meet_day = now.day
        
        # Calculate age
        age = meet_year - birth_year
        
        # Adjust if birthday hasn't occurred yet this year
        if (meet_month, meet_day) < (birth_month, birth_day):
            age -= 1
        
        return age
        
    except (ValueError, IndexError):
        return 0

def format_time_input(time_str: str) -> Optional[float]:
    """
    Parse user time input and convert to seconds.
    Accepts formats: 23.45, 1:23.45, NT
    
    Returns:
        Seconds as float, or None for NT/invalid
    """
    from src.hy3_parser import time_to_seconds
    return time_to_seconds(time_str)

def validate_usas_id(usas_id: str) -> bool:
    """
    Validate USA Swimming ID format (typically 12 digits).
    
    Args:
        usas_id: USA Swimming ID to validate
    
    Returns:
        True if valid format, False otherwise
    """
    if not usas_id:
        return True  # Empty is OK
    
    # Remove any dashes or spaces
    cleaned = usas_id.replace('-', '').replace(' ', '')
    
    # Check if it's all digits and proper length
    return cleaned.isdigit() and len(cleaned) in [10, 12, 14]

def format_meet_date(date_str: str) -> str:
    """
    Format a date string for display.
    
    Args:
        date_str: Date in YYYYMMDD or YYYY-MM-DD format
    
    Returns:
        Formatted date string (e.g., "January 15, 2025")
    """
    try:
        if len(date_str) == 8:  # YYYYMMDD
            dt = datetime.strptime(date_str, '%Y%m%d')
        else:  # YYYY-MM-DD
            dt = datetime.strptime(date_str, '%Y-%m-%d')
        
        return dt.strftime('%B %d, %Y')
    except:
        return date_str