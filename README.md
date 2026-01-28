# PCBA Database Application

A PyQt6-based desktop application for managing PCBA (Printed Circuit Board Assembly) and PMT (PhotoMultiplier Tube) test data. The application provides comprehensive tools for browsing test logs, analyzing measurement data, generating reports, and exporting results.

## Features

### 📊 Graphs Page
- **Multi-mode plotting**: Standard, Comparison, Relational, and Plot Overlay modes
- **Interactive PyQtGraph charts**: Scatter, Line, Histogram visualizations
- **Grouping & filtering**: Group data by device, batch, fixture, or date
- **Spec line overlays**: Display upper/lower limits on plots
- **Crosshairs & tooltips**: Interactive data exploration

### 🗄️ Database Page
- **Multi-view browsing**: Test Logs, PIA Boards, PMT Devices, Manufacturers
- **Advanced filtering**: Search, date range, test fixture, pass/fail status
- **Inline editing**: Edit device serial numbers, part numbers, test metadata
- **Detail panel**: View and modify selected records
- **HTML report navigation**: Jump to full test reports
- **Manufacturer management**: Add and manage manufacturer data

### 📈 Reports Page
- **Spec data viewer**: View measurements across devices and tests
- **Trend analysis**: Compare up to 10 test runs per device
- **Customizable Excel export**:
  - Custom colors for headers, data rows, borders
  - Zebra striping
  - Pass/Fail conditional formatting
  - Transpose data option
  - Embedded plot images
- **Flexible grouping**: By part number, serial number, batch, test name

### 🔍 Search / Report Viewer Page
- **Autocomplete search**: Search by serial numbers, part numbers with suggestions
- **HTML report viewer**: Embedded web view with zoom controls
- **Export options**: Save HTML to file, open in browser, print
- **Compare mode**: Side-by-side comparison of two test reports
- **Recent history**: Quick access to recently viewed reports

## Installation

### Prerequisites
- Python 3.10 or higher
- pip package manager

### Setup

1. Clone or extract the project:
```bash
cd "pcba database_v2"
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python -m src.main
```

## Project Structure

```
pcba database_v2/
├── config/
│   └── bench_config.toml      # Application configuration
├── data/
│   └── Combined_database.db   # SQLite database file
├── src/
│   ├── database/
│   │   ├── base.py                    # SQLAlchemy base & session factory
│   │   ├── manager.py                 # DatabaseManager class
│   │   ├── database_device_tables.py  # PCBABoard, PMT models
│   │   ├── database_test_log_tables.py # TestLog, SubTest, Spec models
│   │   ├── database_manufacturer_tables.py # Manufacturer models
│   │   ├── database_queries.py        # Query classes
│   │   └── database_worker.py         # Background query worker
│   ├── gui/
│   │   ├── mainWindow.py              # Main application window
│   │   ├── pages/
│   │   │   ├── graph_page.py          # Graphs page handler
│   │   │   ├── database_page.py       # Database page handler
│   │   │   ├── reports_page.py        # Reports page handler
│   │   │   └── search_page.py         # Search/viewer page handler
│   │   ├── graph_generation/          # Plot generation utilities
│   │   ├── styling/
│   │   │   ├── generated/             # Generated QSS stylesheets
│   │   │   ├── templates/             # QSS templates
│   │   │   └── themes/                # Theme definitions (TOML)
│   │   └── user_interfaces/           # Qt Designer .ui files
│   └── main.py                        # Application entry point
├── tests/
│   ├── test_pages.py                  # Page functionality tests
│   ├── database_testing/              # Database-specific tests
│   └── graph_generation_testing/      # Graph generation tests
├── requirements.txt
└── README.md
```

## Database Schema

### Device Tables
- **PCBABoard (pia_board)**: PIA board inventory
  - serial_number, part_number, generation_project, version
- **PMT (pmt_device)**: PMT device inventory
  - pmt_serial_number, generation, batch_number

### Test Log Tables
- **TestLog (test_log)**: Individual test runs
  - Links to pia_board and pmt_device
  - name, description, test_fixture, full_test_completed, full_test_passed
  - html_content for storing test reports
- **SubTest (sub_test)**: Test sections within a test log
- **Spec (spec)**: Individual measurements
  - name, measurement, unit, lower_limit, upper_limit, result
  - has_plot, plot_data for waveform data

### Manufacturer Tables
- **Manufacturer**: Vendor information
- **ManufacturerDeviceBatch**: Batch groupings
- **ManufacturerSpec**: Manufacturer-provided specifications

## Theming

The application supports multiple color themes with light/dark modes:
- Ocean (default)
- Emerald
- Forest
- Slate
- Sunset
- Violet

To change the theme, modify the `load_stylesheet()` call in `mainWindow.py`:
```python
self.load_stylesheet("emerald", "dark")  # or "light"
```

To generate new theme stylesheets:
```bash
cd src/gui/styling
python generate_qss.py --theme ocean --mode dark
```

## Usage

### Adding Test Data
Test data is typically added programmatically during test execution. The database page also allows:
- Adding new manufacturers via the "Add Entry" button
- Editing existing device serial/part numbers
- Deleting records (with confirmation)

### Viewing Test Reports
1. Navigate to the **Database** page
2. Find the test log using filters
3. Select a row and click "View HTML Report"
4. Or use the **Search** page with autocomplete

### Generating Excel Reports
1. Navigate to the **Reports** page
2. Select specs from the list (multi-select)
3. Apply filters (device, date range, etc.)
4. Click "Generate Report"
5. Configure export options (colors, layout)
6. Click "Export to Excel"

### Comparing Test Reports
1. Navigate to the **Search** page
2. Enable "Compare Mode"
3. Search for test logs
4. Click two results to load side-by-side

## Development

### Running Tests
```bash
pytest tests/ -v
```

### Code Style
- Python code follows PEP 8 guidelines
- PyQt6 naming conventions for UI elements
- SQLAlchemy ORM for database operations

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| PyQt6 | ≥6.4.0 | GUI framework |
| PyQt6-WebEngine | ≥6.4.0 | HTML report viewer |
| SQLAlchemy | ≥2.0.0 | Database ORM |
| pandas | ≥2.0.0 | Data processing |
| numpy | ≥1.24.0 | Numerical operations |
| pyqtgraph | ≥0.13.0 | Interactive plotting |
| matplotlib | ≥3.7.0 | Plot image generation |
| openpyxl | ≥3.1.0 | Excel export |

## License

Proprietary - Internal use only.

## Support

For issues or feature requests, contact the development team.
