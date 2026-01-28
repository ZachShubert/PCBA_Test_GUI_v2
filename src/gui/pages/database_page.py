"""
Database Page - Browse, search, and manage test logs and device records.

Features:
- View modes: Test Logs, PIA Boards, PMT Devices, Manufacturers
- Advanced filtering with search, date range, test fixture, result filters
- Sortable table with virtual scrolling
- Inline detail panel for viewing/editing selected records
- Sync functionality for collecting database files from test fixtures
- HTML report viewing integration with search page

Author: Generated for PCBA Database Application
"""
import logging
import os
import webbrowser
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from functools import partial

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QLabel, QLineEdit, QComboBox,
    QPushButton, QFrame, QScrollArea, QDateEdit, QMessageBox,
    QProgressDialog, QApplication, QFileDialog, QSplitter,
    QTextEdit, QGroupBox, QRadioButton, QButtonGroup, QSpacerItem,
    QSizePolicy, QMenu, QCheckBox, QGridLayout
)
from PyQt6.QtCore import (
    QThread, pyqtSignal, Qt, QDate, QTimer, QSortFilterProxyModel,
    QAbstractTableModel, QModelIndex, QVariant
)
from PyQt6.QtGui import QAction, QColor, QBrush, QFont, QIcon

from src.database import DatabaseManager
from src.database.database_device_tables import PCBABoard, PMT
from src.database.database_test_log_tables import TestLog, SubTest, Spec
from src.database.database_manufacturer_tables import (
    Manufacturer, ManufacturerDeviceBatch, ManufacturerSpec
)

logger = logging.getLogger(__name__)


class ViewMode:
    """View mode constants for the database browser."""
    TEST_LOGS = "Test Logs"
    PIA_BOARDS = "PIA Boards"
    PMT_DEVICES = "PMT Devices"
    MANUFACTURERS = "Manufacturers"


class DatabaseQueryWorker(QThread):
    """
    Worker thread for database queries to keep UI responsive.
    
    Signals:
        progress: Emits (current, total) for progress updates
        finished: Emits list of results when complete
        error: Emits error message string on failure
    """
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, db_manager: DatabaseManager, query_func: Callable, *args, **kwargs):
        super().__init__()
        self.db_manager = db_manager
        self.query_func = query_func
        self.args = args
        self.kwargs = kwargs
        self._cancel = False
    
    def cancel(self):
        """Request cancellation of the query."""
        self._cancel = True
    
    def run(self):
        """Execute the query in a separate thread."""
        try:
            results = self.query_func(*self.args, **self.kwargs)
            if not self._cancel:
                self.finished.emit(results if results else [])
        except Exception as e:
            logger.exception("Database query failed")
            self.error.emit(str(e))


class TestLogTableModel(QAbstractTableModel):
    """
    Custom table model for test logs with lazy loading support.
    
    Displays: Test Name, Test Date, Result, Full Test, PIA Part#, PIA Serial#, 
              PMT Batch#, PMT Serial#
    """
    
    COLUMNS = [
        ("Test Name", "name"),
        ("Test Date", "created_at"),
        ("Result", "full_test_passed"),
        ("Full Test", "full_test_completed"),
        ("Test Fixture", "test_fixture"),
        ("PIA Part #", "pia_part_number"),
        ("PIA Serial #", "pia_serial_number"),
        ("PMT Batch #", "pmt_batch_number"),
        ("PMT Serial #", "pmt_serial_number"),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[TestLog] = []
        self._raw_data: List[Dict] = []  # Cached data for display
    
    def set_data(self, test_logs: List[TestLog]):
        """Set the data and refresh the model."""
        self.beginResetModel()
        self._data = test_logs
        self._raw_data = []
        
        for tl in test_logs:
            row = {
                'id': tl.id,
                'name': tl.name or 'N/A',
                'created_at': tl.created_at.strftime('%Y-%m-%d %H:%M') if tl.created_at else 'N/A',
                'full_test_passed': tl.full_test_passed,
                'full_test_completed': tl.full_test_completed,
                'test_fixture': tl.test_fixture or 'N/A',
                'pia_part_number': tl.pia_board.part_number if tl.pia_board and tl.pia_board.part_number else 'N/A',
                'pia_serial_number': tl.pia_board.serial_number if tl.pia_board and tl.pia_board.serial_number else 'N/A',
                'pmt_batch_number': tl.pmt_device.batch_number if tl.pmt_device and tl.pmt_device.batch_number else 'N/A',
                'pmt_serial_number': tl.pmt_device.pmt_serial_number if tl.pmt_device and tl.pmt_device.pmt_serial_number else 'N/A',
                '_test_log': tl,  # Store reference for detail view
            }
            self._raw_data.append(row)
        
        self.endResetModel()
    
    def rowCount(self, parent=QModelIndex()):
        return len(self._raw_data)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)
    
    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._raw_data):
            return None
        
        row_data = self._raw_data[index.row()]
        col_name = self.COLUMNS[index.column()][1]
        
        if role == Qt.ItemDataRole.DisplayRole:
            value = row_data.get(col_name, 'N/A')
            
            # Format boolean values
            if col_name == 'full_test_passed':
                if value is None:
                    return 'N/A'
                return '✓ PASS' if value else '✗ FAIL'
            elif col_name == 'full_test_completed':
                if value is None:
                    return 'N/A'
                return '✓ Yes' if value else '○ No'
            
            return str(value) if value is not None else 'N/A'
        
        elif role == Qt.ItemDataRole.ForegroundRole:
            if col_name == 'full_test_passed':
                value = row_data.get(col_name)
                if value is True:
                    return QBrush(QColor('#22c55e'))  # Green
                elif value is False:
                    return QBrush(QColor('#ef4444'))  # Red
            return None
        
        elif role == Qt.ItemDataRole.FontRole:
            if col_name in ('full_test_passed', 'full_test_completed'):
                font = QFont()
                font.setBold(True)
                return font
            return None
        
        elif role == Qt.ItemDataRole.UserRole:
            # Return the full row data for detail view
            return row_data
        
        return None
    
    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section][0]
        return None
    
    def get_test_log(self, row: int) -> Optional[TestLog]:
        """Get the TestLog object for a given row."""
        if 0 <= row < len(self._raw_data):
            return self._raw_data[row].get('_test_log')
        return None
    
    def get_row_data(self, row: int) -> Optional[Dict]:
        """Get the raw data dict for a given row."""
        if 0 <= row < len(self._raw_data):
            return self._raw_data[row]
        return None


class PIABoardTableModel(QAbstractTableModel):
    """Table model for PIA Boards."""
    
    COLUMNS = [
        ("Serial Number", "serial_number"),
        ("Part Number", "part_number"),
        ("Generation/Project", "generation_project"),
        ("Version", "version"),
        ("Test Count", "test_count"),
        ("Created", "created_at"),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[PCBABoard] = []
        self._raw_data: List[Dict] = []
    
    def set_data(self, boards: List[PCBABoard], test_counts: Dict[int, int] = None):
        """Set the data and refresh the model."""
        self.beginResetModel()
        self._data = boards
        self._raw_data = []
        test_counts = test_counts or {}
        
        for board in boards:
            row = {
                'id': board.id,
                'serial_number': board.serial_number or 'N/A',
                'part_number': board.part_number or 'N/A',
                'generation_project': board.generation_project or 'N/A',
                'version': board.version or 'N/A',
                'test_count': test_counts.get(board.id, 0),
                'created_at': board.created_at.strftime('%Y-%m-%d') if board.created_at else 'N/A',
                '_board': board,
            }
            self._raw_data.append(row)
        
        self.endResetModel()
    
    def rowCount(self, parent=QModelIndex()):
        return len(self._raw_data)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)
    
    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._raw_data):
            return None
        
        row_data = self._raw_data[index.row()]
        col_name = self.COLUMNS[index.column()][1]
        
        if role == Qt.ItemDataRole.DisplayRole:
            return str(row_data.get(col_name, 'N/A'))
        elif role == Qt.ItemDataRole.UserRole:
            return row_data
        
        return None
    
    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section][0]
        return None
    
    def get_board(self, row: int) -> Optional[PCBABoard]:
        """Get the PCBABoard object for a given row."""
        if 0 <= row < len(self._raw_data):
            return self._raw_data[row].get('_board')
        return None


