"""
Main application for OpenSwimMeet using tkinter.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import sqlite3
from pathlib import Path
from datetime import datetime

from src.database import (
    init_db, open_meet_db, get_or_insert_swimmer, get_or_insert_team,
    get_event_id, insert_or_update_entry, get_meet_setting, set_meet_setting
)
from src.hy3_parser import parse_hy3_file, time_to_seconds
from src.hy3_exporter import export_to_hy3
from src.seeding import apply_seeding, get_heat_sheet
from src.psych_sheets import generate_psych_sheet_pdf, generate_heat_sheet_pdf


class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OpenSwimMeet - Swim Meet Manager")
        self.root.geometry("1000x700")
        
        self.current_meet_path = None
        self.db_conn = None
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        self.show_welcome_screen()
    
    def clear_window(self):
        """Clear all widgets from window."""
        for widget in self.root.winfo_children():
            widget.destroy()
    
    def show_welcome_screen(self):
        """Show welcome screen with New/Open options."""
        self.clear_window()
        
        # Main frame
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(expand=True, fill='both')
        
        # Welcome label
        welcome_label = ttk.Label(
            frame,
            text="OpenSwimMeet",
            font=('Arial', 28, 'bold')
        )
        welcome_label.pack(pady=20)
        
        subtitle = ttk.Label(
            frame,
            text="Offline swimming meet management – intuitive & Hy-Tek compatible",
            font=('Arial', 12)
        )
        subtitle.pack(pady=10)
        
        # Button frame
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=40)
        
        new_btn = ttk.Button(
            btn_frame,
            text="New Meet",
            command=self.new_meet,
            width=20
        )
        new_btn.pack(pady=10)
        
        open_btn = ttk.Button(
            btn_frame,
            text="Open Existing Meet",
            command=self.open_meet,
            width=20
        )
        open_btn.pack(pady=10)
    
    def new_meet(self):
        """Create a new meet database."""
        path = filedialog.asksaveasfilename(
            title="Create New Meet",
            defaultextension=".db",
            filetypes=[("Meet Database", "*.db"), ("All Files", "*.*")]
        )
        
        if path:
            self.current_meet_path = path
            self.db_conn = init_db(path)
            self.show_meet_setup_wizard()
    
    def open_meet(self):
        """Open an existing meet database."""
        path = filedialog.askopenfilename(
            title="Open Meet",
            filetypes=[("Meet Database", "*.db"), ("All Files", "*.*")]
        )
        
        if path:
            try:
                self.current_meet_path = path
                self.db_conn = open_meet_db(path)
                self.show_main_dashboard()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open meet: {e}")
    
    def show_meet_setup_wizard(self):
        """Show wizard for initial meet setup."""
        wizard = tk.Toplevel(self.root)
        wizard.title("Meet Setup Wizard")
        wizard.geometry("500x400")
        
        frame = ttk.Frame(wizard, padding="20")
        frame.pack(fill='both', expand=True)
        
        # Meet name
        ttk.Label(frame, text="Meet Name:").grid(row=0, column=0, sticky='w', pady=5)
        meet_name_var = tk.StringVar(value="Swim Meet")
        ttk.Entry(frame, textvariable=meet_name_var, width=40).grid(row=0, column=1, pady=5)
        
        # Meet date
        ttk.Label(frame, text="Meet Date:").grid(row=1, column=0, sticky='w', pady=5)
        meet_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=meet_date_var, width=40).grid(row=1, column=1, pady=5)
        
        # Course
        ttk.Label(frame, text="Course:").grid(row=2, column=0, sticky='w', pady=5)
        course_var = tk.StringVar(value="SCY")
        course_combo = ttk.Combobox(frame, textvariable=course_var, 
                                    values=["SCY", "SCM", "LCM"], state='readonly', width=37)
        course_combo.grid(row=2, column=1, pady=5)
        
        # Meet type
        ttk.Label(frame, text="Meet Type:").grid(row=3, column=0, sticky='w', pady=5)
        type_var = tk.StringVar(value="Dual")
        type_combo = ttk.Combobox(frame, textvariable=type_var,
                                  values=["Dual", "Invitational", "Championship"], 
                                  state='readonly', width=37)
        type_combo.grid(row=3, column=1, pady=5)
        
        # Lanes
        ttk.Label(frame, text="Number of Lanes:").grid(row=4, column=0, sticky='w', pady=5)
        lanes_var = tk.IntVar(value=6)
        lanes_spin = ttk.Spinbox(frame, from_=4, to=10, textvariable=lanes_var, width=38)
        lanes_spin.grid(row=4, column=1, pady=5)
        
        def save_and_continue():
            # Save settings
            set_meet_setting(self.db_conn, 'meet_name', meet_name_var.get())
            set_meet_setting(self.db_conn, 'meet_date', meet_date_var.get())
            set_meet_setting(self.db_conn, 'course', course_var.get())
            set_meet_setting(self.db_conn, 'meet_type', type_var.get())
            set_meet_setting(self.db_conn, 'lanes', str(lanes_var.get()))
            
            wizard.destroy()
            self.show_main_dashboard()
        
        ttk.Button(frame, text="Save & Continue", command=save_and_continue).grid(
            row=5, column=0, columnspan=2, pady=20
        )
    
    def show_main_dashboard(self):
        """Show main dashboard with tabs."""
        self.clear_window()
        
        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Meet", command=self.new_meet)
        file_menu.add_command(label="Open Meet", command=self.open_meet)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Import menu
        import_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Import", menu=import_menu)
        import_menu.add_command(label="Import HY3 File", command=self.import_hy3)
        
        # Export menu
        export_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Export", menu=export_menu)
        export_menu.add_command(label="Export to HY3", command=self.export_hy3)
        export_menu.add_command(label="Generate Psych Sheet", command=self.generate_psych_sheet)
        
        # Create notebook (tabs)
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Dashboard tab
        dashboard_frame = self.create_dashboard_tab()
        notebook.add(dashboard_frame, text="Dashboard")
        
        # Events tab
        events_frame = self.create_events_tab()
        notebook.add(events_frame, text="Events")
        
        # Swimmers tab
        swimmers_frame = self.create_swimmers_tab()
        notebook.add(swimmers_frame, text="Swimmers")
        
        # Entries tab
        entries_frame = self.create_entries_tab()
        notebook.add(entries_frame, text="Entries")
    
    def create_dashboard_tab(self):
        """Create dashboard tab with action buttons."""
        frame = ttk.Frame()
        
        # Meet info
        meet_name = get_meet_setting(self.db_conn, 'meet_name', 'Untitled Meet')
        meet_date = get_meet_setting(self.db_conn, 'meet_date', '')
        
        info_frame = ttk.LabelFrame(frame, text="Meet Information", padding="10")
        info_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(info_frame, text=f"Name: {meet_name}", font=('Arial', 12, 'bold')).pack(anchor='w')
        ttk.Label(info_frame, text=f"Date: {meet_date}").pack(anchor='w')
        
        # Quick actions
        actions_frame = ttk.LabelFrame(frame, text="Quick Actions", padding="10")
        actions_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Button(actions_frame, text="Add Swimmer", 
                  command=self.add_swimmer_dialog).pack(fill='x', pady=5)
        ttk.Button(actions_frame, text="Add Event", 
                  command=self.add_event_dialog).pack(fill='x', pady=5)
        ttk.Button(actions_frame, text="Add Entry", 
                  command=self.add_entry_dialog).pack(fill='x', pady=5)
        ttk.Button(actions_frame, text="Import HY3 File", 
                  command=self.import_hy3).pack(fill='x', pady=5)
        ttk.Button(actions_frame, text="Seed All Events", 
                  command=self.seed_all_events).pack(fill='x', pady=5)
        ttk.Button(actions_frame, text="Generate Psych Sheet", 
                  command=self.generate_psych_sheet).pack(fill='x', pady=5)
        
        return frame
    
    def create_events_tab(self):
        """Create events tab with event list."""
        frame = ttk.Frame()
        
        # Toolbar
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(toolbar, text="Add Event", command=self.add_event_dialog).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Delete Event", command=self.delete_selected_event).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_events_list).pack(side='left', padx=2)
        
        # Treeview
        columns = ('Number', 'Name', 'Distance', 'Stroke', 'Gender')
        self.events_tree = ttk.Treeview(frame, columns=columns, show='headings')
        
        for col in columns:
            self.events_tree.heading(col, text=col)
            self.events_tree.column(col, width=100)
        
        self.events_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.events_tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.events_tree.configure(yscrollcommand=scrollbar.set)
        
        self.refresh_events_list()
        
        return frame
    
    def create_swimmers_tab(self):
        """Create swimmers tab with swimmer list."""
        frame = ttk.Frame()
        
        # Toolbar
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(toolbar, text="Add Swimmer", command=self.add_swimmer_dialog).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Delete Swimmer", command=self.delete_selected_swimmer).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_swimmers_list).pack(side='left', padx=2)
        
        # Treeview
        columns = ('Name', 'Team', 'Age', 'Gender', 'USAS ID')
        self.swimmers_tree = ttk.Treeview(frame, columns=columns, show='headings')
        
        for col in columns:
            self.swimmers_tree.heading(col, text=col)
            self.swimmers_tree.column(col, width=120)
        
        self.swimmers_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.swimmers_tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.swimmers_tree.configure(yscrollcommand=scrollbar.set)
        
        self.refresh_swimmers_list()
        
        return frame
    
    def create_entries_tab(self):
        """Create entries tab with entry list."""
        frame = ttk.Frame()
        
        # Toolbar
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(toolbar, text="Add Entry", command=self.add_entry_dialog).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Delete Entry", command=self.delete_selected_entry).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_entries_list).pack(side='left', padx=2)
        
        # Treeview
        columns = ('Swimmer', 'Event', 'Seed Time')
        self.entries_tree = ttk.Treeview(frame, columns=columns, show='headings')
        
        for col in columns:
            self.entries_tree.heading(col, text=col)
            self.entries_tree.column(col, width=200)
        
        self.entries_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.entries_tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.entries_tree.configure(yscrollcommand=scrollbar.set)
        
        self.refresh_entries_list()
        
        return frame
    
    def add_swimmer_dialog(self):
        """Show dialog to add a swimmer."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Swimmer")
        dialog.geometry("400x350")
        
        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill='both', expand=True)
        
        # Name
        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=name_var, width=30).grid(row=0, column=1, pady=5)
        
        # Team code
        ttk.Label(frame, text="Team Code:").grid(row=1, column=0, sticky='w', pady=5)
        team_code_var = tk.StringVar()
        ttk.Entry(frame, textvariable=team_code_var, width=30).grid(row=1, column=1, pady=5)
        
        # Team name
        ttk.Label(frame, text="Team Name:").grid(row=2, column=0, sticky='w', pady=5)
        team_name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=team_name_var, width=30).grid(row=2, column=1, pady=5)
        
        # Age
        ttk.Label(frame, text="Age:").grid(row=3, column=0, sticky='w', pady=5)
        age_var = tk.IntVar(value=0)
        ttk.Spinbox(frame, from_=0, to=99, textvariable=age_var, width=28).grid(row=3, column=1, pady=5)
        
        # Gender
        ttk.Label(frame, text="Gender:").grid(row=4, column=0, sticky='w', pady=5)
        gender_var = tk.StringVar()
        ttk.Combobox(frame, textvariable=gender_var, values=['M', 'F', 'X'], 
                    state='readonly', width=27).grid(row=4, column=1, pady=5)
        
        # USAS ID
        ttk.Label(frame, text="USAS ID (optional):").grid(row=5, column=0, sticky='w', pady=5)
        usas_var = tk.StringVar()
        ttk.Entry(frame, textvariable=usas_var, width=30).grid(row=5, column=1, pady=5)
        
        def save_swimmer():
            try:
                swimmer_id = get_or_insert_swimmer(
                    self.db_conn,
                    name=name_var.get(),
                    team_code=team_code_var.get(),
                    team_name=team_name_var.get() or team_code_var.get(),
                    age=age_var.get(),
                    gender=gender_var.get() or None,
                    usas_id=usas_var.get() or None
                )
                messagebox.showinfo("Success", f"Swimmer added (ID: {swimmer_id})")
                dialog.destroy()
                self.refresh_swimmers_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add swimmer: {e}")
        
        ttk.Button(frame, text="Add Swimmer", command=save_swimmer).grid(
            row=6, column=0, columnspan=2, pady=20
        )
    
    def add_event_dialog(self):
        """Show dialog to add an event."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Event")
        dialog.geometry("400x300")
        
        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill='both', expand=True)
        
        # Event number
        ttk.Label(frame, text="Event Number:").grid(row=0, column=0, sticky='w', pady=5)
        number_var = tk.IntVar()
        ttk.Entry(frame, textvariable=number_var, width=30).grid(row=0, column=1, pady=5)
        
        # Event name
        ttk.Label(frame, text="Event Name:").grid(row=1, column=0, sticky='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=name_var, width=30).grid(row=1, column=1, pady=5)
        
        # Distance
        ttk.Label(frame, text="Distance (yards/meters):").grid(row=2, column=0, sticky='w', pady=5)
        distance_var = tk.IntVar()
        ttk.Entry(frame, textvariable=distance_var, width=30).grid(row=2, column=1, pady=5)
        
        # Stroke
        ttk.Label(frame, text="Stroke:").grid(row=3, column=0, sticky='w', pady=5)
        stroke_var = tk.StringVar()
        ttk.Combobox(frame, textvariable=stroke_var, 
                    values=['FREE', 'BACK', 'BREAST', 'FLY', 'IM'], 
                    state='readonly', width=27).grid(row=3, column=1, pady=5)
        
        # Gender
        ttk.Label(frame, text="Gender:").grid(row=4, column=0, sticky='w', pady=5)
        gender_var = tk.StringVar()
        ttk.Combobox(frame, textvariable=gender_var, 
                    values=['M', 'F', 'Mixed'], 
                    state='readonly', width=27).grid(row=4, column=1, pady=5)
        
        def save_event():
            try:
                cursor = self.db_conn.cursor()
                cursor.execute("""
                    INSERT INTO events (number, name, distance, stroke, gender)
                    VALUES (?, ?, ?, ?, ?)
                """, (number_var.get(), name_var.get(), distance_var.get(), 
                     stroke_var.get(), gender_var.get()))
                self.db_conn.commit()
                messagebox.showinfo("Success", "Event added")
                dialog.destroy()
                self.refresh_events_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add event: {e}")
        
        ttk.Button(frame, text="Add Event", command=save_event).grid(
            row=5, column=0, columnspan=2, pady=20
        )
    
    def add_entry_dialog(self):
        """Show dialog to add an entry."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Entry")
        dialog.geometry("400x250")
        
        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill='both', expand=True)
        
        # Get swimmers and events for dropdowns
        cursor = self.db_conn.cursor()
        
        cursor.execute("SELECT id, name, team_id FROM swimmers ORDER BY name")
        swimmers = cursor.fetchall()
        swimmer_dict = {f"{s[1]} (ID:{s[0]})": s[0] for s in swimmers}
        
        cursor.execute("SELECT id, number, name FROM events ORDER BY number")
        events = cursor.fetchall()
        event_dict = {f"#{e[1]}: {e[2]}": e[0] for e in events}
        
        # Swimmer
        ttk.Label(frame, text="Swimmer:").grid(row=0, column=0, sticky='w', pady=5)
        swimmer_var = tk.StringVar()
        swimmer_combo = ttk.Combobox(frame, textvariable=swimmer_var, 
                                    values=list(swimmer_dict.keys()), 
                                    state='readonly', width=35)
        swimmer_combo.grid(row=0, column=1, pady=5)
        
        # Event
        ttk.Label(frame, text="Event:").grid(row=1, column=0, sticky='w', pady=5)
        event_var = tk.StringVar()
        event_combo = ttk.Combobox(frame, textvariable=event_var, 
                                   values=list(event_dict.keys()), 
                                   state='readonly', width=35)
        event_combo.grid(row=1, column=1, pady=5)
        
        # Seed time
        ttk.Label(frame, text="Seed Time (MM:SS.HH or NT):").grid(row=2, column=0, sticky='w', pady=5)
        time_var = tk.StringVar(value="NT")
        ttk.Entry(frame, textvariable=time_var, width=37).grid(row=2, column=1, pady=5)
        
        def save_entry():
            try:
                swimmer_id = swimmer_dict[swimmer_var.get()]
                event_id = event_dict[event_var.get()]
                seed_time = time_to_seconds(time_var.get())
                
                insert_or_update_entry(self.db_conn, swimmer_id, event_id, seed_time)
                messagebox.showinfo("Success", "Entry added")
                dialog.destroy()
                self.refresh_entries_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add entry: {e}")
        
        ttk.Button(frame, text="Add Entry", command=save_entry).grid(
            row=3, column=0, columnspan=2, pady=20
        )
    
    def import_hy3(self):
        """Import entries from HY3 file."""
        path = filedialog.askopenfilename(
            title="Select HY3 File",
            filetypes=[("HY3 Files", "*.hy3"), ("All Files", "*.*")]
        )
        
        if not path:
            return
        
        try:
            result = parse_hy3_file(path)
            
            if not result or 'swimmers' not in result:
                messagebox.showerror("Error", "Failed to parse HY3 file")
                return
            
            # Create a mapping of swimmer keys to swimmer IDs
            swimmer_map = {}
            
            # Insert swimmers
            for swimmer in result['swimmers']:
                swimmer_id = get_or_insert_swimmer(
                    self.db_conn,
                    name=swimmer['name'],
                    team_code=swimmer['team_code'],
                    team_name=swimmer['team_name'],
                    usas_id=swimmer.get('usas_id'),
                    age=swimmer.get('age', 0),
                    gender=swimmer.get('sex'),
                    date_of_birth=swimmer.get('birth_date')
                )
                swimmer_map[swimmer['name'] + "_" + swimmer['team_code']] = swimmer_id
                if swimmer.get('usas_id'):
                    swimmer_map[swimmer['usas_id']] = swimmer_id
            
            # Insert entries
            entries_added = 0
            for entry in result['entries']:
                swimmer_key = entry['swimmer_key']
                if swimmer_key not in swimmer_map:
                    continue
                
                swimmer_id = swimmer_map[swimmer_key]
                event_id = get_event_id(self.db_conn, int(entry['event_num']))
                
                if event_id:
                    insert_or_update_entry(self.db_conn, swimmer_id, event_id, entry['seed_time'])
                    entries_added += 1
            
            messagebox.showinfo(
                "Import Complete",
                f"Imported {len(result['swimmers'])} swimmers and {entries_added} entries"
            )
            
            self.refresh_swimmers_list()
            self.refresh_entries_list()
            
        except Exception as e:
            messagebox.showerror("Error", f"Import failed: {e}")
    
    def export_hy3(self):
        """Export meet to HY3 file."""
        path = filedialog.asksaveasfilename(
            title="Export to HY3",
            defaultextension=".hy3",
            filetypes=[("HY3 Files", "*.hy3"), ("All Files", "*.*")]
        )
        
        if path:
            try:
                success = export_to_hy3(self.db_conn, path)
                if success:
                    messagebox.showinfo("Success", f"Exported to {path}")
                else:
                    messagebox.showerror("Error", "Export failed")
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {e}")
    
    def generate_psych_sheet(self):
        """Generate psych sheet PDF."""
        path = filedialog.asksaveasfilename(
            title="Save Psych Sheet",
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        
        if path:
            try:
                success = generate_psych_sheet_pdf(self.db_conn, path)
                if success:
                    messagebox.showinfo("Success", f"Psych sheet saved to {path}")
                else:
                    messagebox.showerror("Error", "Failed to generate psych sheet")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate psych sheet: {e}")
    
    def seed_all_events(self):
        """Seed all events."""
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT id, number, name FROM events ORDER BY number")
            events = cursor.fetchall()
            
            lanes = int(get_meet_setting(self.db_conn, 'lanes', '6'))
            
            total_heats = 0
            for event in events:
                event_id = event[0]
                num_heats = apply_seeding(self.db_conn, event_id, method='circle', lanes=lanes)
                total_heats += num_heats
            
            messagebox.showinfo(
                "Seeding Complete",
                f"Seeded {len(events)} events with {total_heats} total heats"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Seeding failed: {e}")
    
    def refresh_events_list(self):
        """Refresh events list."""
        if not hasattr(self, 'events_tree'):
            return
        
        for item in self.events_tree.get_children():
            self.events_tree.delete(item)
        
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT number, name, distance, stroke, gender FROM events ORDER BY number")
        
        for row in cursor.fetchall():
            self.events_tree.insert('', 'end', values=row)
    
    def refresh_swimmers_list(self):
        """Refresh swimmers list."""
        if not hasattr(self, 'swimmers_tree'):
            return
        
        for item in self.swimmers_tree.get_children():
            self.swimmers_tree.delete(item)
        
        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT s.name, t.team_code, s.age, s.gender, s.usas_id
            FROM swimmers s
            LEFT JOIN teams t ON s.team_id = t.id
            ORDER BY s.name
        """)
        
        for row in cursor.fetchall():
            self.swimmers_tree.insert('', 'end', values=row)
    
    def refresh_entries_list(self):
        """Refresh entries list."""
        if not hasattr(self, 'entries_tree'):
            return
        
        for item in self.entries_tree.get_children():
            self.entries_tree.delete(item)
        
        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT s.name, ev.number || ': ' || ev.name, e.seed_time
            FROM entries e
            JOIN swimmers s ON e.swimmer_id = s.id
            JOIN events ev ON e.event_id = ev.id
            ORDER BY ev.number, e.seed_time
        """)
        
        from src.hy3_parser import seconds_to_time_str
        for row in cursor.fetchall():
            time_str = seconds_to_time_str(row[2])
            self.entries_tree.insert('', 'end', values=(row[0], row[1], time_str))
    
    def delete_selected_event(self):
        """Delete selected event."""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an event to delete")
            return
        
        if messagebox.askyesno("Confirm", "Delete selected event and all entries?"):
            try:
                item = self.events_tree.item(selection[0])
                event_num = item['values'][0]
                
                cursor = self.db_conn.cursor()
                cursor.execute("DELETE FROM events WHERE number = ?", (event_num,))
                self.db_conn.commit()
                
                self.refresh_events_list()
                messagebox.showinfo("Success", "Event deleted")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete event: {e}")
    
    def delete_selected_swimmer(self):
        """Delete selected swimmer."""
        selection = self.swimmers_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a swimmer to delete")
            return
        
        if messagebox.askyesno("Confirm", "Delete selected swimmer and all entries?"):
            try:
                item = self.swimmers_tree.item(selection[0])
                swimmer_name = item['values'][0]
                
                cursor = self.db_conn.cursor()
                cursor.execute("DELETE FROM swimmers WHERE name = ?", (swimmer_name,))
                self.db_conn.commit()
                
                self.refresh_swimmers_list()
                self.refresh_entries_list()
                messagebox.showinfo("Success", "Swimmer deleted")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete swimmer: {e}")
    
    def delete_selected_entry(self):
        """Delete selected entry."""
        selection = self.entries_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an entry to delete")
            return
        
        if messagebox.askyesno("Confirm", "Delete selected entry?"):
            try:
                item = self.entries_tree.item(selection[0])
                swimmer_name = item['values'][0]
                event_info = item['values'][1]
                
                cursor = self.db_conn.cursor()
                cursor.execute("""
                    DELETE FROM entries 
                    WHERE swimmer_id = (SELECT id FROM swimmers WHERE name = ?)
                    AND event_id = (SELECT id FROM events WHERE number || ': ' || name = ?)
                """, (swimmer_name, event_info))
                self.db_conn.commit()
                
                self.refresh_entries_list()
                messagebox.showinfo("Success", "Entry deleted")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete entry: {e}")
