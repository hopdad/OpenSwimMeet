"""
Main application for OpenSwimMeet using tkinter.
Enhanced with Results Entry, Team Scoring, Validation, Backup, Undo, and keyboard shortcuts.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import sqlite3
from pathlib import Path
from datetime import datetime

from src.database import (
    init_db, open_meet_db, get_or_insert_swimmer, get_or_insert_team,
    get_event_id, insert_or_update_entry, get_meet_setting, set_meet_setting,
    save_result, calculate_places, assign_points, check_records,
    get_team_scores, validate_meet, get_meet_stats, create_backup,
    list_backups, restore_backup, save_undo_point, undo_last_action,
    get_undo_history, check_in_swimmer, check_out_swimmer,
    get_check_in_status, add_announcement, get_announcements,
    SCORING_TABLES, DQ_CODES,
)
from src.hy3_parser import parse_hy3_file, time_to_seconds, seconds_to_time_str
from src.hy3_exporter import export_to_hy3
from src.seeding import apply_seeding, get_heat_sheet
from src.psych_sheets import generate_psych_sheet_pdf, generate_heat_sheet_pdf


class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OpenSwimMeet - Swim Meet Manager")
        self.root.geometry("1100x750")

        self.current_meet_path = None
        self.db_conn = None
        self.notebook = None
        self._autosave_id = None

        # Configure style
        style = ttk.Style()
        style.theme_use('clam')

        self._bind_global_shortcuts()
        self.show_welcome_screen()

    # ─── Keyboard Shortcuts ────────────────────────────────────────────

    def _bind_global_shortcuts(self):
        """Bind global keyboard shortcuts."""
        self.root.bind('<Control-n>', lambda e: self.new_meet())
        self.root.bind('<Control-o>', lambda e: self.open_meet())
        self.root.bind('<Control-s>', lambda e: self.seed_all_events() if self.db_conn else None)
        self.root.bind('<Control-i>', lambda e: self.import_hy3() if self.db_conn else None)
        self.root.bind('<Control-e>', lambda e: self.export_hy3() if self.db_conn else None)
        self.root.bind('<Control-p>', lambda e: self.generate_psych_sheet() if self.db_conn else None)
        self.root.bind('<Control-z>', lambda e: self.undo_action() if self.db_conn else None)
        self.root.bind('<Control-b>', lambda e: self.backup_meet() if self.db_conn else None)
        self.root.bind('<Control-v>', lambda e: self.show_validation_dialog() if self.db_conn else None)
        self.root.bind('<F5>', lambda e: self._refresh_all() if self.db_conn else None)

    # ─── Window Management ─────────────────────────────────────────────

    def clear_window(self):
        """Clear all widgets from window."""
        if self._autosave_id:
            self.root.after_cancel(self._autosave_id)
            self._autosave_id = None
        for widget in self.root.winfo_children():
            widget.destroy()

    def _refresh_all(self):
        """Refresh all visible lists."""
        self.refresh_events_list()
        self.refresh_swimmers_list()
        self.refresh_entries_list()
        if hasattr(self, 'scores_tree'):
            self.refresh_scores()

    # ─── Welcome Screen ───────────────────────────────────────────────

    def show_welcome_screen(self):
        """Show welcome screen with New/Open options."""
        self.clear_window()

        frame = ttk.Frame(self.root, padding="20")
        frame.pack(expand=True, fill='both')

        ttk.Label(frame, text="OpenSwimMeet", font=('Arial', 28, 'bold')).pack(pady=20)
        ttk.Label(
            frame,
            text="Offline swimming meet management \u2013 intuitive & Hy-Tek compatible",
            font=('Arial', 12)
        ).pack(pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=40)

        ttk.Button(btn_frame, text="New Meet  (Ctrl+N)", command=self.new_meet, width=25).pack(pady=10)
        ttk.Button(btn_frame, text="Open Existing Meet  (Ctrl+O)", command=self.open_meet, width=25).pack(pady=10)

        # Shortcuts hint
        ttk.Label(frame, text="Tip: Use keyboard shortcuts for quick access",
                  font=('Arial', 9), foreground='grey').pack(pady=20)

    # ─── Meet Open / Create ────────────────────────────────────────────

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
        wizard.geometry("500x450")
        wizard.grab_set()

        frame = ttk.Frame(wizard, padding="20")
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Meet Name:").grid(row=0, column=0, sticky='w', pady=5)
        meet_name_var = tk.StringVar(value="Swim Meet")
        ttk.Entry(frame, textvariable=meet_name_var, width=40).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Meet Date:").grid(row=1, column=0, sticky='w', pady=5)
        meet_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=meet_date_var, width=40).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Course:").grid(row=2, column=0, sticky='w', pady=5)
        course_var = tk.StringVar(value="SCY")
        ttk.Combobox(frame, textvariable=course_var,
                     values=["SCY", "SCM", "LCM"], state='readonly', width=37).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Meet Type:").grid(row=3, column=0, sticky='w', pady=5)
        type_var = tk.StringVar(value="Dual")
        ttk.Combobox(frame, textvariable=type_var,
                     values=["Dual", "Invitational", "Championship"],
                     state='readonly', width=37).grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="Number of Lanes:").grid(row=4, column=0, sticky='w', pady=5)
        lanes_var = tk.IntVar(value=6)
        ttk.Spinbox(frame, from_=4, to=10, textvariable=lanes_var, width=38).grid(row=4, column=1, pady=5)

        ttk.Label(frame, text="Scoring Type:").grid(row=5, column=0, sticky='w', pady=5)
        scoring_var = tk.StringVar(value="dual")
        scoring_combo = ttk.Combobox(frame, textvariable=scoring_var,
                                     values=list(SCORING_TABLES.keys()),
                                     state='readonly', width=37)
        scoring_combo.grid(row=5, column=1, pady=5)

        def save_and_continue():
            set_meet_setting(self.db_conn, 'meet_name', meet_name_var.get())
            set_meet_setting(self.db_conn, 'meet_date', meet_date_var.get())
            set_meet_setting(self.db_conn, 'course', course_var.get())
            set_meet_setting(self.db_conn, 'meet_type', type_var.get())
            set_meet_setting(self.db_conn, 'lanes', str(lanes_var.get()))
            set_meet_setting(self.db_conn, 'scoring_type', scoring_var.get())
            wizard.destroy()
            self.show_main_dashboard()

        ttk.Button(frame, text="Save & Continue", command=save_and_continue).grid(
            row=6, column=0, columnspan=2, pady=20
        )

    # ─── Main Dashboard ───────────────────────────────────────────────

    def show_main_dashboard(self):
        """Show main dashboard with tabs."""
        self.clear_window()
        self._build_menu_bar()

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # Dashboard tab
        self.notebook.add(self.create_dashboard_tab(), text="Dashboard")
        # Events tab
        self.notebook.add(self.create_events_tab(), text="Events")
        # Swimmers tab
        self.notebook.add(self.create_swimmers_tab(), text="Swimmers")
        # Entries tab
        self.notebook.add(self.create_entries_tab(), text="Entries")
        # Results tab
        self.notebook.add(self.create_results_tab(), text="Results")
        # Scoring tab
        self.notebook.add(self.create_scoring_tab(), text="Scoring")

        # Start autosave timer (every 60 seconds)
        self._start_autosave()

    def _build_menu_bar(self):
        """Build the application menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Meet        Ctrl+N", command=self.new_meet)
        file_menu.add_command(label="Open Meet       Ctrl+O", command=self.open_meet)
        file_menu.add_separator()
        file_menu.add_command(label="Backup Meet     Ctrl+B", command=self.backup_meet)
        file_menu.add_command(label="Restore Backup...", command=self.restore_backup_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo            Ctrl+Z", command=self.undo_action)
        edit_menu.add_command(label="Undo History...", command=self.show_undo_history)

        # Import menu
        import_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Import", menu=import_menu)
        import_menu.add_command(label="Import HY3 File   Ctrl+I", command=self.import_hy3)

        # Export menu
        export_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Export", menu=export_menu)
        export_menu.add_command(label="Export to HY3      Ctrl+E", command=self.export_hy3)
        export_menu.add_command(label="Psych Sheet PDF    Ctrl+P", command=self.generate_psych_sheet)
        export_menu.add_command(label="Heat Sheet PDF...", command=self.generate_heat_sheet)

        # Meet menu
        meet_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Meet", menu=meet_menu)
        meet_menu.add_command(label="Seed All Events    Ctrl+S", command=self.seed_all_events)
        meet_menu.add_command(label="Validate Meet      Ctrl+V", command=self.show_validation_dialog)
        meet_menu.add_command(label="Meet Statistics...", command=self.show_meet_stats)
        meet_menu.add_separator()
        meet_menu.add_command(label="Refresh All        F5", command=self._refresh_all)

    # ─── Autosave ──────────────────────────────────────────────────────

    def _start_autosave(self):
        """Start autosave timer (backup every 60 seconds)."""
        if self.current_meet_path and self.db_conn:
            create_backup(self.current_meet_path)
        self._autosave_id = self.root.after(60000, self._start_autosave)

    # ─── Dashboard Tab ─────────────────────────────────────────────────

    def create_dashboard_tab(self):
        """Create dashboard tab with meet info, stats, and quick actions."""
        frame = ttk.Frame()

        # Top row: meet info + stats side by side
        top_frame = ttk.Frame(frame)
        top_frame.pack(fill='x', padx=10, pady=10)

        # Meet info (left)
        meet_name = get_meet_setting(self.db_conn, 'meet_name', 'Untitled Meet')
        meet_date = get_meet_setting(self.db_conn, 'meet_date', '')
        course = get_meet_setting(self.db_conn, 'course', 'SCY')
        meet_type = get_meet_setting(self.db_conn, 'meet_type', 'Dual')

        info_frame = ttk.LabelFrame(top_frame, text="Meet Information", padding="10")
        info_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))

        ttk.Label(info_frame, text=f"Name: {meet_name}", font=('Arial', 12, 'bold')).pack(anchor='w')
        ttk.Label(info_frame, text=f"Date: {meet_date}").pack(anchor='w')
        ttk.Label(info_frame, text=f"Course: {course}  |  Type: {meet_type}").pack(anchor='w')
        ttk.Label(info_frame, text=f"Database: {self.current_meet_path}",
                  foreground='grey').pack(anchor='w', pady=(5, 0))

        # Stats (right)
        stats = get_meet_stats(self.db_conn)
        stats_frame = ttk.LabelFrame(top_frame, text="Meet Statistics", padding="10")
        stats_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))

        stats_text = (
            f"Teams: {stats['total_teams']}    "
            f"Swimmers: {stats['total_swimmers']}    "
            f"Checked In: {stats['checked_in']}\n"
            f"Events: {stats['total_events']} "
            f"({stats['individual_events']} ind / {stats['relay_events']} relay)\n"
            f"Entries: {stats['total_entries']}    "
            f"Seeded: {stats['events_seeded']}/{stats['total_events']}    "
            f"Results: {stats['events_with_results']}/{stats['total_events']}\n"
            f"DQs: {stats['total_dqs']}    No-Shows: {stats['total_ns']}"
        )
        ttk.Label(stats_frame, text=stats_text, justify='left').pack(anchor='w')

        # Quick actions
        actions_frame = ttk.LabelFrame(frame, text="Quick Actions", padding="10")
        actions_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        # Two columns of buttons
        left_col = ttk.Frame(actions_frame)
        left_col.pack(side='left', fill='both', expand=True, padx=5)
        right_col = ttk.Frame(actions_frame)
        right_col.pack(side='right', fill='both', expand=True, padx=5)

        ttk.Button(left_col, text="Add Swimmer", command=self.add_swimmer_dialog).pack(fill='x', pady=3)
        ttk.Button(left_col, text="Add Event", command=self.add_event_dialog).pack(fill='x', pady=3)
        ttk.Button(left_col, text="Add Entry", command=self.add_entry_dialog).pack(fill='x', pady=3)
        ttk.Button(left_col, text="Import HY3 File  (Ctrl+I)", command=self.import_hy3).pack(fill='x', pady=3)

        ttk.Button(right_col, text="Seed All Events  (Ctrl+S)", command=self.seed_all_events).pack(fill='x', pady=3)
        ttk.Button(right_col, text="Enter Results", command=self.results_entry_dialog).pack(fill='x', pady=3)
        ttk.Button(right_col, text="Psych Sheet PDF  (Ctrl+P)", command=self.generate_psych_sheet).pack(fill='x', pady=3)
        ttk.Button(right_col, text="Validate Meet  (Ctrl+V)", command=self.show_validation_dialog).pack(fill='x', pady=3)

        return frame

    # ─── Events Tab ────────────────────────────────────────────────────

    def create_events_tab(self):
        """Create events tab with event list."""
        frame = ttk.Frame()

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=5, pady=5)

        ttk.Button(toolbar, text="Add Event", command=self.add_event_dialog).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Delete Event", command=self.delete_selected_event).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_events_list).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Generate Heat Sheet", command=self.generate_heat_sheet_for_selected).pack(side='left', padx=2)

        # Search
        ttk.Label(toolbar, text="  Search:").pack(side='left', padx=(10, 2))
        self.events_search_var = tk.StringVar()
        self.events_search_var.trace_add('write', lambda *a: self.refresh_events_list())
        ttk.Entry(toolbar, textvariable=self.events_search_var, width=20).pack(side='left', padx=2)

        columns = ('Number', 'Name', 'Distance', 'Stroke', 'Gender', 'Entries', 'Heats')
        self.events_tree = ttk.Treeview(frame, columns=columns, show='headings')

        col_widths = {'Number': 70, 'Name': 200, 'Distance': 80, 'Stroke': 80,
                      'Gender': 70, 'Entries': 70, 'Heats': 70}
        for col in columns:
            self.events_tree.heading(col, text=col)
            self.events_tree.column(col, width=col_widths.get(col, 100))

        self.events_tree.pack(fill='both', expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.events_tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.events_tree.configure(yscrollcommand=scrollbar.set)

        self.refresh_events_list()
        return frame

    # ─── Swimmers Tab ──────────────────────────────────────────────────

    def create_swimmers_tab(self):
        """Create swimmers tab with swimmer list."""
        frame = ttk.Frame()

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=5, pady=5)

        ttk.Button(toolbar, text="Add Swimmer", command=self.add_swimmer_dialog).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Delete Swimmer", command=self.delete_selected_swimmer).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Check In", command=self.check_in_selected).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_swimmers_list).pack(side='left', padx=2)

        # Search
        ttk.Label(toolbar, text="  Search:").pack(side='left', padx=(10, 2))
        self.swimmers_search_var = tk.StringVar()
        self.swimmers_search_var.trace_add('write', lambda *a: self.refresh_swimmers_list())
        ttk.Entry(toolbar, textvariable=self.swimmers_search_var, width=20).pack(side='left', padx=2)

        columns = ('Name', 'Team', 'Age', 'Gender', 'USAS ID', 'Checked In')
        self.swimmers_tree = ttk.Treeview(frame, columns=columns, show='headings')

        for col in columns:
            self.swimmers_tree.heading(col, text=col)
            self.swimmers_tree.column(col, width=100 if col != 'Name' else 180)

        self.swimmers_tree.pack(fill='both', expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.swimmers_tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.swimmers_tree.configure(yscrollcommand=scrollbar.set)

        self.refresh_swimmers_list()
        return frame

    # ─── Entries Tab ───────────────────────────────────────────────────

    def create_entries_tab(self):
        """Create entries tab with entry list."""
        frame = ttk.Frame()

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=5, pady=5)

        ttk.Button(toolbar, text="Add Entry", command=self.add_entry_dialog).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Delete Entry", command=self.delete_selected_entry).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_entries_list).pack(side='left', padx=2)

        # Search
        ttk.Label(toolbar, text="  Search:").pack(side='left', padx=(10, 2))
        self.entries_search_var = tk.StringVar()
        self.entries_search_var.trace_add('write', lambda *a: self.refresh_entries_list())
        ttk.Entry(toolbar, textvariable=self.entries_search_var, width=20).pack(side='left', padx=2)

        columns = ('Swimmer', 'Event', 'Seed Time')
        self.entries_tree = ttk.Treeview(frame, columns=columns, show='headings')

        for col in columns:
            self.entries_tree.heading(col, text=col)
            self.entries_tree.column(col, width=200)

        self.entries_tree.pack(fill='both', expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.entries_tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.entries_tree.configure(yscrollcommand=scrollbar.set)

        self.refresh_entries_list()
        return frame

    # ─── Results Tab ───────────────────────────────────────────────────

    def create_results_tab(self):
        """Create results tab showing entered results."""
        frame = ttk.Frame()

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=5, pady=5)

        ttk.Button(toolbar, text="Enter Results", command=self.results_entry_dialog).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_results_list).pack(side='left', padx=2)

        columns = ('Event', 'Heat', 'Lane', 'Swimmer', 'Team', 'Time', 'Place', 'Points', 'DQ')
        self.results_tree = ttk.Treeview(frame, columns=columns, show='headings')

        col_widths = {'Event': 60, 'Heat': 50, 'Lane': 50, 'Swimmer': 170, 'Team': 70,
                      'Time': 80, 'Place': 50, 'Points': 60, 'DQ': 50}
        for col in columns:
            self.results_tree.heading(col, text=col)
            self.results_tree.column(col, width=col_widths.get(col, 80))

        self.results_tree.pack(fill='both', expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.results_tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.results_tree.configure(yscrollcommand=scrollbar.set)

        self.refresh_results_list()
        return frame

    # ─── Scoring Tab ───────────────────────────────────────────────────

    def create_scoring_tab(self):
        """Create team scoring tab."""
        frame = ttk.Frame()

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=5, pady=5)

        ttk.Label(toolbar, text="Scoring Type:").pack(side='left', padx=2)
        self.scoring_type_var = tk.StringVar(
            value=get_meet_setting(self.db_conn, 'scoring_type', 'dual'))
        scoring_combo = ttk.Combobox(toolbar, textvariable=self.scoring_type_var,
                                     values=list(SCORING_TABLES.keys()),
                                     state='readonly', width=15)
        scoring_combo.pack(side='left', padx=2)
        scoring_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_scores())

        ttk.Button(toolbar, text="Refresh Scores", command=self.refresh_scores).pack(side='left', padx=10)
        ttk.Button(toolbar, text="Calculate All Scores", command=self.calculate_all_scores).pack(side='left', padx=2)

        columns = ('Rank', 'Team', 'Name', 'Boys', 'Girls', 'Relay', 'Total')
        self.scores_tree = ttk.Treeview(frame, columns=columns, show='headings')

        col_widths = {'Rank': 50, 'Team': 80, 'Name': 200, 'Boys': 80,
                      'Girls': 80, 'Relay': 80, 'Total': 80}
        for col in columns:
            self.scores_tree.heading(col, text=col)
            self.scores_tree.column(col, width=col_widths.get(col, 80))

        self.scores_tree.pack(fill='both', expand=True, padx=5, pady=5)

        self.refresh_scores()
        return frame

    # ─── Refresh Functions ─────────────────────────────────────────────

    def refresh_events_list(self):
        """Refresh events list with optional search filter."""
        if not hasattr(self, 'events_tree'):
            return

        for item in self.events_tree.get_children():
            self.events_tree.delete(item)

        search = self.events_search_var.get().lower() if hasattr(self, 'events_search_var') else ''

        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT ev.number, ev.name, ev.distance, ev.stroke, ev.gender, ev.id
            FROM events ev ORDER BY ev.number
        """)

        for row in cursor.fetchall():
            num, name, dist, stroke, gender, event_id = row
            display_name = name or ''
            if search and search not in f"{num} {display_name} {stroke} {gender}".lower():
                continue

            # Count entries and heats
            cursor.execute("SELECT COUNT(*) FROM entries WHERE event_id = ?", (event_id,))
            entry_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM heats WHERE event_id = ?", (event_id,))
            heat_count = cursor.fetchone()[0]

            self.events_tree.insert('', 'end', values=(num, display_name, dist, stroke, gender,
                                                        entry_count, heat_count),
                                    iid=str(event_id))

    def refresh_swimmers_list(self):
        """Refresh swimmers list with optional search filter."""
        if not hasattr(self, 'swimmers_tree'):
            return

        for item in self.swimmers_tree.get_children():
            self.swimmers_tree.delete(item)

        search = self.swimmers_search_var.get().lower() if hasattr(self, 'swimmers_search_var') else ''

        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT s.id, s.name, t.team_code, s.age, s.gender, s.usas_id, s.checked_in
            FROM swimmers s
            LEFT JOIN teams t ON s.team_id = t.id
            ORDER BY s.name
        """)

        for row in cursor.fetchall():
            sid, name, team, age, gender, usas, checked_in = row
            if search and search not in f"{name} {team} {usas}".lower():
                continue
            check_str = "Yes" if checked_in else ""
            self.swimmers_tree.insert('', 'end',
                                      values=(name, team, age, gender, usas, check_str),
                                      iid=str(sid))

    def refresh_entries_list(self):
        """Refresh entries list with optional search filter."""
        if not hasattr(self, 'entries_tree'):
            return

        for item in self.entries_tree.get_children():
            self.entries_tree.delete(item)

        search = self.entries_search_var.get().lower() if hasattr(self, 'entries_search_var') else ''

        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT s.name, ev.number || ': ' || ev.name, e.seed_time
            FROM entries e
            JOIN swimmers s ON e.swimmer_id = s.id
            JOIN events ev ON e.event_id = ev.id
            ORDER BY ev.number, e.seed_time
        """)

        for row in cursor.fetchall():
            swimmer_name, event_info, seed_time = row
            if search and search not in f"{swimmer_name} {event_info}".lower():
                continue
            time_str = seconds_to_time_str(seed_time)
            self.entries_tree.insert('', 'end', values=(swimmer_name, event_info, time_str))

    def refresh_results_list(self):
        """Refresh results list."""
        if not hasattr(self, 'results_tree'):
            return

        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT ev.number, h.heat_number, r.lane, s.name, t.team_code,
                   r.finish_time, r.place, r.points, r.dq, r.dq_code, r.ns
            FROM results r
            JOIN heats h ON r.heat_id = h.id
            JOIN events ev ON h.event_id = ev.id
            JOIN entries e ON r.entry_id = e.id
            JOIN swimmers s ON e.swimmer_id = s.id
            JOIN teams t ON s.team_id = t.id
            ORDER BY ev.number, h.heat_number, r.lane
        """)

        for row in cursor.fetchall():
            ev_num, heat_num, lane, name, team, ftime, place, points, dq, dq_code, ns = row
            if ns:
                time_str = "NS"
            elif dq:
                time_str = f"DQ ({dq_code})" if dq_code else "DQ"
            else:
                time_str = seconds_to_time_str(ftime)
            place_str = str(place) if place else ""
            points_str = f"{points:.0f}" if points else ""
            dq_str = dq_code if dq else ""
            self.results_tree.insert('', 'end', values=(
                ev_num, heat_num, lane, name, team, time_str, place_str, points_str, dq_str
            ))

    def refresh_scores(self):
        """Refresh team scores."""
        if not hasattr(self, 'scores_tree'):
            return

        for item in self.scores_tree.get_children():
            self.scores_tree.delete(item)

        scoring_type = self.scoring_type_var.get() if hasattr(self, 'scoring_type_var') else 'dual'
        scores = get_team_scores(self.db_conn, scoring_type)

        for rank, score in enumerate(scores, 1):
            self.scores_tree.insert('', 'end', values=(
                rank, score['team_code'], score['team_name'],
                f"{score['boys']:.0f}", f"{score['girls']:.0f}",
                f"{score['relay']:.0f}", f"{score['total']:.0f}"
            ))

    # ─── Results Entry Dialog ──────────────────────────────────────────

    def results_entry_dialog(self):
        """Show dialog to enter results for a heat."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Enter Results")
        dialog.geometry("700x550")
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill='both', expand=True)

        # Event selector
        top = ttk.Frame(frame)
        top.pack(fill='x', pady=5)

        ttk.Label(top, text="Event:").pack(side='left', padx=2)
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id, number, name FROM events ORDER BY number")
        events = cursor.fetchall()
        event_dict = {f"#{e[1]}: {e[2]}": e[0] for e in events}

        event_var = tk.StringVar()
        event_combo = ttk.Combobox(top, textvariable=event_var,
                                   values=list(event_dict.keys()),
                                   state='readonly', width=40)
        event_combo.pack(side='left', padx=5)

        ttk.Label(top, text="Heat:").pack(side='left', padx=5)
        heat_var = tk.StringVar()
        heat_combo = ttk.Combobox(top, textvariable=heat_var, state='readonly', width=8)
        heat_combo.pack(side='left', padx=2)

        # Lane entries frame
        lanes_frame = ttk.LabelFrame(frame, text="Lane Results", padding="10")
        lanes_frame.pack(fill='both', expand=True, pady=10)

        lane_widgets = {}  # lane -> {name_label, time_entry, dq_var, ns_var}

        def load_heat(*args):
            """Load lane assignments for the selected heat."""
            for w in lanes_frame.winfo_children():
                w.destroy()
            lane_widgets.clear()

            event_key = event_var.get()
            heat_num = heat_var.get()
            if not event_key or not heat_num:
                return

            event_id = event_dict[event_key]

            cursor.execute("""
                SELECT ha.lane, s.name, t.team_code, ha.entry_id, ha.heat_id, e.seed_time
                FROM heat_assignments ha
                JOIN heats h ON ha.heat_id = h.id
                JOIN entries e ON ha.entry_id = e.id
                JOIN swimmers s ON e.swimmer_id = s.id
                JOIN teams t ON s.team_id = t.id
                WHERE h.event_id = ? AND h.heat_number = ?
                ORDER BY ha.lane
            """, (event_id, int(heat_num)))

            assignments = cursor.fetchall()

            # Headers
            ttk.Label(lanes_frame, text="Lane", font=('Arial', 9, 'bold')).grid(row=0, column=0, padx=3)
            ttk.Label(lanes_frame, text="Swimmer", font=('Arial', 9, 'bold')).grid(row=0, column=1, padx=3)
            ttk.Label(lanes_frame, text="Team", font=('Arial', 9, 'bold')).grid(row=0, column=2, padx=3)
            ttk.Label(lanes_frame, text="Seed", font=('Arial', 9, 'bold')).grid(row=0, column=3, padx=3)
            ttk.Label(lanes_frame, text="Finish Time", font=('Arial', 9, 'bold')).grid(row=0, column=4, padx=3)
            ttk.Label(lanes_frame, text="DQ", font=('Arial', 9, 'bold')).grid(row=0, column=5, padx=3)
            ttk.Label(lanes_frame, text="NS", font=('Arial', 9, 'bold')).grid(row=0, column=6, padx=3)
            ttk.Label(lanes_frame, text="DQ Code", font=('Arial', 9, 'bold')).grid(row=0, column=7, padx=3)

            for i, (lane, name, team, entry_id, heat_id, seed_time) in enumerate(assignments, 1):
                ttk.Label(lanes_frame, text=str(lane)).grid(row=i, column=0, padx=3, pady=2)
                ttk.Label(lanes_frame, text=name, width=20, anchor='w').grid(row=i, column=1, padx=3, pady=2)
                ttk.Label(lanes_frame, text=team).grid(row=i, column=2, padx=3, pady=2)
                ttk.Label(lanes_frame, text=seconds_to_time_str(seed_time)).grid(row=i, column=3, padx=3, pady=2)

                time_entry = ttk.Entry(lanes_frame, width=12)
                time_entry.grid(row=i, column=4, padx=3, pady=2)

                # Check for existing result
                cursor.execute(
                    "SELECT finish_time, dq, ns, dq_code FROM results WHERE entry_id = ? AND heat_id = ?",
                    (entry_id, heat_id))
                existing = cursor.fetchone()
                if existing:
                    if existing[0] is not None:
                        time_entry.insert(0, seconds_to_time_str(existing[0]))

                dq_var = tk.BooleanVar(value=bool(existing[1]) if existing else False)
                ttk.Checkbutton(lanes_frame, variable=dq_var).grid(row=i, column=5, padx=3, pady=2)

                ns_var = tk.BooleanVar(value=bool(existing[2]) if existing else False)
                ttk.Checkbutton(lanes_frame, variable=ns_var).grid(row=i, column=6, padx=3, pady=2)

                dq_code_var = tk.StringVar(value=existing[3] if existing and existing[3] else '')
                dq_combo = ttk.Combobox(lanes_frame, textvariable=dq_code_var,
                                        values=list(DQ_CODES.keys()), width=5)
                dq_combo.grid(row=i, column=7, padx=3, pady=2)

                lane_widgets[lane] = {
                    'entry_id': entry_id,
                    'heat_id': heat_id,
                    'time_entry': time_entry,
                    'dq_var': dq_var,
                    'ns_var': ns_var,
                    'dq_code_var': dq_code_var,
                }

        def on_event_change(*args):
            """Update heat list when event changes."""
            heat_combo.set('')
            event_key = event_var.get()
            if not event_key:
                return
            event_id = event_dict[event_key]
            cursor.execute("SELECT heat_number FROM heats WHERE event_id = ? ORDER BY heat_number",
                          (event_id,))
            heats = [str(r[0]) for r in cursor.fetchall()]
            heat_combo['values'] = heats
            if heats:
                heat_combo.set(heats[0])
                load_heat()

        event_combo.bind('<<ComboboxSelected>>', on_event_change)
        heat_combo.bind('<<ComboboxSelected>>', load_heat)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=5)

        def save_results():
            """Save all entered results."""
            event_key = event_var.get()
            if not event_key:
                return
            event_id = event_dict[event_key]

            saved = 0
            for lane, widgets in lane_widgets.items():
                time_str = widgets['time_entry'].get().strip()
                finish_time = time_to_seconds(time_str) if time_str else None
                dq = widgets['dq_var'].get()
                ns = widgets['ns_var'].get()
                dq_code = widgets['dq_code_var'].get() or None

                save_result(
                    self.db_conn,
                    entry_id=widgets['entry_id'],
                    heat_id=widgets['heat_id'],
                    lane=lane,
                    finish_time=finish_time,
                    dq=dq,
                    dq_code=dq_code,
                    ns=ns,
                )
                saved += 1

            # Calculate places and points
            scoring_type = get_meet_setting(self.db_conn, 'scoring_type', 'dual')
            calculate_places(self.db_conn, event_id)
            assign_points(self.db_conn, event_id, scoring_type)

            # Check for broken records
            broken = check_records(self.db_conn, event_id)

            msg = f"Saved {saved} results."
            if broken:
                record_msgs = [f"  NEW {r['record_type'].upper()} RECORD: {r['swimmer_name']} "
                              f"({seconds_to_time_str(r['new_time'])})" for r in broken]
                msg += "\n\nRECORDS BROKEN:\n" + "\n".join(record_msgs)

            messagebox.showinfo("Results Saved", msg)
            self.refresh_results_list()
            if hasattr(self, 'scores_tree'):
                self.refresh_scores()

        ttk.Button(btn_frame, text="Save Results", command=save_results).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

    # ─── Add Dialogs ──────────────────────────────────────────────────

    def add_swimmer_dialog(self):
        """Show dialog to add a swimmer."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Swimmer")
        dialog.geometry("400x350")
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=name_var, width=30).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Team Code:").grid(row=1, column=0, sticky='w', pady=5)
        team_code_var = tk.StringVar()
        ttk.Entry(frame, textvariable=team_code_var, width=30).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Team Name:").grid(row=2, column=0, sticky='w', pady=5)
        team_name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=team_name_var, width=30).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Age:").grid(row=3, column=0, sticky='w', pady=5)
        age_var = tk.IntVar(value=0)
        ttk.Spinbox(frame, from_=0, to=99, textvariable=age_var, width=28).grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="Gender:").grid(row=4, column=0, sticky='w', pady=5)
        gender_var = tk.StringVar()
        ttk.Combobox(frame, textvariable=gender_var, values=['M', 'F', 'X'],
                     state='readonly', width=27).grid(row=4, column=1, pady=5)

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
                save_undo_point(self.db_conn, 'insert', 'swimmers', swimmer_id,
                               description=f"Added swimmer {name_var.get()}")
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
        dialog.geometry("400x350")
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Event Number:").grid(row=0, column=0, sticky='w', pady=5)
        number_var = tk.IntVar()
        ttk.Entry(frame, textvariable=number_var, width=30).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Event Name:").grid(row=1, column=0, sticky='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=name_var, width=30).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Distance:").grid(row=2, column=0, sticky='w', pady=5)
        distance_var = tk.IntVar()
        ttk.Entry(frame, textvariable=distance_var, width=30).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Stroke:").grid(row=3, column=0, sticky='w', pady=5)
        stroke_var = tk.StringVar()
        ttk.Combobox(frame, textvariable=stroke_var,
                     values=['FREE', 'BACK', 'BREAST', 'FLY', 'IM'],
                     state='readonly', width=27).grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="Gender:").grid(row=4, column=0, sticky='w', pady=5)
        gender_var = tk.StringVar()
        ttk.Combobox(frame, textvariable=gender_var,
                     values=['M', 'F', 'Mixed'],
                     state='readonly', width=27).grid(row=4, column=1, pady=5)

        ttk.Label(frame, text="Relay:").grid(row=5, column=0, sticky='w', pady=5)
        relay_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, variable=relay_var).grid(row=5, column=1, sticky='w', pady=5)

        def save_event():
            try:
                cursor = self.db_conn.cursor()
                cursor.execute("""
                    INSERT INTO events (number, name, distance, stroke, gender, is_relay)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (number_var.get(), name_var.get(), distance_var.get(),
                      stroke_var.get(), gender_var.get(), int(relay_var.get())))
                self.db_conn.commit()
                save_undo_point(self.db_conn, 'insert', 'events', cursor.lastrowid,
                               description=f"Added event #{number_var.get()}")
                messagebox.showinfo("Success", "Event added")
                dialog.destroy()
                self.refresh_events_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add event: {e}")

        ttk.Button(frame, text="Add Event", command=save_event).grid(
            row=6, column=0, columnspan=2, pady=20
        )

    def add_entry_dialog(self):
        """Show dialog to add an entry."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Entry")
        dialog.geometry("400x250")
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill='both', expand=True)

        cursor = self.db_conn.cursor()

        cursor.execute("SELECT id, name, team_id FROM swimmers ORDER BY name")
        swimmers = cursor.fetchall()
        swimmer_dict = {f"{s[1]} (ID:{s[0]})": s[0] for s in swimmers}

        cursor.execute("SELECT id, number, name FROM events ORDER BY number")
        events = cursor.fetchall()
        event_dict = {f"#{e[1]}: {e[2]}": e[0] for e in events}

        ttk.Label(frame, text="Swimmer:").grid(row=0, column=0, sticky='w', pady=5)
        swimmer_var = tk.StringVar()
        ttk.Combobox(frame, textvariable=swimmer_var,
                     values=list(swimmer_dict.keys()),
                     state='readonly', width=35).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Event:").grid(row=1, column=0, sticky='w', pady=5)
        event_var = tk.StringVar()
        ttk.Combobox(frame, textvariable=event_var,
                     values=list(event_dict.keys()),
                     state='readonly', width=35).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Seed Time (MM:SS.HH or NT):").grid(row=2, column=0, sticky='w', pady=5)
        time_var = tk.StringVar(value="NT")
        ttk.Entry(frame, textvariable=time_var, width=37).grid(row=2, column=1, pady=5)

        def save_entry():
            try:
                swimmer_id = swimmer_dict[swimmer_var.get()]
                event_id = event_dict[event_var.get()]
                seed_time = time_to_seconds(time_var.get())
                insert_or_update_entry(self.db_conn, swimmer_id, event_id, seed_time)
                save_undo_point(self.db_conn, 'insert', 'entries',
                               description=f"Added entry for {swimmer_var.get()}")
                messagebox.showinfo("Success", "Entry added")
                dialog.destroy()
                self.refresh_entries_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add entry: {e}")

        ttk.Button(frame, text="Add Entry", command=save_entry).grid(
            row=3, column=0, columnspan=2, pady=20
        )

    # ─── Import / Export ───────────────────────────────────────────────

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

            swimmer_map = {}

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
            self._refresh_all()

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

    def generate_heat_sheet(self):
        """Generate heat sheet PDF - prompts for event selection."""
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id, number, name FROM events ORDER BY number")
        events = cursor.fetchall()

        if not events:
            messagebox.showwarning("No Events", "No events found to generate heat sheets for.")
            return

        event_dict = {f"#{e[1]}: {e[2]}": e[0] for e in events}
        choice = simpledialog.askstring(
            "Select Event",
            f"Enter event (e.g. '#{events[0][1]}: {events[0][2]}'):\n\nAvailable:\n" +
            "\n".join(event_dict.keys())
        )
        if choice and choice in event_dict:
            path = filedialog.asksaveasfilename(
                title="Save Heat Sheet", defaultextension=".pdf",
                filetypes=[("PDF Files", "*.pdf")]
            )
            if path:
                try:
                    success = generate_heat_sheet_pdf(self.db_conn, event_dict[choice], path)
                    if success:
                        messagebox.showinfo("Success", f"Heat sheet saved to {path}")
                    else:
                        messagebox.showerror("Error", "Failed to generate heat sheet")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed: {e}")

    def generate_heat_sheet_for_selected(self):
        """Generate heat sheet for the selected event in the events tree."""
        if not hasattr(self, 'events_tree'):
            return
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an event first")
            return

        event_id = int(selection[0])
        path = filedialog.asksaveasfilename(
            title="Save Heat Sheet", defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")]
        )
        if path:
            try:
                success = generate_heat_sheet_pdf(self.db_conn, event_id, path)
                if success:
                    messagebox.showinfo("Success", f"Heat sheet saved to {path}")
                else:
                    messagebox.showerror("Error", "Failed to generate heat sheet")
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {e}")

    # ─── Seeding ───────────────────────────────────────────────────────

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
            self.refresh_events_list()
        except Exception as e:
            messagebox.showerror("Error", f"Seeding failed: {e}")

    # ─── Scoring ───────────────────────────────────────────────────────

    def calculate_all_scores(self):
        """Recalculate places and points for all events."""
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id FROM events ORDER BY number")
        events = cursor.fetchall()

        scoring_type = get_meet_setting(self.db_conn, 'scoring_type', 'dual')

        for (event_id,) in events:
            calculate_places(self.db_conn, event_id)
            assign_points(self.db_conn, event_id, scoring_type)

        self.refresh_scores()
        self.refresh_results_list()
        messagebox.showinfo("Scoring Complete", f"Recalculated scores for {len(events)} events")

    # ─── Validation Dialog ─────────────────────────────────────────────

    def show_validation_dialog(self):
        """Show meet validation results."""
        violations = validate_meet(self.db_conn)

        dialog = tk.Toplevel(self.root)
        dialog.title("Meet Validation")
        dialog.geometry("600x400")
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill='both', expand=True)

        if violations:
            ttk.Label(frame, text=f"Found {len(violations)} violation(s):",
                      font=('Arial', 11, 'bold'), foreground='red').pack(anchor='w', pady=5)

            text = tk.Text(frame, wrap='word', height=20)
            text.pack(fill='both', expand=True, pady=5)
            for v in violations:
                text.insert('end', f"  - {v}\n")
            text.config(state='disabled')
        else:
            ttk.Label(frame, text="All validations passed!",
                      font=('Arial', 14, 'bold'), foreground='green').pack(expand=True)

        ttk.Button(frame, text="Close", command=dialog.destroy).pack(pady=10)

    # ─── Meet Statistics Dialog ────────────────────────────────────────

    def show_meet_stats(self):
        """Show meet statistics dialog."""
        stats = get_meet_stats(self.db_conn)

        dialog = tk.Toplevel(self.root)
        dialog.title("Meet Statistics")
        dialog.geometry("400x350")
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Meet Statistics",
                  font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        stats_lines = [
            f"Teams: {stats['total_teams']}",
            f"Swimmers: {stats['total_swimmers']}  (Checked in: {stats['checked_in']})",
            f"Events: {stats['total_events']}  ({stats['individual_events']} individual, {stats['relay_events']} relay)",
            f"Entries: {stats['total_entries']}",
            f"Events Seeded: {stats['events_seeded']} / {stats['total_events']}",
            f"Events with Results: {stats['events_with_results']} / {stats['total_events']}",
            f"Total Results: {stats['total_results']}",
            f"DQs: {stats['total_dqs']}",
            f"No-Shows: {stats['total_ns']}",
        ]

        for line in stats_lines:
            ttk.Label(frame, text=line, font=('Arial', 11)).pack(anchor='w', pady=2)

        ttk.Button(frame, text="Close", command=dialog.destroy).pack(pady=15)

    # ─── Backup / Restore ─────────────────────────────────────────────

    def backup_meet(self):
        """Create a backup of the current meet."""
        if not self.current_meet_path:
            return
        backup_path = create_backup(self.current_meet_path)
        if backup_path:
            messagebox.showinfo("Backup Created", f"Backup saved to:\n{backup_path}")
        else:
            messagebox.showerror("Error", "Backup failed")

    def restore_backup_dialog(self):
        """Show dialog to restore from backup."""
        if not self.current_meet_path:
            return

        backups = list_backups(self.current_meet_path)
        if not backups:
            messagebox.showinfo("No Backups", "No backups found for this database.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Restore Backup")
        dialog.geometry("600x400")
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Select a backup to restore:",
                  font=('Arial', 11, 'bold')).pack(anchor='w', pady=5)

        columns = ('Name', 'Date', 'Size')
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=12)
        tree.heading('Name', text='Backup Name')
        tree.heading('Date', text='Date')
        tree.heading('Size', text='Size')
        tree.column('Name', width=300)
        tree.column('Date', width=150)
        tree.column('Size', width=80)
        tree.pack(fill='both', expand=True, pady=5)

        backup_map = {}
        for b in backups:
            iid = tree.insert('', 'end', values=(b['name'], b['modified'], f"{b['size']//1024}KB"))
            backup_map[iid] = b['path']

        def do_restore():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("No Selection", "Select a backup to restore")
                return
            if messagebox.askyesno("Confirm Restore",
                                   "This will replace the current database. Continue?"):
                backup_p = backup_map[sel[0]]
                if self.db_conn:
                    self.db_conn.close()
                success = restore_backup(backup_p, self.current_meet_path)
                if success:
                    self.db_conn = open_meet_db(self.current_meet_path)
                    dialog.destroy()
                    self.show_main_dashboard()
                    messagebox.showinfo("Restored", "Backup restored successfully")
                else:
                    messagebox.showerror("Error", "Restore failed")

        ttk.Button(frame, text="Restore Selected", command=do_restore).pack(pady=10)

    # ─── Undo ──────────────────────────────────────────────────────────

    def undo_action(self):
        """Undo the last action."""
        result = undo_last_action(self.db_conn)
        if result:
            messagebox.showinfo("Undo", result)
            self._refresh_all()
        else:
            messagebox.showinfo("Undo", "Nothing to undo")

    def show_undo_history(self):
        """Show undo history dialog."""
        history = get_undo_history(self.db_conn, limit=20)

        dialog = tk.Toplevel(self.root)
        dialog.title("Undo History")
        dialog.geometry("600x400")
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill='both', expand=True)

        columns = ('Time', 'Action', 'Table', 'Description')
        tree = ttk.Treeview(frame, columns=columns, show='headings')
        tree.heading('Time', text='Time')
        tree.heading('Action', text='Action')
        tree.heading('Table', text='Table')
        tree.heading('Description', text='Description')
        tree.column('Time', width=140)
        tree.column('Action', width=80)
        tree.column('Table', width=100)
        tree.column('Description', width=250)
        tree.pack(fill='both', expand=True, pady=5)

        for entry in history:
            tree.insert('', 'end', values=(
                entry['timestamp'], entry['action'], entry['table_name'],
                entry['description'] or ''
            ))

        ttk.Button(frame, text="Close", command=dialog.destroy).pack(pady=10)

    # ─── Check-in ──────────────────────────────────────────────────────

    def check_in_selected(self):
        """Toggle check-in for the selected swimmer."""
        if not hasattr(self, 'swimmers_tree'):
            return
        selection = self.swimmers_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a swimmer")
            return

        swimmer_id = int(selection[0])
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT checked_in FROM swimmers WHERE id = ?", (swimmer_id,))
        row = cursor.fetchone()
        if row and row[0]:
            check_out_swimmer(self.db_conn, swimmer_id)
        else:
            check_in_swimmer(self.db_conn, swimmer_id)
        self.refresh_swimmers_list()

    # ─── Delete Functions ──────────────────────────────────────────────

    def delete_selected_event(self):
        """Delete selected event."""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an event to delete")
            return

        if messagebox.askyesno("Confirm", "Delete selected event and all entries?"):
            try:
                event_id = int(selection[0])
                cursor = self.db_conn.cursor()
                cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
                self.db_conn.commit()
                self.refresh_events_list()
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
                swimmer_id = int(selection[0])
                cursor = self.db_conn.cursor()
                cursor.execute("DELETE FROM swimmers WHERE id = ?", (swimmer_id,))
                self.db_conn.commit()
                self.refresh_swimmers_list()
                self.refresh_entries_list()
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
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete entry: {e}")