class PMTDeviceTableModel(QAbstractTableModel):
    """Table model for PMT Devices."""
    
    COLUMNS = [
        ("Serial Number", "pmt_serial_number"),
        ("Generation", "generation"),
        ("Batch Number", "batch_number"),
        ("Test Count", "test_count"),
        ("Created", "created_at"),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[PMT] = []
        self._raw_data: List[Dict] = []
    
    def set_data(self, pmts: List[PMT], test_counts: Dict[int, int] = None):
        """Set the data and refresh the model."""
        self.beginResetModel()
        self._data = pmts
        self._raw_data = []
        test_counts = test_counts or {}
        
        for pmt in pmts:
            row = {
                'id': pmt.id,
                'pmt_serial_number': pmt.pmt_serial_number or 'N/A',
                'generation': pmt.generation or 'N/A',
                'batch_number': pmt.batch_number or 'N/A',
                'test_count': test_counts.get(pmt.id, 0),
                'created_at': pmt.created_at.strftime('%Y-%m-%d') if pmt.created_at else 'N/A',
                '_pmt': pmt,
            }
            self._raw_data.append(row)
        
        self.endResetModel()
    
    def rowCount(self, parent=QModelIndex()):
        return len(self._raw_data)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)
    
    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._raw_data):
            return None
        
        row_data = self._raw_data[index.row()]
        col_name = self.COLUMNS[index.column()][1]
        
        if role == Qt.ItemDataRole.DisplayRole:
            return str(row_data.get(col_name, 'N/A'))
        elif role == Qt.ItemDataRole.UserRole:
            return row_data
        
        return None
    
    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section][0]
        return None
    
    def get_pmt(self, row: int) -> Optional[PMT]:
        """Get the PMT object for a given row."""
        if 0 <= row < len(self._raw_data):
            return self._raw_data[row].get('_pmt')
        return None


class ManufacturerTableModel(QAbstractTableModel):
    """Table model for Manufacturers."""
    
    COLUMNS = [
        ("Name", "name"),
        ("Description", "description"),
        ("Website", "website"),
        ("Spec Count", "spec_count"),
        ("Batch Count", "batch_count"),
        ("Created", "created_at"),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[Manufacturer] = []
        self._raw_data: List[Dict] = []
    
    def set_data(self, manufacturers: List[Manufacturer]):
        """Set the data and refresh the model."""
        self.beginResetModel()
        self._data = manufacturers
        self._raw_data = []
        
        for mfr in manufacturers:
            row = {
                'id': mfr.id,
                'name': mfr.name or 'N/A',
                'description': mfr.description or 'N/A',
                'website': mfr.website or 'N/A',
                'spec_count': len(mfr.specs) if mfr.specs else 0,
                'batch_count': len(mfr.device_batches) if mfr.device_batches else 0,
                'created_at': mfr.created_at.strftime('%Y-%m-%d') if mfr.created_at else 'N/A',
                '_manufacturer': mfr,
            }
            self._raw_data.append(row)
        
        self.endResetModel()
    
    def rowCount(self, parent=QModelIndex()):
        return len(self._raw_data)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)
    
    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._raw_data):
            return None
        
        row_data = self._raw_data[index.row()]
        col_name = self.COLUMNS[index.column()][1]
        
        if role == Qt.ItemDataRole.DisplayRole:
            return str(row_data.get(col_name, 'N/A'))
        elif role == Qt.ItemDataRole.UserRole:
            return row_data
        
        return None
    
    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section][0]
        return None


