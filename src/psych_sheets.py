"""
Psych sheet generation for swim meets.
Creates PDF psych sheets showing entries ranked by seed time.
"""
import sqlite3
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from src.hy3_parser import seconds_to_time_str
from src.database import get_meet_setting

def generate_psych_sheet_pdf(conn: sqlite3.Connection, output_path: str) -> bool:
    """
    Generate psych sheet PDF showing all events with entries ranked by seed time.
    
    Args:
        conn: Database connection
        output_path: Path to output PDF file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        doc = SimpleDocTemplate(output_path, pagesize=letter,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#003366'),
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        event_style = ParagraphStyle(
            'EventTitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#0066CC'),
            spaceAfter=6,
            alignment=TA_LEFT
        )
        
        # Meet header
        meet_name = get_meet_setting(conn, 'meet_name', 'Swim Meet')
        meet_date = get_meet_setting(conn, 'meet_date', '')
        
        title = Paragraph(f"<b>{meet_name}</b><br/>Psych Sheet", title_style)
        story.append(title)
        
        if meet_date:
            date_para = Paragraph(f"Date: {meet_date}", styles['Normal'])
            story.append(date_para)
        
        story.append(Spacer(1, 0.3*inch))
        
        # Get all events
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, number, name, distance, stroke, gender
            FROM events
            ORDER BY number
        """)
        
        events = cursor.fetchall()
        
        for event in events:
            event_id, event_num, event_name, distance, stroke, gender = event
            
            # Get entries for this event
            cursor.execute("""
                SELECT 
                    s.name,
                    t.team_code,
                    s.age,
                    e.seed_time
                FROM entries e
                JOIN swimmers s ON e.swimmer_id = s.id
                JOIN teams t ON s.team_id = t.id
                WHERE e.event_id = ?
                ORDER BY 
                    CASE WHEN e.seed_time IS NULL THEN 1 ELSE 0 END,
                    e.seed_time ASC
            """, (event_id,))
            
            entries = cursor.fetchall()
            
            if not entries:
                continue  # Skip events with no entries
            
            # Event header
            event_title = f"Event {event_num}: {event_name}"
            story.append(Paragraph(event_title, event_style))
            story.append(Spacer(1, 0.1*inch))
            
            # Create table data
            table_data = [['Rank', 'Name', 'Team', 'Age', 'Seed Time']]
            
            rank = 1
            for entry in entries:
                name, team, age, seed_time = entry
                time_str = seconds_to_time_str(seed_time)
                
                table_data.append([
                    str(rank) if seed_time else 'NT',
                    name,
                    team,
                    str(age) if age else '',
                    time_str
                ])
                
                if seed_time:  # Only increment rank for seeded swimmers
                    rank += 1
            
            # Create table
            table = Table(table_data, colWidths=[0.6*inch, 2.5*inch, 0.8*inch, 0.6*inch, 1.0*inch])
            
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066CC')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Name column left-aligned
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F8FF')])
            ]))
            
            story.append(table)
            story.append(Spacer(1, 0.3*inch))
            
            # Page break after every 2 events (adjust as needed)
            if events.index(event) % 2 == 1 and events.index(event) < len(events) - 1:
                story.append(PageBreak())
        
        # Build PDF
        doc.build(story)
        return True
        
    except Exception as e:
        print(f"Error generating psych sheet: {e}")
        return False

def generate_heat_sheet_pdf(conn: sqlite3.Connection, event_id: int, output_path: str) -> bool:
    """
    Generate heat sheet PDF for a specific event.
    
    Args:
        conn: Database connection
        event_id: Event to generate heat sheet for
        output_path: Path to output PDF file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        from src.seeding import get_heat_sheet
        
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Get event info
        cursor = conn.cursor()
        cursor.execute("SELECT number, name FROM events WHERE id = ?", (event_id,))
        event = cursor.fetchone()
        
        if not event:
            return False
        
        event_num, event_name = event
        
        # Title
        title = Paragraph(f"<b>Event {event_num}: {event_name}</b><br/>Heat Sheet", 
                         styles['Title'])
        story.append(title)
        story.append(Spacer(1, 0.2*inch))
        
        # Get heat sheet data
        heat_data = get_heat_sheet(conn, event_id)
        
        if not heat_data:
            story.append(Paragraph("No heats seeded yet.", styles['Normal']))
        else:
            # Group by heat
            current_heat = None
            table_data = []
            
            for row in heat_data:
                if row['heat'] != current_heat:
                    if table_data:
                        # Create table for previous heat
                        table = Table(table_data, colWidths=[0.8*inch, 2.5*inch, 1.0*inch, 1.2*inch])
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066CC')),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                        ]))
                        story.append(table)
                        story.append(Spacer(1, 0.2*inch))
                    
                    # Start new heat
                    current_heat = row['heat']
                    story.append(Paragraph(f"<b>Heat {current_heat}</b>", styles['Heading3']))
                    story.append(Spacer(1, 0.1*inch))
                    table_data = [['Lane', 'Name', 'Team', 'Seed Time']]
                
                table_data.append([
                    str(row['lane']),
                    row['name'],
                    row['team'],
                    row['seed_time']
                ])
            
            # Add final table
            if table_data:
                table = Table(table_data, colWidths=[0.8*inch, 2.5*inch, 1.0*inch, 1.2*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066CC')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ]))
                story.append(table)
        
        doc.build(story)
        return True
        
    except Exception as e:
        print(f"Error generating heat sheet: {e}")
        return False