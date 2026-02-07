import sys
import json
import shutil
import os
import threading
import time
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QLabel, QPushButton, QVBoxLayout, QWidget, QFileDialog, QMessageBox,
    QTabWidget, QTableView, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QHBoxLayout, QLineEdit, QComboBox, QSpinBox, QCheckBox, QProgressDialog,
    QTextEdit
)
from PyQt6.QtSql import QSqlDatabase, QSqlQueryModel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
import psutil

from src.database import init_db, open_meet_db, get_meet_setting, set_meet_setting, is_meet_completed, mark_meet_complete
from src.ui.add_swimmer_dialog import AddSwimmerDialog
from src.ui.add_entry_dialog import AddEntryDialog
from src.ui.add_event_dialog import AddEventDialog
from src.ui.relay_entry_dialog import RelayEntryDialog
from src.ui.relay_edit_dialog import RelayEditDialog
from src.ui.backup_time_dialog import BackupTimeDialog
from src.ui.run_meet_screen import RunMeetScreen
from src.ui.scoring_config_dialog import ScoringConfigDialog
from src.ui.time_converter_dialog import TimeConverterDialog
from src.ui.scratch_swimmer_dialog import ScratchSwimmerDialog
from src.seeding import apply_seeding
from src.scoring import award_points, update_team_scores
from src.meet_exporter import export_meet_bundle
from src.swimmer_cards import generate_swimmer_cards_by_team
from src.psych_heat_sheets import generate_psych_heat_pdf
from src.manual_timekeeper_sheets import generate_timekeeper_sheets
from src.diving_judge_sheets import generate_diving_judge_sheets
from src.relay_heat_sheets import generate_relay_heat_sheets
from src.final_results_pdf import generate_final_results_pdf
from src.csv_exporter import export_results_csv, export_team_scores_csv, export_entries_csv, export_relay_groups_csv, export_relay_members_csv, export_relay_results_csv

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenSwimMeet - Open Source Swim Meet Manager")
        self.resize(1200, 800)

        self.current_meet_path = None
        self.db_conn = None

        self.backup_timer = None
        self.backup_interval_seconds = 180  # 3 minutes
        self.max_backups_to_keep = 10
        self.usb_backup_prompted = False

        self.setup_ui()
        self.show_welcome_screen()

        # Start auto-backup timer
        self.start_auto_backup()

    def setup_ui(self):
        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.layout = QVBoxLayout(self.central)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setSpacing(20)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def clear_layout(self):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def show_welcome_screen(self):
        self.clear_layout()

        welcome_label = QLabel("Welcome to OpenSwimMeet")
        welcome_label.setStyleSheet("font: bold 28pt Arial; color: #333;")
        self.layout.addWidget(welcome_label)

        sub_label = QLabel("Offline swimming meet management – intuitive & Hy-Tek compatible")
        sub_label.setStyleSheet("font: 14pt Arial; color: #666;")
        self.layout.addWidget(sub_label)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        new_btn = QPushButton("New Meet")
        new_btn.setFixedSize(200, 60)
        new_btn.setStyleSheet("background-color: #007BFF; color: white; font: bold 14pt Arial; border-radius: 5px;")
        new_btn.clicked.connect(self.new_meet)
        btn_layout.addWidget(new_btn)

        open_btn = QPushButton("Open Existing Meet")
        open_btn.setFixedSize(200, 60)
        open_btn.setStyleSheet("background-color: #007BFF; color: white; font: bold 14pt Arial; border-radius: 5px;")
        open_btn.clicked.connect(self.open_meet)
        btn_layout.addWidget(open_btn)

        self.layout.addLayout(btn_layout)

    def new_meet(self):
        path, _ = QFileDialog.getSaveFileName(self, "Create New Meet", "", "Meet Database (*.db)")
        if path:
            self.current_meet_path = path
            self.db_conn = init_db(path)
            self.show_meet_settings_wizard()
            self.show_main_dashboard()
            self.start_auto_backup()
            self.load_meet_state()

    def open_meet(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Meet", "", "Meet Database (*.db)")
        if path:
            self.current_meet_path = path
            self.db_conn = open_meet_db(path)

            # Check for recent backup and offer restore
            backup_dir = Path(path).parent / "MeetBackups"
            if backup_dir.exists():
                recent_backups = sorted(backup_dir.glob("backup_*"), key=lambda p: p.name, reverse=True)
                if recent_backups:
                    latest = recent_backups[0]
                    reply = QMessageBox.question(
                        self, "Backup Found",
                        f"Found recent backup: {latest.name}\n\nRestore from this backup?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        shutil.copy2(latest / Path(path).name, path)
                        state_backup = latest / Path(path).with_suffix('.state.json').name
                        if Path(state_backup).exists():
                            shutil.copy2(state_backup, Path(path).with_suffix('.state.json'))
                        QMessageBox.information(self, "Restored", "Meet restored from backup.")

            self.show_main_dashboard()
            self.start_auto_backup()
            self.load_meet_state()

    def show_meet_settings_wizard(self):
        # ... (full wizard code from previous messages, including meet_type, course, dual mode, home lanes, etc.)
        # Make sure to save all settings including 'meet_type', 'course', 'dual_meet_mode', 'dual_meet_home_lanes', etc.
        # After save:
        self.auto_insert_events(type_combo.currentText())

    def auto_insert_events(self, meet_type: str):
        # ... (full code from earlier, using EVENT_TEMPLATES)
        pass

    def show_main_dashboard(self):
        self.clear_layout()
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # Dashboard tab (buttons)
        dash_tab = QWidget()
        dash_layout = QVBoxLayout(dash_tab)

        # Example buttons (add all from previous messages)
        # Add Swimmer, Add Event, Add Entry, Enter Relay, Edit Relay, etc.
        # Complete meet, backup USB, restore USB, cloud config, audience host, etc.

        self.tabs.addTab(dash_tab, "Dashboard")

        # Run Meet tab
        run_tab = QWidget()
        run_layout = QVBoxLayout(run_tab)
        self.run_screen = RunMeetScreen(self, self.db_conn)
        run_layout.addWidget(self.run_screen)
        self.tabs.addTab(run_tab, "Run Meet")

        # Team Scores tab
        scores_tab = QWidget()
        scores_layout = QVBoxLayout(scores_tab)
        self.scores_table = QTableWidget(0, 5)
        self.scores_table.setHorizontalHeaderLabels(["Rank", "Team", "Boys", "Girls", "Total"])
        scores_layout.addWidget(self.scores_table)
        refresh_scores_btn = QPushButton("Refresh Standings")
        refresh_scores_btn.clicked.connect(self.refresh_team_standings)
        scores_layout.addWidget(refresh_scores_btn)
        self.tabs.addTab(scores_tab, "Team Standings")

        # Non-Scoring Swimmers tab
        non_scoring_tab = QWidget()
        non_scoring_layout = QVBoxLayout(non_scoring_tab)
        self.non_scoring_table = QTableWidget(0, 6)
        self.non_scoring_table.setHorizontalHeaderLabels(["Name", "Age", "Gender", "Team", "Events Entered", "Actions"])
        non_scoring_layout.addWidget(self.non_scoring_table)
        refresh_non_btn = QPushButton("Refresh Non-Scoring List")
        refresh_non_btn.clicked.connect(self.refresh_non_scoring_list)
        non_scoring_layout.addWidget(refresh_non_btn)
        self.tabs.addTab(non_scoring_tab, "Non-Scoring Swimmers")

        # ... add other tabs as needed

        if is_meet_completed(self.db_conn):
            lock_label = QLabel("Meet is COMPLETE and LOCKED for editing.\nViewing and exporting still available.")
            lock_label.setStyleSheet("font: bold 16pt Arial; color: #DC3545; background: #fff3cd; padding: 15px; border-radius: 8px;")
            lock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(lock_label)

            # Disable editing buttons (example)
            # for btn in [add_swimmer_btn, ...]: btn.setEnabled(False)

    def refresh_team_standings(self):
        # ... (full code from earlier)
        pass

    def refresh_non_scoring_list(self):
        # ... (full code from earlier)
        pass

    def toggle_non_scoring(self, swimmer_id: int):
        # ... (full code from earlier)
        pass

    def save_meet_state(self):
        # ... (full code from earlier)
        pass

    def load_meet_state(self):
        # ... (full code from earlier)
        pass

    def start_auto_backup(self):
        # ... (full code from earlier)
        pass

    def perform_auto_backup(self):
        # ... (full code from earlier, including local + cloud + USB if enabled)
        pass

    def backup_to_external(self):
        # ... (full code from earlier)
        pass

    def restore_from_usb_backup(self):
        # ... (full code from earlier)
        pass

    def complete_meet_and_export(self):
        # ... (full code from earlier, with cloud/USB auto-backup)
        pass

    # Add other methods as needed (import_team_entries, generate_swimmer_cards, etc.)
