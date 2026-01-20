from PyQt6.QtWidgets import QMainWindow, QLabel, QPushButton, QVBoxLayout, QWidget, QFileDialog, QMessageBox, QTabWidget, QTableView
from PyQt6.QtSql import QSqlDatabase, QSqlQueryModel
from PyQt6.QtCore import Qt
from src.database import init_db, open_meet_db  # Your SQLite helpers (unchanged)

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenSwimMeet - Open Source Swim Meet Manager")
        self.resize(1200, 800)
        # self.setWindowIcon(QIcon("resources/icons/app.ico"))  # Uncomment if you add an icon

        self.db_conn = None
        self.current_meet_path = None

        self.setup_ui()
        self.show_welcome_screen()

    def setup_ui(self):
        # Central widget with layout
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

        export_btn = QPushButton("Export Entries Only (Away Team)")
        export_btn.setFixedSize(200, 60)
        export_btn.setStyleSheet("background-color: #28A745; color: white; font: bold 14pt Arial; border-radius: 5px;")
        export_btn.clicked.connect(self.export_entries)  # TODO: Implement export flow
        btn_layout.addWidget(export_btn)

        self.layout.addLayout(btn_layout)

    def new_meet(self):
        path, _ = QFileDialog.getSaveFileName(self, "Create New Meet", "", "Meet Database (*.db)")
        if path:
            self.current_meet_path = path
            self.db_conn = init_db(path)
            if self.db_conn:
                self.show_main_dashboard()
            else:
                QMessageBox.warning(self, "Error", "Failed to create database.")

    def open_meet(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Meet", "", "Meet Database (*.db)")
        if path:
            self.current_meet_path = path
            self.db_conn = open_meet_db(path)
            if self.db_conn:
                self.show_main_dashboard()
            else:
                QMessageBox.warning(self, "Error", "Failed to open database.")

    def export_entries(self):
        # Placeholder for away team export flow
        QMessageBox.information(self, "Export", "Export entries functionality coming soon!")

    def show_main_dashboard(self):
        self.clear_layout()

        # Tabbed interface for dashboard
        tabs = QTabWidget()
        self.layout.addWidget(tabs)

        # Entries Tab (example with QTableView bound to SQL model)
        entries_tab = QWidget()
        entries_layout = QVBoxLayout(entries_tab)
        entries_label = QLabel("Entries Dashboard")
        entries_label.setStyleSheet("font: bold 18pt Arial;")
        entries_layout.addWidget(entries_label)

        # Example: Display swimmers table
        swimmers_model = QSqlQueryModel()
        swimmers_model.setQuery("SELECT * FROM swimmers", self.db_conn)
        swimmers_table = QTableView()
        swimmers_table.setModel(swimmers_model)
        swimmers_table.setAlternatingRowColors(True)
        swimmers_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        entries_layout.addWidget(swimmers_table)

        tabs.addTab(entries_tab, "Entries")

        # Add more tabs: Seeding, Psych Sheets, etc.
        seeding_tab = QWidget()
        seeding_layout = QVBoxLayout(seeding_tab)
        seeding_label = QLabel("Seeding & Heats (Coming Soon)")
        seeding_layout.addWidget(seeding_label)
        tabs.addTab(seeding_tab, "Seeding")

        psych_tab = QWidget()
        psych_layout = QVBoxLayout(psych_tab)
        psych_label = QLabel("Psych Sheets (Coming Soon)")
        psych_layout.addWidget(psych_label)
        tabs.addTab(psych_tab, "Psych Sheets")

        # Add buttons for actions like Import Team
        import_btn = QPushButton("Import Team Entries (.HY3)")
        import_btn.setFixedSize(200, 40)
        import_btn.setStyleSheet("background-color: #FFC107; color: black; font: bold 12pt Arial; border-radius: 5px;")
        import_btn.clicked.connect(self.import_team_entries)  # TODO: Implement
        self.layout.addWidget(import_btn)

    def import_team_entries(self):
        # Placeholder for import/merge flow
        path, _ = QFileDialog.getOpenFileName(self, "Import .HY3 File", "", "Hy-Tek Entries (*.hy3 *.HY3)")
        if path:
            # Call your hy3_parser here
            QMessageBox.information(self, "Import", f"Imported from {path}. Merge functionality coming soon!")