class DatabasePage:
    """
    Manages the database page functionality.
    
    Provides:
    - Multi-mode browsing (Test Logs, PIA Boards, PMT Devices, Manufacturers)
    - Advanced filtering and search
    - Detail panel for viewing/editing records
    - Database sync from remote fixtures
    - HTML report viewing
    """
    
    def __init__(self, main_window, db_manager: DatabaseManager):
        """
        Initialize the database page.
        
        Args:
            main_window: Reference to the main application window
            db_manager: Database manager instance
        """
        self.main_window = main_window
        self.db = db_manager
        
        # Current state
        self.current_view_mode = ViewMode.TEST_LOGS
        self.selected_record = None
        self.is_dirty = False  # Track unsaved changes
        
        # Query workers
        self.query_worker: Optional[DatabaseQueryWorker] = None
        self.query_thread: Optional[QThread] = None
        
        # Table models
        self.test_log_model = TestLogTableModel()
        self.pia_board_model = PIABoardTableModel()
        self.pmt_device_model = PMTDeviceTableModel()
        self.manufacturer_model = ManufacturerTableModel()
        
        # Build the UI
        self.setup_ui()
        
        # Connect signals
        self.setup_connections()
        
        # Load initial data
        self.load_data()
        
        logger.info("DatabasePage initialized")
    
    def setup_ui(self):
        """Build the database page UI - loads from .ui file or creates programmatically."""
        from PyQt6 import uic
        from pathlib import Path
        
        mw = self.main_window
        
        # Get the database_page widget from the UI
        if not hasattr(mw, 'database_page'):
            logger.error("database_page widget not found in main window")
            return
        
        database_page = mw.database_page
        
        # Try to load from .ui file first
        ui_file = Path(__file__).parent.parent / 'user_interfaces' / 'database_page.ui'
        
        if ui_file.exists():
            try:
                # Load the UI file into the existing widget
                # Clear any existing layout
                if database_page.layout():
                    QWidget().setLayout(database_page.layout())
                
                # Load UI
                loaded_widget = uic.loadUi(str(ui_file))
                
                # Create a layout for the database_page and add the loaded widget
                layout = QHBoxLayout(database_page)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
                layout.addWidget(loaded_widget)
                
                # Get references to widgets from the loaded UI
                self._get_ui_widgets(loaded_widget)
                
                logger.info("DatabasePage UI loaded from .ui file")
                return
                
            except Exception as e:
                logger.warning(f"Failed to load database_page.ui: {e}. Falling back to programmatic UI.")
        
        # Fallback: Create UI programmatically
        self._setup_ui_programmatic(database_page)
    
    def _get_ui_widgets(self, ui):
        """Get widget references from loaded UI file."""
        # View mode radio buttons
        self.test_logs_radio = ui.findChild(QRadioButton, 'test_logs_radio')
        self.pia_boards_radio = ui.findChild(QRadioButton, 'pia_boards_radio')
        self.pmt_devices_radio = ui.findChild(QRadioButton, 'pmt_devices_radio')
        self.manufacturers_radio = ui.findChild(QRadioButton, 'manufacturers_radio')
        
        # Create button group
        self.view_mode_group = QButtonGroup()
        if self.test_logs_radio:
            self.test_logs_radio.setProperty('view_mode', ViewMode.TEST_LOGS)
            self.view_mode_group.addButton(self.test_logs_radio)
        if self.pia_boards_radio:
            self.pia_boards_radio.setProperty('view_mode', ViewMode.PIA_BOARDS)
            self.view_mode_group.addButton(self.pia_boards_radio)
        if self.pmt_devices_radio:
            self.pmt_devices_radio.setProperty('view_mode', ViewMode.PMT_DEVICES)
            self.view_mode_group.addButton(self.pmt_devices_radio)
        if self.manufacturers_radio:
            self.manufacturers_radio.setProperty('view_mode', ViewMode.MANUFACTURERS)
            self.view_mode_group.addButton(self.manufacturers_radio)
        
        # Filter controls
        self.search_input = ui.findChild(QLineEdit, 'search_input')
        self.fixture_filter_combo = ui.findChild(QComboBox, 'fixture_filter_combo')
        self.fixture_filter_label = ui.findChild(QLabel, 'fixture_filter_label') or QLabel()
        self.result_filter_combo = ui.findChild(QComboBox, 'result_filter_combo')
        self.result_filter_label = ui.findChild(QLabel, 'result_filter_label') or QLabel()
        self.date_from_edit = ui.findChild(QDateEdit, 'date_from_edit')
        self.date_to_edit = ui.findChild(QDateEdit, 'date_to_edit')
        self.full_test_only_checkbox = ui.findChild(QCheckBox, 'full_test_only_checkbox')
        
        # Set default dates if found
        if self.date_from_edit:
            self.date_from_edit.setDate(QDate.currentDate().addMonths(-6))
        if self.date_to_edit:
            self.date_to_edit.setDate(QDate.currentDate())
        
        # Buttons
        self.apply_filters_btn = ui.findChild(QPushButton, 'apply_filters_btn')
        self.clear_filters_btn = ui.findChild(QPushButton, 'clear_filters_btn')
        self.add_entry_btn = ui.findChild(QPushButton, 'add_entry_btn')
        self.sync_btn = ui.findChild(QPushButton, 'sync_btn')
        self.refresh_btn = ui.findChild(QPushButton, 'refresh_btn')
        
        # Labels
        self.page_title = ui.findChild(QLabel, 'page_title')
        self.page_subtitle = ui.findChild(QLabel, 'page_subtitle')
        self.db_stats_label = ui.findChild(QLabel, 'db_stats_label')
        
        # Table
        self.table_view = ui.findChild(QTableWidget, 'table_view')
        
        # Detail panel
        self.detail_panel = ui.findChild(QFrame, 'detail_panel')
        if self.detail_panel:
            self.detail_panel.setVisible(False)
        self.detail_title = ui.findChild(QLabel, 'detail_title')
        self.detail_fields_container = ui.findChild(QWidget, 'detail_fields_container')
        
        # Detail panel buttons
        self.save_btn = ui.findChild(QPushButton, 'save_btn')
        self.discard_btn = ui.findChild(QPushButton, 'discard_btn')
        self.delete_btn = ui.findChild(QPushButton, 'delete_btn')
        self.view_html_btn = ui.findChild(QPushButton, 'view_html_btn')
        self.open_browser_btn = ui.findChild(QPushButton, 'open_browser_btn')
        
        # Initialize detail field storage
        self.detail_fields: Dict[str, QWidget] = {}
    
    def _setup_ui_programmatic(self, database_page):
        """Fallback: Create UI programmatically if .ui file not available."""
        # Main horizontal layout
        main_layout = QHBoxLayout(database_page)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ==================== SIDEBAR ====================
        sidebar_frame = QFrame()
        sidebar_frame.setProperty('class', 'side-bar-frame')
        sidebar_frame.setMinimumWidth(280)
        sidebar_frame.setMaximumWidth(280)
        
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        
        # Sidebar scroll area
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        sidebar_content = QWidget()
        sidebar_content_layout = QVBoxLayout(sidebar_content)
        sidebar_content_layout.setContentsMargins(15, 15, 15, 15)
        sidebar_content_layout.setSpacing(12)
        
        # --- View Mode Section ---
        view_mode_label = QLabel("View Mode")
        view_mode_label.setProperty('class', 'heading-3')
        sidebar_content_layout.addWidget(view_mode_label)
        
        self.view_mode_group = QButtonGroup()
        view_modes = [
            (ViewMode.TEST_LOGS, "📋 Test Logs"),
            (ViewMode.PIA_BOARDS, "🔧 PIA Boards"),
            (ViewMode.PMT_DEVICES, "💡 PMT Devices"),
            (ViewMode.MANUFACTURERS, "🏭 Manufacturers"),
        ]
        
        for mode, label in view_modes:
            radio = QRadioButton(label)
            radio.setProperty('view_mode', mode)
            self.view_mode_group.addButton(radio)
            sidebar_content_layout.addWidget(radio)
            if mode == ViewMode.TEST_LOGS:
                radio.setChecked(True)
        
        # Divider
        self._add_divider(sidebar_content_layout)
        
        # --- Filter Section ---
        filter_label = QLabel("Filters")
        filter_label.setProperty('class', 'heading-3')
        sidebar_content_layout.addWidget(filter_label)
        
        # Search box
        search_label = QLabel("Search")
        sidebar_content_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by serial, part #, name...")
        self.search_input.setClearButtonEnabled(True)
        sidebar_content_layout.addWidget(self.search_input)
        
        # Test Fixture filter (for Test Logs mode)
        self.fixture_filter_label = QLabel("Test Fixture")
        sidebar_content_layout.addWidget(self.fixture_filter_label)
        
        self.fixture_filter_combo = QComboBox()
        self.fixture_filter_combo.addItem("All Fixtures", None)
        sidebar_content_layout.addWidget(self.fixture_filter_combo)
        
        # Result filter (for Test Logs mode)
        self.result_filter_label = QLabel("Result")
        sidebar_content_layout.addWidget(self.result_filter_label)
        
        self.result_filter_combo = QComboBox()
        self.result_filter_combo.addItems(["All Results", "Passed Only", "Failed Only"])
        sidebar_content_layout.addWidget(self.result_filter_combo)
        
        # Date range filter
        self.date_filter_label = QLabel("Date Range")
        sidebar_content_layout.addWidget(self.date_filter_label)
        
        date_layout = QHBoxLayout()
        self.date_from_edit = QDateEdit()
        self.date_from_edit.setCalendarPopup(True)
        self.date_from_edit.setDate(QDate.currentDate().addMonths(-6))
        self.date_from_edit.setDisplayFormat("yyyy-MM-dd")
        date_layout.addWidget(self.date_from_edit)
        
        date_to_label = QLabel("to")
        date_to_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_layout.addWidget(date_to_label)
        
        self.date_to_edit = QDateEdit()
        self.date_to_edit.setCalendarPopup(True)
        self.date_to_edit.setDate(QDate.currentDate())
        self.date_to_edit.setDisplayFormat("yyyy-MM-dd")
        date_layout.addWidget(self.date_to_edit)
        
        sidebar_content_layout.addLayout(date_layout)
        
        # Full test only checkbox (for Test Logs mode)
        self.full_test_only_checkbox = QPushButton("Full Tests Only")
        self.full_test_only_checkbox.setCheckable(True)
        self.full_test_only_checkbox.setProperty('class', 'btn-ghost')
        sidebar_content_layout.addWidget(self.full_test_only_checkbox)
        
        # Apply Filters button
        self.apply_filters_btn = QPushButton("🔍  Apply Filters")
        self.apply_filters_btn.setProperty('class', 'btn-primary')
        sidebar_content_layout.addWidget(self.apply_filters_btn)
        
        # Clear Filters button
        self.clear_filters_btn = QPushButton("Clear Filters")
        self.clear_filters_btn.setProperty('class', 'btn-secondary')
        sidebar_content_layout.addWidget(self.clear_filters_btn)
        
        # Divider
        self._add_divider(sidebar_content_layout)
        
        # --- Database Status Section ---
        status_label = QLabel("Database Status")
        status_label.setProperty('class', 'heading-3')
        sidebar_content_layout.addWidget(status_label)
        
        self.db_status_frame = QFrame()
        self.db_status_frame.setProperty('class', 'container-secondary')
        status_frame_layout = QVBoxLayout(self.db_status_frame)
        status_frame_layout.setContentsMargins(10, 10, 10, 10)
        status_frame_layout.setSpacing(4)
        
        self.db_status_label = QLabel("● Online")
        self.db_status_label.setStyleSheet("color: #22c55e; font-weight: bold;")
        status_frame_layout.addWidget(self.db_status_label)
        
        self.db_path_label = QLabel("SQLite 3.x")
        self.db_path_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        status_frame_layout.addWidget(self.db_path_label)
        
        self.db_stats_label = QLabel("")
        self.db_stats_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        status_frame_layout.addWidget(self.db_stats_label)
        
        sidebar_content_layout.addWidget(self.db_status_frame)
        
        # Spacer to push content to top
        sidebar_content_layout.addStretch()
        
        sidebar_scroll.setWidget(sidebar_content)
        sidebar_layout.addWidget(sidebar_scroll)
        
        main_layout.addWidget(sidebar_frame)
        
        # ==================== MAIN CONTENT AREA ====================
        content_frame = QFrame()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(20, 15, 20, 15)
        content_layout.setSpacing(15)
        
        # --- Header Section ---
        header_layout = QHBoxLayout()
        
        # Title and subtitle
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        
        self.page_title = QLabel("Database Browser")
        self.page_title.setProperty('class', 'heading-1')
        title_layout.addWidget(self.page_title)
        
        self.page_subtitle = QLabel("62 Test Logs | 28 PIA Boards | 15 PMTs")
        self.page_subtitle.setStyleSheet("color: #94a3b8;")
        title_layout.addWidget(self.page_subtitle)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        # Action buttons
        self.add_entry_btn = QPushButton("+ Add Entry")
        self.add_entry_btn.setProperty('class', 'btn-primary')
        header_layout.addWidget(self.add_entry_btn)
        
        self.sync_btn = QPushButton("🔄 Sync")
        self.sync_btn.setProperty('class', 'btn-secondary')
        self.sync_btn.setToolTip("Sync database from remote test fixtures")
        header_layout.addWidget(self.sync_btn)
        
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setProperty('class', 'btn-icon')
        self.refresh_btn.setToolTip("Refresh data")
        header_layout.addWidget(self.refresh_btn)
        
        content_layout.addLayout(header_layout)
        
        # --- Main Table ---
        self.table_view = QTableWidget()
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)
        self.table_view.setShowGrid(True)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        content_layout.addWidget(self.table_view, stretch=1)
        
        # --- Detail Panel (initially hidden) ---
        self.detail_panel = QFrame()
        self.detail_panel.setProperty('class', 'container-secondary')
        self.detail_panel.setMinimumHeight(200)
        self.detail_panel.setMaximumHeight(280)
        self.detail_panel.setVisible(False)
        
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(15, 15, 15, 15)
        detail_layout.setSpacing(12)
        
        # Detail header
        detail_header = QHBoxLayout()
        
        self.detail_title = QLabel("📋 Record Details")
        self.detail_title.setProperty('class', 'heading-3')
        detail_header.addWidget(self.detail_title)
        
        self.detail_id_label = QLabel("ID: ---")
        self.detail_id_label.setStyleSheet("color: #64748b; font-size: 11px;")
        detail_header.addWidget(self.detail_id_label)
        
        detail_header.addStretch()
        
        self.discard_btn = QPushButton("Discard")
        self.discard_btn.setProperty('class', 'btn-ghost')
        detail_header.addWidget(self.discard_btn)
        
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setProperty('class', 'btn-primary')
        detail_header.addWidget(self.save_btn)
        
        self.delete_btn = QPushButton("🗑️")
        self.delete_btn.setProperty('class', 'btn-danger btn-icon')
        self.delete_btn.setToolTip("Delete this record")
        detail_header.addWidget(self.delete_btn)
        
        detail_layout.addLayout(detail_header)
        
        # Detail fields container - will be populated based on view mode
        self.detail_fields_container = QWidget()
        self.detail_fields_layout = QHBoxLayout(self.detail_fields_container)
        self.detail_fields_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_fields_layout.setSpacing(20)
        detail_layout.addWidget(self.detail_fields_container)
        
        # Detail footer with actions
        detail_footer = QHBoxLayout()
        
        self.detail_created_label = QLabel("Created: ---")
        self.detail_created_label.setStyleSheet("color: #64748b; font-size: 11px;")
        detail_footer.addWidget(self.detail_created_label)
        
        detail_footer.addStretch()
        
        # View HTML button (for test logs)
        self.view_html_btn = QPushButton("👁️ View HTML Report")
        self.view_html_btn.setProperty('class', 'btn-info')
        self.view_html_btn.setVisible(False)
        detail_footer.addWidget(self.view_html_btn)
        
        self.open_browser_btn = QPushButton("🌐 Open in Browser")
        self.open_browser_btn.setProperty('class', 'btn-ghost')
        self.open_browser_btn.setVisible(False)
        detail_footer.addWidget(self.open_browser_btn)
        
        detail_layout.addLayout(detail_footer)
        
        content_layout.addWidget(self.detail_panel)
        
        main_layout.addWidget(content_frame, stretch=1)
        
        # Store widget references on main window for potential external access
        mw.db_page_table = self.table_view
        mw.db_page_detail_panel = self.detail_panel
    
    def _add_divider(self, layout: QVBoxLayout):
        """Add a horizontal divider line to a layout."""
        divider = QFrame()
        divider.setMinimumHeight(2)
        divider.setMaximumHeight(2)
        divider.setStyleSheet("background-color: #334155;")
        layout.addWidget(divider)
    
    def setup_connections(self):
        """Connect UI signals to handlers."""
        # View mode changes
        self.view_mode_group.buttonClicked.connect(self.on_view_mode_changed)
        
        # Filter controls
        self.apply_filters_btn.clicked.connect(self.on_apply_filters)
        self.clear_filters_btn.clicked.connect(self.on_clear_filters)
        self.search_input.returnPressed.connect(self.on_apply_filters)
        
        # Table selection
        self.table_view.itemSelectionChanged.connect(self.on_table_selection_changed)
        self.table_view.customContextMenuRequested.connect(self.on_table_context_menu)
        
        # Action buttons
        self.add_entry_btn.clicked.connect(self.on_add_entry)
        self.sync_btn.clicked.connect(self.on_sync_database)
        self.refresh_btn.clicked.connect(self.load_data)
        
        # Detail panel buttons
        self.save_btn.clicked.connect(self.on_save_changes)
        self.discard_btn.clicked.connect(self.on_discard_changes)
        self.delete_btn.clicked.connect(self.on_delete_record)
        self.view_html_btn.clicked.connect(self.on_view_html_report)
        self.open_browser_btn.clicked.connect(self.on_open_in_browser)
        
        logger.info("DatabasePage connections established")
    
    def on_view_mode_changed(self, button: QRadioButton):
        """Handle view mode change."""
        mode = button.property('view_mode')
        if mode and mode != self.current_view_mode:
            self.current_view_mode = mode
            self._update_filter_visibility()
            self.load_data()
            self.detail_panel.setVisible(False)
            logger.info(f"View mode changed to: {mode}")
    
    def _update_filter_visibility(self):
        """Show/hide filter controls based on current view mode."""
        is_test_logs = self.current_view_mode == ViewMode.TEST_LOGS
        
        self.fixture_filter_label.setVisible(is_test_logs)
        self.fixture_filter_combo.setVisible(is_test_logs)
        self.result_filter_label.setVisible(is_test_logs)
        self.result_filter_combo.setVisible(is_test_logs)
        self.full_test_only_checkbox.setVisible(is_test_logs)
        
        # Update title
        titles = {
            ViewMode.TEST_LOGS: "Test Log Browser",
            ViewMode.PIA_BOARDS: "PIA Board Registry",
            ViewMode.PMT_DEVICES: "PMT Device Registry",
            ViewMode.MANUFACTURERS: "Manufacturer Database",
        }
        self.page_title.setText(titles.get(self.current_view_mode, "Database Browser"))
    
    def on_apply_filters(self):
        """Apply current filters and reload data."""
        self.load_data()
    
    def on_clear_filters(self):
        """Clear all filters and reload data."""
        self.search_input.clear()
        self.fixture_filter_combo.setCurrentIndex(0)
        self.result_filter_combo.setCurrentIndex(0)
        self.date_from_edit.setDate(QDate.currentDate().addMonths(-6))
        self.date_to_edit.setDate(QDate.currentDate())
        self.full_test_only_checkbox.setChecked(False)
        self.load_data()
    
    def load_data(self):
        """Load data based on current view mode and filters."""
        try:
            if self.current_view_mode == ViewMode.TEST_LOGS:
                self._load_test_logs()
            elif self.current_view_mode == ViewMode.PIA_BOARDS:
                self._load_pia_boards()
            elif self.current_view_mode == ViewMode.PMT_DEVICES:
                self._load_pmt_devices()
            elif self.current_view_mode == ViewMode.MANUFACTURERS:
                self._load_manufacturers()
            
            self._update_stats()
            
        except Exception as e:
            logger.exception("Error loading data")
            QMessageBox.critical(
                self.main_window,
                "Database Error",
                f"Failed to load data: {str(e)}"
            )
    
    def _load_test_logs(self):
        """Load test logs with current filters."""
        try:
            with self.db.session_scope() as session:
                from sqlalchemy.orm import joinedload
                from sqlalchemy import desc
                
                query = session.query(TestLog).options(
                    joinedload(TestLog.pia_board),
                    joinedload(TestLog.pmt_device)
                )
                
                # Apply filters
                search_term = self.search_input.text().strip()
                if search_term:
                    term = f"%{search_term}%"
                    query = query.join(TestLog.pia_board, isouter=True).join(
                        TestLog.pmt_device, isouter=True
                    ).filter(
                        (PCBABoard.serial_number.ilike(term)) |
                        (PCBABoard.part_number.ilike(term)) |
                        (PMT.pmt_serial_number.ilike(term)) |
                        (TestLog.name.ilike(term))
                    )
                
                # Test fixture filter
                fixture = self.fixture_filter_combo.currentData()
                if fixture:
                    query = query.filter(TestLog.test_fixture == fixture)
                
                # Result filter
                result_filter = self.result_filter_combo.currentText()
                if result_filter == "Passed Only":
                    query = query.filter(TestLog.full_test_passed == True)
                elif result_filter == "Failed Only":
                    query = query.filter(TestLog.full_test_passed == False)
                
                # Full test only
                if self.full_test_only_checkbox.isChecked():
                    query = query.filter(TestLog.full_test_completed == True)
                
                # Date range
                from_date = self.date_from_edit.date().toPyDate()
                to_date = self.date_to_edit.date().toPyDate()
                query = query.filter(
                    TestLog.created_at >= datetime.combine(from_date, datetime.min.time()),
                    TestLog.created_at <= datetime.combine(to_date, datetime.max.time())
                )
                
                # Order by date descending
                query = query.order_by(desc(TestLog.created_at))
                
                test_logs = query.all()
                
                # Detach from session for use in UI
                # Track already expunged objects to avoid duplicate expunge errors
                expunged_ids = set()
                for tl in test_logs:
                    if id(tl) not in expunged_ids:
                        session.expunge(tl)
                        expunged_ids.add(id(tl))
                    if tl.pia_board and id(tl.pia_board) not in expunged_ids:
                        session.expunge(tl.pia_board)
                        expunged_ids.add(id(tl.pia_board))
                    if tl.pmt_device and id(tl.pmt_device) not in expunged_ids:
                        session.expunge(tl.pmt_device)
                        expunged_ids.add(id(tl.pmt_device))
                
                self._populate_test_log_table(test_logs)
                self.page_subtitle.setText(f"{len(test_logs)} Test Logs")
                
        except Exception as e:
            logger.exception("Error loading test logs")
            raise
    
    def _populate_test_log_table(self, test_logs: List[TestLog]):
        """Populate the table with test log data."""
        columns = [
            "Test Name", "Test Date", "Result", "Full Test", "Test Fixture",
            "PIA Part #", "PIA Serial #", "PMT Batch #", "PMT Serial #"
        ]
        
        self.table_view.clear()
        self.table_view.setRowCount(len(test_logs))
        self.table_view.setColumnCount(len(columns))
        self.table_view.setHorizontalHeaderLabels(columns)
        
        for row, tl in enumerate(test_logs):
            # Store test log reference
            items = []
            
            # Test Name
            item = QTableWidgetItem(tl.name or 'N/A')
            item.setData(Qt.ItemDataRole.UserRole, tl)
            items.append(item)
            
            # Test Date
            date_str = tl.created_at.strftime('%Y-%m-%d %H:%M') if tl.created_at else 'N/A'
            items.append(QTableWidgetItem(date_str))
            
            # Result
            if tl.full_test_passed is None:
                result_item = QTableWidgetItem('N/A')
            elif tl.full_test_passed:
                result_item = QTableWidgetItem('✓ PASS')
                result_item.setForeground(QBrush(QColor('#22c55e')))
            else:
                result_item = QTableWidgetItem('✗ FAIL')
                result_item.setForeground(QBrush(QColor('#ef4444')))
            result_item.setFont(QFont('', -1, QFont.Weight.Bold))
            items.append(result_item)
            
            # Full Test
            if tl.full_test_completed is None:
                full_item = QTableWidgetItem('N/A')
            elif tl.full_test_completed:
                full_item = QTableWidgetItem('✓ Yes')
                full_item.setForeground(QBrush(QColor('#22c55e')))
            else:
                full_item = QTableWidgetItem('○ No')
            items.append(full_item)
            
            # Test Fixture
            items.append(QTableWidgetItem(tl.test_fixture or 'N/A'))
            
            # PIA Part #
            pia_part = tl.pia_board.part_number if tl.pia_board and tl.pia_board.part_number else 'N/A'
            items.append(QTableWidgetItem(pia_part))
            
            # PIA Serial #
            pia_serial = tl.pia_board.serial_number if tl.pia_board and tl.pia_board.serial_number else 'N/A'
            items.append(QTableWidgetItem(pia_serial))
            
            # PMT Batch #
            pmt_batch = tl.pmt_device.batch_number if tl.pmt_device and tl.pmt_device.batch_number else 'N/A'
            items.append(QTableWidgetItem(pmt_batch))
            
            # PMT Serial #
            pmt_serial = tl.pmt_device.pmt_serial_number if tl.pmt_device and tl.pmt_device.pmt_serial_number else 'N/A'
            items.append(QTableWidgetItem(pmt_serial))
            
            for col, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table_view.setItem(row, col, item)
        
        # Resize columns to content
        self.table_view.resizeColumnsToContents()
    
    def _load_pia_boards(self):
        """Load PIA boards with current filters."""
        try:
            with self.db.session_scope() as session:
                from sqlalchemy import func
                
                query = session.query(PCBABoard)
                
                # Apply search filter
                search_term = self.search_input.text().strip()
                if search_term:
                    term = f"%{search_term}%"
                    query = query.filter(
                        (PCBABoard.serial_number.ilike(term)) |
                        (PCBABoard.part_number.ilike(term))
                    )
                
                boards = query.all()
                
                # Get test counts per board
                test_counts = dict(
                    session.query(TestLog.pia_board_id, func.count(TestLog.id))
                    .group_by(TestLog.pia_board_id)
                    .all()
                )
                
                # Detach from session
                for board in boards:
                    session.expunge(board)
                
                self._populate_pia_board_table(boards, test_counts)
                self.page_subtitle.setText(f"{len(boards)} PIA Boards")
                
        except Exception as e:
            logger.exception("Error loading PIA boards")
            raise
    
    def _populate_pia_board_table(self, boards: List[PCBABoard], test_counts: Dict[int, int]):
        """Populate the table with PIA board data."""
        columns = ["Serial Number", "Part Number", "Generation/Project", "Version", "Test Count", "Created"]
        
        self.table_view.clear()
        self.table_view.setRowCount(len(boards))
        self.table_view.setColumnCount(len(columns))
        self.table_view.setHorizontalHeaderLabels(columns)
        
        for row, board in enumerate(boards):
            items = [
                QTableWidgetItem(board.serial_number or 'N/A'),
                QTableWidgetItem(board.part_number or 'N/A'),
                QTableWidgetItem(board.generation_project or 'N/A'),
                QTableWidgetItem(board.version or 'N/A'),
                QTableWidgetItem(str(test_counts.get(board.id, 0))),
                QTableWidgetItem(board.created_at.strftime('%Y-%m-%d') if board.created_at else 'N/A'),
            ]
            
            items[0].setData(Qt.ItemDataRole.UserRole, board)
            
            for col, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table_view.setItem(row, col, item)
        
        self.table_view.resizeColumnsToContents()
    
    def _load_pmt_devices(self):
        """Load PMT devices with current filters."""
        try:
            with self.db.session_scope() as session:
                from sqlalchemy import func
                
                query = session.query(PMT)
                
                # Apply search filter
                search_term = self.search_input.text().strip()
                if search_term:
                    term = f"%{search_term}%"
                    query = query.filter(
                        (PMT.pmt_serial_number.ilike(term)) |
                        (PMT.batch_number.ilike(term))
                    )
                
                pmts = query.all()
                
                # Get test counts per PMT
                test_counts = dict(
                    session.query(TestLog.pmt_id, func.count(TestLog.id))
                    .filter(TestLog.pmt_id.isnot(None))
                    .group_by(TestLog.pmt_id)
                    .all()
                )
                
                # Detach from session
                for pmt in pmts:
                    session.expunge(pmt)
                
                self._populate_pmt_table(pmts, test_counts)
                self.page_subtitle.setText(f"{len(pmts)} PMT Devices")
                
        except Exception as e:
            logger.exception("Error loading PMT devices")
            raise
    
    def _populate_pmt_table(self, pmts: List[PMT], test_counts: Dict[int, int]):
        """Populate the table with PMT device data."""
        columns = ["Serial Number", "Generation", "Batch Number", "Test Count", "Created"]
        
        self.table_view.clear()
        self.table_view.setRowCount(len(pmts))
        self.table_view.setColumnCount(len(columns))
        self.table_view.setHorizontalHeaderLabels(columns)
        
        for row, pmt in enumerate(pmts):
            items = [
                QTableWidgetItem(pmt.pmt_serial_number or 'N/A'),
                QTableWidgetItem(pmt.generation or 'N/A'),
                QTableWidgetItem(pmt.batch_number or 'N/A'),
                QTableWidgetItem(str(test_counts.get(pmt.id, 0))),
                QTableWidgetItem(pmt.created_at.strftime('%Y-%m-%d') if pmt.created_at else 'N/A'),
            ]
            
            items[0].setData(Qt.ItemDataRole.UserRole, pmt)
            
            for col, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table_view.setItem(row, col, item)
        
        self.table_view.resizeColumnsToContents()
    
    def _load_manufacturers(self):
        """Load manufacturers with current filters."""
        try:
            with self.db.session_scope() as session:
                from sqlalchemy.orm import joinedload
                
                query = session.query(Manufacturer).options(
                    joinedload(Manufacturer.specs),
                    joinedload(Manufacturer.device_batches)
                )
                
                # Apply search filter
                search_term = self.search_input.text().strip()
                if search_term:
                    term = f"%{search_term}%"
                    query = query.filter(
                        (Manufacturer.name.ilike(term)) |
                        (Manufacturer.description.ilike(term))
                    )
                
                manufacturers = query.all()
                
                # Detach from session
                for mfr in manufacturers:
                    session.expunge(mfr)
                
                self._populate_manufacturer_table(manufacturers)
                self.page_subtitle.setText(f"{len(manufacturers)} Manufacturers")
                
        except Exception as e:
            logger.exception("Error loading manufacturers")
            raise
    
    def _populate_manufacturer_table(self, manufacturers: List[Manufacturer]):
        """Populate the table with manufacturer data."""
        columns = ["Name", "Description", "Website", "Spec Count", "Batch Count", "Created"]
        
        self.table_view.clear()
        self.table_view.setRowCount(len(manufacturers))
        self.table_view.setColumnCount(len(columns))
        self.table_view.setHorizontalHeaderLabels(columns)
        
        for row, mfr in enumerate(manufacturers):
            items = [
                QTableWidgetItem(mfr.name or 'N/A'),
                QTableWidgetItem(mfr.description or 'N/A'),
                QTableWidgetItem(mfr.website or 'N/A'),
                QTableWidgetItem(str(len(mfr.specs) if mfr.specs else 0)),
                QTableWidgetItem(str(len(mfr.device_batches) if mfr.device_batches else 0)),
                QTableWidgetItem(mfr.created_at.strftime('%Y-%m-%d') if mfr.created_at else 'N/A'),
            ]
            
            items[0].setData(Qt.ItemDataRole.UserRole, mfr)
            
            for col, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table_view.setItem(row, col, item)
        
        self.table_view.resizeColumnsToContents()
    
    def _update_stats(self):
        """Update database statistics in the sidebar."""
        try:
            stats = self.db.get_database_stats()
            self.db_stats_label.setText(
                f"{stats['total_boards']} boards | {stats['total_pmts']} PMTs | {stats['total_test_logs']} logs"
            )
        except Exception as e:
            logger.error(f"Error updating stats: {e}")
    
    def on_table_selection_changed(self):
        """Handle table row selection change."""
        selected_items = self.table_view.selectedItems()
        if not selected_items:
            self.detail_panel.setVisible(False)
            self.selected_record = None
            return
        
        # Get the record from the first column's user data
        row = selected_items[0].row()
        first_col_item = self.table_view.item(row, 0)
        if not first_col_item:
            return
        
        record = first_col_item.data(Qt.ItemDataRole.UserRole)
        if not record:
            return
        
        self.selected_record = record
        self._populate_detail_panel(record)
        self.detail_panel.setVisible(True)
    
    def _populate_detail_panel(self, record):
        """Populate the detail panel based on record type."""
        # Clear existing fields
        while self.detail_fields_layout.count():
            child = self.detail_fields_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Store field references for saving
        self.detail_fields = {}
        
        if isinstance(record, TestLog):
            self._populate_test_log_details(record)
        elif isinstance(record, PCBABoard):
            self._populate_pia_board_details(record)
        elif isinstance(record, PMT):
            self._populate_pmt_details(record)
        elif isinstance(record, Manufacturer):
            self._populate_manufacturer_details(record)
    
    def _populate_test_log_details(self, test_log: TestLog):
        """Populate detail panel for a test log."""
        self.detail_title.setText("📋 Test Log Details")
        self.detail_id_label.setText(f"ID: {test_log.id}")
        self.detail_created_label.setText(
            f"Created: {test_log.created_at.strftime('%Y-%m-%d %H:%M') if test_log.created_at else 'N/A'}"
        )
        
        # Show HTML buttons for test logs
        self.view_html_btn.setVisible(True)
        self.open_browser_btn.setVisible(True)
        
        # Column 1: Test info
        col1 = QVBoxLayout()
        col1.setSpacing(8)
        
        # Test Name (read-only)
        col1.addWidget(QLabel("Test Name"))
        name_edit = QLineEdit(test_log.name or '')
        name_edit.setReadOnly(True)
        name_edit.setStyleSheet("background-color: #1e293b;")
        col1.addWidget(name_edit)
        
        # Test Fixture (editable)
        col1.addWidget(QLabel("Test Fixture"))
        fixture_edit = QLineEdit(test_log.test_fixture or '')
        self.detail_fields['test_fixture'] = fixture_edit
        col1.addWidget(fixture_edit)
        
        col1.addStretch()
        
        col1_widget = QWidget()
        col1_widget.setLayout(col1)
        self.detail_fields_layout.addWidget(col1_widget)
        
        # Column 2: PIA info
        col2 = QVBoxLayout()
        col2.setSpacing(8)
        
        col2.addWidget(QLabel("PIA Serial Number"))
        pia_serial_edit = QLineEdit(
            test_log.pia_board.serial_number if test_log.pia_board else ''
        )
        self.detail_fields['pia_serial_number'] = pia_serial_edit
        col2.addWidget(pia_serial_edit)
        
        col2.addWidget(QLabel("PIA Part Number"))
        pia_part_edit = QLineEdit(
            test_log.pia_board.part_number if test_log.pia_board else ''
        )
        self.detail_fields['pia_part_number'] = pia_part_edit
        col2.addWidget(pia_part_edit)
        
        col2.addStretch()
        
        col2_widget = QWidget()
        col2_widget.setLayout(col2)
        self.detail_fields_layout.addWidget(col2_widget)
        
        # Column 3: PMT info
        col3 = QVBoxLayout()
        col3.setSpacing(8)
        
        col3.addWidget(QLabel("PMT Serial Number"))
        pmt_serial_edit = QLineEdit(
            test_log.pmt_device.pmt_serial_number if test_log.pmt_device else ''
        )
        self.detail_fields['pmt_serial_number'] = pmt_serial_edit
        col3.addWidget(pmt_serial_edit)
        
        col3.addWidget(QLabel("Result"))
        result_label = QLabel()
        if test_log.full_test_passed is None:
            result_label.setText("N/A")
        elif test_log.full_test_passed:
            result_label.setText("✓ PASSED")
            result_label.setStyleSheet("color: #22c55e; font-weight: bold; font-size: 14px;")
        else:
            result_label.setText("✗ FAILED")
            result_label.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 14px;")
        col3.addWidget(result_label)
        
        col3.addStretch()
        
        col3_widget = QWidget()
        col3_widget.setLayout(col3)
        self.detail_fields_layout.addWidget(col3_widget)
        
        self.detail_fields_layout.addStretch()
    
    def _populate_pia_board_details(self, board: PCBABoard):
        """Populate detail panel for a PIA board."""
        self.detail_title.setText("🔧 PIA Board Details")
        self.detail_id_label.setText(f"ID: {board.id}")
        self.detail_created_label.setText(
            f"Created: {board.created_at.strftime('%Y-%m-%d %H:%M') if board.created_at else 'N/A'}"
        )
        
        # Hide HTML buttons for non-test-log records
        self.view_html_btn.setVisible(False)
        self.open_browser_btn.setVisible(False)
        
        # Column 1
        col1 = QVBoxLayout()
        col1.setSpacing(8)
        
        col1.addWidget(QLabel("Serial Number"))
        serial_edit = QLineEdit(board.serial_number or '')
        self.detail_fields['serial_number'] = serial_edit
        col1.addWidget(serial_edit)
        
        col1.addWidget(QLabel("Part Number"))
        part_edit = QLineEdit(board.part_number or '')
        self.detail_fields['part_number'] = part_edit
        col1.addWidget(part_edit)
        
        col1.addStretch()
        
        col1_widget = QWidget()
        col1_widget.setLayout(col1)
        self.detail_fields_layout.addWidget(col1_widget)
        
        # Column 2
        col2 = QVBoxLayout()
        col2.setSpacing(8)
        
        col2.addWidget(QLabel("Generation/Project"))
        gen_edit = QLineEdit(board.generation_project or '')
        self.detail_fields['generation_project'] = gen_edit
        col2.addWidget(gen_edit)
        
        col2.addWidget(QLabel("Version"))
        version_edit = QLineEdit(board.version or '')
        self.detail_fields['version'] = version_edit
        col2.addWidget(version_edit)
        
        col2.addStretch()
        
        col2_widget = QWidget()
        col2_widget.setLayout(col2)
        self.detail_fields_layout.addWidget(col2_widget)
        
        self.detail_fields_layout.addStretch()
    
    def _populate_pmt_details(self, pmt: PMT):
        """Populate detail panel for a PMT device."""
        self.detail_title.setText("💡 PMT Device Details")
        self.detail_id_label.setText(f"ID: {pmt.id}")
        self.detail_created_label.setText(
            f"Created: {pmt.created_at.strftime('%Y-%m-%d %H:%M') if pmt.created_at else 'N/A'}"
        )
        
        self.view_html_btn.setVisible(False)
        self.open_browser_btn.setVisible(False)
        
        # Column 1
        col1 = QVBoxLayout()
        col1.setSpacing(8)
        
        col1.addWidget(QLabel("Serial Number"))
        serial_edit = QLineEdit(pmt.pmt_serial_number or '')
        self.detail_fields['pmt_serial_number'] = serial_edit
        col1.addWidget(serial_edit)
        
        col1.addWidget(QLabel("Batch Number"))
        batch_edit = QLineEdit(pmt.batch_number or '')
        self.detail_fields['batch_number'] = batch_edit
        col1.addWidget(batch_edit)
        
        col1.addStretch()
        
        col1_widget = QWidget()
        col1_widget.setLayout(col1)
        self.detail_fields_layout.addWidget(col1_widget)
        
        # Column 2
        col2 = QVBoxLayout()
        col2.setSpacing(8)
        
        col2.addWidget(QLabel("Generation"))
        gen_edit = QLineEdit(pmt.generation or '')
        self.detail_fields['generation'] = gen_edit
        col2.addWidget(gen_edit)
        
        col2.addStretch()
        
        col2_widget = QWidget()
        col2_widget.setLayout(col2)
        self.detail_fields_layout.addWidget(col2_widget)
        
        self.detail_fields_layout.addStretch()
    
    def _populate_manufacturer_details(self, mfr: Manufacturer):
        """Populate detail panel for a manufacturer."""
        self.detail_title.setText("🏭 Manufacturer Details")
        self.detail_id_label.setText(f"ID: {mfr.id}")
        self.detail_created_label.setText(
            f"Created: {mfr.created_at.strftime('%Y-%m-%d %H:%M') if mfr.created_at else 'N/A'}"
        )
        
        self.view_html_btn.setVisible(False)
        self.open_browser_btn.setVisible(False)
        
        # Column 1
        col1 = QVBoxLayout()
        col1.setSpacing(8)
        
        col1.addWidget(QLabel("Name"))
        name_edit = QLineEdit(mfr.name or '')
        self.detail_fields['name'] = name_edit
        col1.addWidget(name_edit)
        
        col1.addWidget(QLabel("Website"))
        website_edit = QLineEdit(mfr.website or '')
        self.detail_fields['website'] = website_edit
        col1.addWidget(website_edit)
        
        col1.addStretch()
        
        col1_widget = QWidget()
        col1_widget.setLayout(col1)
        self.detail_fields_layout.addWidget(col1_widget)
        
        # Column 2
        col2 = QVBoxLayout()
        col2.setSpacing(8)
        
        col2.addWidget(QLabel("Description"))
        desc_edit = QLineEdit(mfr.description or '')
        self.detail_fields['description'] = desc_edit
        col2.addWidget(desc_edit)
        
        col2.addWidget(QLabel("Contact Info"))
        contact_edit = QLineEdit(mfr.contact_info or '')
        self.detail_fields['contact_info'] = contact_edit
        col2.addWidget(contact_edit)
        
        col2.addStretch()
        
        col2_widget = QWidget()
        col2_widget.setLayout(col2)
        self.detail_fields_layout.addWidget(col2_widget)
        
        self.detail_fields_layout.addStretch()
    
    def on_table_context_menu(self, position):
        """Show context menu for table."""
        menu = QMenu()
        
        view_action = QAction("View Details", self.main_window)
        view_action.triggered.connect(lambda: self.on_table_selection_changed())
        menu.addAction(view_action)
        
        if self.current_view_mode == ViewMode.TEST_LOGS:
            html_action = QAction("View HTML Report", self.main_window)
            html_action.triggered.connect(self.on_view_html_report)
            menu.addAction(html_action)
            
            browser_action = QAction("Open in Browser", self.main_window)
            browser_action.triggered.connect(self.on_open_in_browser)
            menu.addAction(browser_action)
        
        menu.addSeparator()
        
        delete_action = QAction("Delete Record", self.main_window)
        delete_action.triggered.connect(self.on_delete_record)
        menu.addAction(delete_action)
        
        menu.exec(self.table_view.viewport().mapToGlobal(position))
    
    def on_save_changes(self):
        """Save changes to the selected record."""
        if not self.selected_record or not self.detail_fields:
            return
        
        try:
            with self.db.session_scope() as session:
                if isinstance(self.selected_record, TestLog):
                    # Reload the test log in this session
                    test_log = session.query(TestLog).get(self.selected_record.id)
                    if test_log:
                        test_log.test_fixture = self.detail_fields['test_fixture'].text() or None
                        
                        # Update PIA board
                        if test_log.pia_board:
                            test_log.pia_board.serial_number = self.detail_fields['pia_serial_number'].text() or None
                            test_log.pia_board.part_number = self.detail_fields['pia_part_number'].text() or None
                        
                        # Update PMT
                        if test_log.pmt_device:
                            test_log.pmt_device.pmt_serial_number = self.detail_fields['pmt_serial_number'].text() or None
                
                elif isinstance(self.selected_record, PCBABoard):
                    board = session.query(PCBABoard).get(self.selected_record.id)
                    if board:
                        board.serial_number = self.detail_fields['serial_number'].text() or None
                        board.part_number = self.detail_fields['part_number'].text() or None
                        board.generation_project = self.detail_fields['generation_project'].text() or None
                        board.version = self.detail_fields['version'].text() or None
                
                elif isinstance(self.selected_record, PMT):
                    pmt = session.query(PMT).get(self.selected_record.id)
                    if pmt:
                        pmt.pmt_serial_number = self.detail_fields['pmt_serial_number'].text() or None
                        pmt.batch_number = self.detail_fields['batch_number'].text() or None
                        pmt.generation = self.detail_fields['generation'].text() or None
                
                elif isinstance(self.selected_record, Manufacturer):
                    mfr = session.query(Manufacturer).get(self.selected_record.id)
                    if mfr:
                        mfr.name = self.detail_fields['name'].text() or None
                        mfr.description = self.detail_fields['description'].text() or None
                        mfr.website = self.detail_fields['website'].text() or None
                        mfr.contact_info = self.detail_fields['contact_info'].text() or None
            
            QMessageBox.information(
                self.main_window,
                "Success",
                "Changes saved successfully."
            )
            
            # Reload data to reflect changes
            self.load_data()
            
        except Exception as e:
            logger.exception("Error saving changes")
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Failed to save changes: {str(e)}"
            )
    
    def on_discard_changes(self):
        """Discard changes and reload the detail panel."""
        if self.selected_record:
            self._populate_detail_panel(self.selected_record)
    
    def on_delete_record(self):
        """Delete the selected record after confirmation."""
        if not self.selected_record:
            return
        
        # Confirm deletion
        record_type = type(self.selected_record).__name__
        reply = QMessageBox.question(
            self.main_window,
            "Confirm Deletion",
            f"Are you sure you want to delete this {record_type} record?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            with self.db.session_scope() as session:
                record_id = self.selected_record.id
                
                if isinstance(self.selected_record, TestLog):
                    record = session.query(TestLog).get(record_id)
                elif isinstance(self.selected_record, PCBABoard):
                    record = session.query(PCBABoard).get(record_id)
                elif isinstance(self.selected_record, PMT):
                    record = session.query(PMT).get(record_id)
                elif isinstance(self.selected_record, Manufacturer):
                    record = session.query(Manufacturer).get(record_id)
                else:
                    return
                
                if record:
                    session.delete(record)
            
            QMessageBox.information(
                self.main_window,
                "Success",
                "Record deleted successfully."
            )
            
            self.selected_record = None
            self.detail_panel.setVisible(False)
            self.load_data()
            
        except Exception as e:
            logger.exception("Error deleting record")
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Failed to delete record: {str(e)}"
            )
    
    def on_view_html_report(self):
        """View the HTML test report in the search page viewer."""
        if not isinstance(self.selected_record, TestLog):
            return
        
        try:
            mw = self.main_window
            
            # Use the search page handler if available
            if hasattr(mw, 'search_page_handler') and mw.search_page_handler:
                mw.search_page_handler.load_report_from_database_page(self.selected_record.id)
            else:
                # Fallback: Load HTML directly
                html_content = self.db.get_test_log_html(self.selected_record.id)
                
                if not html_content:
                    QMessageBox.warning(
                        self.main_window,
                        "No Report",
                        "No HTML report available for this test log."
                    )
                    return
                
                # Navigate to search page and display HTML
                if hasattr(mw, 'main_section_stackedWidget') and hasattr(mw, 'search_page'):
                    mw.main_section_stackedWidget.setCurrentWidget(mw.search_page)
                
                # Load HTML in webviewer (if it exists)
                if hasattr(mw, 'test_log_webViewer'):
                    mw.test_log_webViewer.setHtml(html_content)
            
            logger.info(f"Displaying HTML report for test log {self.selected_record.id}")
            
        except Exception as e:
            logger.exception("Error viewing HTML report")
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Failed to load HTML report: {str(e)}"
            )
    
    def on_open_in_browser(self):
        """Open the HTML test report in Chrome browser."""
        if not isinstance(self.selected_record, TestLog):
            return
        
        try:
            import subprocess
            import sys
            import tempfile
            
            # Get the HTML content or path
            html_path = None
            if self.selected_record.html_path and os.path.exists(self.selected_record.html_path):
                html_path = self.selected_record.html_path
            else:
                # Create a temp file
                html_content = self.db.get_test_log_html(self.selected_record.id)
                if html_content:
                    with tempfile.NamedTemporaryFile(
                        mode='w', suffix='.html', delete=False, encoding='utf-8'
                    ) as f:
                        f.write(html_content)
                        html_path = f.name
                else:
                    QMessageBox.warning(
                        self.main_window,
                        "No Report",
                        "No HTML report available for this test log."
                    )
                    return
            
            # Try to open with Chrome specifically
            chrome_paths = []
            if sys.platform == 'win32':
                # Windows Chrome paths
                chrome_paths = [
                    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                    os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
                ]
            elif sys.platform == 'darwin':
                # macOS Chrome path
                chrome_paths = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
            else:
                # Linux Chrome paths
                chrome_paths = ['/usr/bin/google-chrome', '/usr/bin/chromium-browser', '/usr/bin/chromium']
            
            chrome_opened = False
            for chrome_path in chrome_paths:
                if os.path.exists(chrome_path):
                    subprocess.Popen([chrome_path, f"file://{html_path}"])
                    chrome_opened = True
                    break
            
            if not chrome_opened:
                # Fallback to default browser
                webbrowser.open(f"file://{html_path}")
            
        except Exception as e:
            logger.exception("Error opening in browser")
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Failed to open in browser: {str(e)}"
            )
    
    def on_add_entry(self):
        """Handle adding a new entry based on current view mode."""
        if self.current_view_mode == ViewMode.MANUFACTURERS:
            self._add_manufacturer_dialog()
        else:
            QMessageBox.information(
                self.main_window,
                "Add Entry",
                f"Add {self.current_view_mode} functionality to be implemented.\n\n"
                "For now, records are typically created during test execution."
            )
    
    def _add_manufacturer_dialog(self):
        """Show dialog to add a new manufacturer."""
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        
        dialog = QDialog(self.main_window)
        dialog.setWindowTitle("Add Manufacturer")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()
        
        name_edit = QLineEdit()
        form_layout.addRow("Name:", name_edit)
        
        desc_edit = QLineEdit()
        form_layout.addRow("Description:", desc_edit)
        
        website_edit = QLineEdit()
        form_layout.addRow("Website:", website_edit)
        
        contact_edit = QLineEdit()
        form_layout.addRow("Contact Info:", contact_edit)
        
        layout.addLayout(form_layout)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_edit.text().strip()
            if not name:
                QMessageBox.warning(
                    self.main_window,
                    "Validation Error",
                    "Manufacturer name is required."
                )
                return
            
            try:
                with self.db.session_scope() as session:
                    mfr = Manufacturer(
                        name=name,
                        description=desc_edit.text().strip() or None,
                        website=website_edit.text().strip() or None,
                        contact_info=contact_edit.text().strip() or None
                    )
                    session.add(mfr)
                
                QMessageBox.information(
                    self.main_window,
                    "Success",
                    f"Manufacturer '{name}' added successfully."
                )
                self.load_data()
                
            except Exception as e:
                logger.exception("Error adding manufacturer")
                QMessageBox.critical(
                    self.main_window,
                    "Error",
                    f"Failed to add manufacturer: {str(e)}"
                )
    
    def on_sync_database(self):
        """Sync database from remote test fixtures."""
        # TODO: Implement actual sync logic based on configured paths
        QMessageBox.information(
            self.main_window,
            "Sync Database",
            "Database sync functionality.\n\n"
            "This will collect database files from configured test fixture paths.\n\n"
            "Configure sync paths in settings to enable this feature."
        )
    
    def load_fixture_filter_options(self):
        """Load available test fixtures into the filter combo."""
        try:
            with self.db.session_scope() as session:
                fixtures = session.query(TestLog.test_fixture).distinct().all()
                
                self.fixture_filter_combo.clear()
                self.fixture_filter_combo.addItem("All Fixtures", None)
                
                for (fixture,) in fixtures:
                    if fixture:
                        self.fixture_filter_combo.addItem(fixture, fixture)
                        
        except Exception as e:
            logger.error(f"Error loading fixture options: {e}")
    
    def cleanup(self):
        """Clean up resources when page is destroyed."""
        if self.query_worker:
            self.query_worker.cancel()
        if self.query_thread and self.query_thread.isRunning():
            self.query_thread.quit()
            self.query_thread.wait()
        
        logger.info("DatabasePage cleaned up")
