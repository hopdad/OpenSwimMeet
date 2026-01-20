OpenSwimMeet
OpenSwimMeet Logo 
OpenSwimMeet is an open-source, offline-first swimming meet management software designed to be intuitive and user-friendly, like using an iPhone. It aims to rival proprietary tools like Hy-Tek Meet Manager by providing seamless features for high school and club teams, including entry submissions, merging, seeding, heat generation, psych sheets, and future timing system integrations—all without needing internet or external infrastructure.
Built with coaches, officials, and volunteers in mind, it eliminates steep learning curves with drag-and-drop interfaces, wizards, and visual previews. Teams can exchange entries via simple files (e.g., .HY3 for Hy-Tek compatibility) over email or USB.
Key Features

Offline-First & Self-Contained: Runs on your laptop (Windows/Mac/Linux) with no servers, accounts, or internet required. Each meet is a single .db file.
Intuitive UI: Modern, clean interface with wizards for setup, drag-drop for imports, and real-time previews. No dense menus or manuals needed.
Entry Management: Add swimmers, events, and seed times easily. Export/import entries as .HY3 (Hy-Tek compatible) or JSON/CSV.
Team Merging: Home teams import away team files, auto-detect conflicts, and merge with one click.
Seeding & Heats: Automatic sorting by seed times, circle seeding, lane assignments per USA Swimming/FINA rules.
Psych Sheets & Reports: Generate printable PDF psych sheets (ranked by event, with seed times and projected heats).
Future Plans: Timing console integrations (file/serial for CTS, Daktronics, etc.), live meet running, USA Swimming API support (post-approval).
Cross-Platform: Desktop app via Python, with potential for web/PWA versions.

Installation

Prerequisites: Python 3.10+ installed on your system.
Clone the repo:textgit clone https://github.com/yourusername/OpenSwimMeet.git
cd OpenSwimMeet
Install dependencies:textpip install -r requirements.txt(Includes customtkinter for UI, reportlab for PDFs.)
Run the app:textpython src/main.py

For a standalone executable (no Python needed):

Install PyInstaller: pip install pyinstaller
Build: pyinstaller --onefile --windowed --icon=resources/icons/app.ico src/main.py
Find the .exe in /dist/.

Usage
Quick Start

Launch the app → "New Meet" → Save a .db file (e.g., MyMeet.db).
Set up basics: Add events (e.g., 50 Free, 100 Back) via wizard.
Add your team's swimmers and entries.
For away teams: Export entries as .HY3 file → email/USB to host.
Host: Import .HY3 → preview & merge → "Seed Meet" → Generate Psych Sheets PDF.

Example Workflow

Away Team: Open app → "Import Entries Only" mode → Add swimmers/events → Export .HY3 → Send to host.
Home Team: Open meet .db → "Add Team Entries" → Drag-drop .HY3 → Merge → View combined entries → Seed → Print psych sheets.

Sample data is in resources/sample_data/ for testing.
Screenshots


Welcome Screen: Welcome
Meet Dashboard: Dashboard
Import Merge: Import

Contributing
We welcome contributions! Fork the repo, create a branch, and submit a PR.

Issues: Report bugs or suggest features via GitHub Issues.
Code Style: Follow PEP8 for Python.
Testing: Add unit tests in /tests/ using pytest.
Focus areas: .HY3 parser improvements, UI polish, timing integrations.

See docs/CONTRIBUTING.md for details (coming soon).
License
MIT License – see LICENSE for details.
Acknowledgments

Inspired by existing open-source tools like SwimClubMeet.
