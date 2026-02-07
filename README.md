# OpenSwimMeet

**OpenSwimMeet** is an open-source, offline-first swimming meet management software designed to be intuitive and user-friendly. It aims to rival proprietary tools like Hy-Tek Meet Manager by providing seamless features for high school and club teams, including entry submissions, merging, seeding, heat generation, psych sheets, and future timing system integrations—all without needing internet or external infrastructure.

Built with coaches, officials, and volunteers in mind, it eliminates steep learning curves with a clean interface, wizards, and visual previews. Teams can exchange entries via simple files (e.g., .HY3 for Hy-Tek compatibility) over email or USB.

## Key Features

- **Offline-First & Self-Contained**: Runs on your laptop (Windows/Mac/Linux) with no servers, accounts, or internet required. Each meet is a single .db file.
- **Intuitive UI**: Modern, clean tkinter-based interface with wizards for setup and easy-to-use dialogs. No dense menus or manuals needed.
- **Entry Management**: Add swimmers, events, and seed times easily. Export/import entries as .HY3 (Hy-Tek compatible) or CSV.
- **Team Merging**: Home teams import away team files with proper SDIF parsing and automatic swimmer/team matching.
- **Seeding & Heats**: Automatic circle seeding algorithm, lane assignments per USA Swimming rules (middle lanes for fastest swimmers).
- **Psych Sheets & Reports**: Generate printable PDF psych sheets ranked by event with seed times.
- **Future Plans**: Timing console integrations (file/serial for CTS, Daktronics, etc.), live meet running, results tracking, USA Swimming API support.
- **Cross-Platform**: Desktop app via Python + tkinter (built-in to Python), with potential for web versions.

## Installation

### Prerequisites
- Python 3.10+ installed on your system (includes tkinter by default)

### Quick Setup

1. **Clone the repo:**
   ```bash
   git clone https://github.com/hopdad/OpenSwimMeet.git
   cd OpenSwimMeet
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   (Includes reportlab for PDFs, Pillow for images, pandas/openpyxl for data handling)

3. **Run the app:**
   ```bash
   python src/main.py
   ```

### For a Standalone Executable (No Python Needed)

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Build executable:
   ```bash
   pyinstaller --onefile --windowed --name OpenSwimMeet src/main.py
   ```

3. Find the executable in `/dist/` folder

## Usage

### Quick Start

1. Launch the app → Click **"New Meet"** → Save a .db file (e.g., `MyMeet.db`)
2. Fill in meet setup wizard (name, date, course, lanes)
3. Add events using **"Add Event"** button (Event #, Name, Distance, Stroke, Gender)
4. Add swimmers using **"Add Swimmer"** button (Name, Team, Age, Gender)
5. Add entries using **"Add Entry"** button (Swimmer, Event, Seed Time)
6. Or import entries from HY3 file: **File → Import → Import HY3 File**
7. Seed all events: **"Seed All Events"** button on Dashboard
8. Generate psych sheets: **Export → Generate Psych Sheet**

### Example Workflow

**Away Team:**
1. Create new meet → Add swimmers and entries for your team
2. Export entries as .HY3: **Export → Export to HY3**
3. Email/USB the .HY3 file to host team

**Home Team:**
1. Open your meet database
2. Import away team entries: **Import → Import HY3 File**
3. Review all entries in **Entries** tab
4. Seed all events: **Dashboard → Seed All Events**
5. Generate and print psych sheets: **Export → Generate Psych Sheet**

### Sample Data

Sample SDIF-format HY3 file available in `resources/sample_data/SAMPLE.hy3` for testing the import functionality.

## Project Structure

```
OpenSwimMeet/
├── src/
│   ├── main.py              # Entry point
│   ├── app.py               # Main tkinter application
│   ├── database.py          # SQLite database functions
│   ├── hy3_parser.py        # SDIF/HY3 file parser
│   ├── hy3_exporter.py      # SDIF/HY3 file exporter
│   ├── seeding.py           # Circle seeding algorithm
│   ├── psych_sheets.py      # PDF generation
│   └── utils.py             # Helper functions
├── tests/
│   └── test_hy3_parser.py   # Unit tests
├── resources/
│   ├── icons/               # App icons (TODO)
│   └── sample_data/         # Sample HY3 files
├── requirements.txt         # Python dependencies
├── pyproject.toml          # Project configuration
└── README.md               # This file
```

## Database Schema

The application uses SQLite with the following main tables:

- **teams**: Team information (code, name, colors)
- **swimmers**: Swimmer details (name, team, age, gender, USAS ID)
- **events**: Event definitions (number, name, distance, stroke, gender)
- **entries**: Swimmer entries in events (with seed times)
- **heats**: Heat definitions for each event
- **heat_assignments**: Lane assignments within heats
- **results**: Race results (times, places, points)
- **meet_settings**: Meet configuration (name, date, course, etc.)

## SDIF/HY3 Format

The application supports the SDIF (Swim Data Interchange Format) used by Hy-Tek:

- **A1 records**: Meet header
- **C1 records**: Team information
- **D0 records**: Individual entries (name, USAS ID, event, seed time)
- **E0 records**: Relay entries (future)
- **Z0 record**: End of file marker

## Testing

Run tests with pytest:

```bash
pip install pytest pytest-cov
pytest tests/ -v
```

Run tests with coverage:

```bash
pytest tests/ --cov=src --cov-report=html
```

## Contributing

We welcome contributions! Here's how you can help:

1. **Fork the repo** and create a feature branch
2. **Make your changes** following PEP8 style guidelines
3. **Add tests** for new functionality
4. **Submit a pull request** with a clear description

Focus areas:
- HY3 parser improvements for edge cases
- UI/UX enhancements
- Timing system integrations
- Results entry and scoring
- Meet reports and exports

## Roadmap

### Version 0.1 (Current)
- [x] Basic meet creation and management
- [x] Swimmer and event management
- [x] HY3 import/export
- [x] Circle seeding algorithm
- [x] Psych sheet PDF generation

### Version 0.2 (Next)
- [ ] Results entry interface
- [ ] Team scoring with configurable rules
- [ ] Heat sheet PDF generation
- [ ] Awards/ribbons generation
- [ ] Backup/restore functionality

### Version 0.3 (Future)
- [ ] Timing system integration (file-based)
- [ ] Live heat management during meet
- [ ] Final results PDF with places/times
- [ ] Team score tracking in real-time
- [ ] Relay team management

### Version 1.0 (Long-term)
- [ ] Direct timing console integration (serial/USB)
- [ ] USA Swimming TIMES database integration
- [ ] Online meet registration portal
- [ ] Multi-meet season tracking

## Known Issues

- HY3 parser may not handle all SDIF variations perfectly
- Relay entries not yet fully supported
- No meet results entry interface yet (planned for v0.2)

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by existing open-source meet management tools
- SDIF format documentation from USA Swimming
- ReportLab for PDF generation
- The swimming community for feedback and testing

## Support

For questions, bug reports, or feature requests:
- **Issues**: [GitHub Issues](https://github.com/hopdad/OpenSwimMeet/issues)
- **Discussions**: [GitHub Discussions](https://github.com/hopdad/OpenSwimMeet/discussions)

---

**Made with ❤️ for the swimming community**
