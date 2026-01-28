"""
Search / Report Viewer Page - View and compare HTML test reports.

Features:
- Search test logs by part numbers and serial numbers with autocomplete
- View HTML test reports in embedded web viewer
- Export HTML reports to files
- Compare two test reports side-by-side
- Zoom and print controls
- Quick navigation and recent reports history

Author: Generated for PCBA Database Application
"""
import logging
import os
import tempfile
import webbrowser
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QFrame, QScrollArea, QMessageBox, QCompleter,
    QApplication, QFileDialog, QSplitter, QListWidget, QListWidgetItem,
    QSizePolicy, QStackedWidget, QSlider, QToolBar, QToolButton,
    QMenu, QWidgetAction
)
from PyQt6.QtCore import (
    Qt, QUrl, QStringListModel, QTimer, QSize
)
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtWebEngineWidgets import QWebEngineView

from src.database import DatabaseManager
from src.database.database_device_tables import PCBABoard, PMT
from src.database.database_test_log_tables import TestLog, SubTest, Spec

logger = logging.getLogger(__name__)


class ReportViewerWidget(QFrame):
    """
    A widget containing a QWebEngineView with toolbar controls.
    
    Features:
    - HTML rendering
    - Zoom controls
    - Print functionality
    - Export to file
    - Open in browser
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_test_log: Optional[TestLog] = None
        self.current_html: Optional[str] = None
        self.zoom_level = 100
        
        self.setup_ui()
    
    def setup_ui(self):
        """Build the viewer UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Toolbar
        toolbar = QFrame()
        toolbar.setProperty('class', 'container-secondary')
        toolbar.setMaximumHeight(45)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 5, 10, 5)
        toolbar_layout.setSpacing(8)
        
        # Report info label
        self.report_info_label = QLabel("No report loaded")
        self.report_info_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        toolbar_layout.addWidget(self.report_info_label)
        
        toolbar_layout.addStretch()
        
        # Zoom controls
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setProperty('class', 'btn-ghost btn-sm')
        zoom_out_btn.setFixedWidth(30)
        zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.clicked.connect(self.zoom_out)
        toolbar_layout.addWidget(zoom_out_btn)
        
        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(45)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar_layout.addWidget(self.zoom_label)
        
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setProperty('class', 'btn-ghost btn-sm')
        zoom_in_btn.setFixedWidth(30)
        zoom_in_btn.setToolTip("Zoom In")
        zoom_in_btn.clicked.connect(self.zoom_in)
        toolbar_layout.addWidget(zoom_in_btn)
        
        zoom_reset_btn = QPushButton("Reset")
        zoom_reset_btn.setProperty('class', 'btn-ghost btn-sm')
        zoom_reset_btn.setToolTip("Reset Zoom")
        zoom_reset_btn.clicked.connect(self.zoom_reset)
        toolbar_layout.addWidget(zoom_reset_btn)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("background-color: #334155;")
        sep.setMaximumWidth(1)
        toolbar_layout.addWidget(sep)
        
        # Print button
        print_btn = QPushButton("🖨️ Print")
        print_btn.setProperty('class', 'btn-ghost btn-sm')
        print_btn.setToolTip("Print Report")
        print_btn.clicked.connect(self.print_report)
        toolbar_layout.addWidget(print_btn)
        
        # Export button
        export_btn = QPushButton("💾 Export")
        export_btn.setProperty('class', 'btn-ghost btn-sm')
        export_btn.setToolTip("Export HTML to File")
        export_btn.clicked.connect(self.export_html)
        toolbar_layout.addWidget(export_btn)
        
        # Open in browser button
        browser_btn = QPushButton("🌐 Browser")
        browser_btn.setProperty('class', 'btn-ghost btn-sm')
        browser_btn.setToolTip("Open in System Browser")
        browser_btn.clicked.connect(self.open_in_browser)
        toolbar_layout.addWidget(browser_btn)
        
        layout.addWidget(toolbar)
        
        # Web view
        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(300)
        layout.addWidget(self.web_view)
    
    def load_test_log(self, test_log: TestLog, html_content: str):
        """Load a test log report into the viewer."""
        self.current_test_log = test_log
        self.current_html = html_content
        
        # Update info label
        if test_log:
            pia_serial = test_log.pia_board.serial_number if test_log.pia_board else "N/A"
            date_str = test_log.created_at.strftime('%Y-%m-%d %H:%M') if test_log.created_at else "N/A"
            self.report_info_label.setText(f"{test_log.name or 'Test Log'} | {pia_serial} | {date_str}")
        else:
            self.report_info_label.setText("Report loaded")
        
        # Load HTML
        if html_content:
            self.web_view.setHtml(html_content)
        else:
            self.web_view.setHtml("<html><body><h2>No HTML content available</h2></body></html>")
        
        # Reset zoom
        self.zoom_reset()
    
    def load_html(self, html_content: str, title: str = "Report"):
        """Load raw HTML content without a test log reference."""
        self.current_test_log = None
        self.current_html = html_content
        self.report_info_label.setText(title)
        
        if html_content:
            self.web_view.setHtml(html_content)
        else:
            self.web_view.setHtml("<html><body><h2>No content</h2></body></html>")
        
        self.zoom_reset()
    
    def clear(self):
        """Clear the viewer."""
        self.current_test_log = None
        self.current_html = None
        self.report_info_label.setText("No report loaded")
        self.web_view.setHtml("")
    
    def zoom_in(self):
        """Increase zoom level."""
        self.zoom_level = min(200, self.zoom_level + 10)
        self._apply_zoom()
    
    def zoom_out(self):
        """Decrease zoom level."""
        self.zoom_level = max(50, self.zoom_level - 10)
        self._apply_zoom()
    
    def zoom_reset(self):
        """Reset zoom to 100%."""
        self.zoom_level = 100
        self._apply_zoom()
    
    def _apply_zoom(self):
        """Apply current zoom level to web view."""
        self.web_view.setZoomFactor(self.zoom_level / 100)
        self.zoom_label.setText(f"{self.zoom_level}%")
    
    def print_report(self):
        """Print the current report."""
        if not self.current_html:
            return
        
        # Use the web view's print functionality
        self.web_view.page().printToPdf(self._get_temp_pdf_path())
        QMessageBox.information(
            self,
            "Print",
            "Use your browser's print dialog for best results.\n"
            "Click 'Browser' to open the report in your default browser."
        )
    
    def _get_temp_pdf_path(self) -> str:
        """Get a temporary path for PDF export."""
        return os.path.join(tempfile.gettempdir(), "pcba_report_print.pdf")
    
    def export_html(self):
        """Export the current HTML to a file."""
        if not self.current_html:
            QMessageBox.warning(self, "No Report", "No report loaded to export.")
            return
        
        # Generate default filename
        if self.current_test_log:
            pia_serial = self.current_test_log.pia_board.serial_number if self.current_test_log.pia_board else "unknown"
            date_str = self.current_test_log.created_at.strftime('%Y%m%d_%H%M%S') if self.current_test_log.created_at else "unknown"
            default_name = f"test_report_{pia_serial}_{date_str}.html"
        else:
            default_name = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export HTML Report",
            default_name,
            "HTML Files (*.html);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.current_html)
                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Report exported to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Export Error",
                    f"Failed to export: {str(e)}"
                )
    
    def open_in_browser(self):
        """Open the current report in Chrome browser."""
        if not self.current_html:
            QMessageBox.warning(self, "No Report", "No report loaded.")
            return
        
        try:
            import subprocess
            import sys
            
            # Create temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(self.current_html)
                temp_path = f.name
            
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
                    subprocess.Popen([chrome_path, f"file://{temp_path}"])
                    chrome_opened = True
                    break
            
            if not chrome_opened:
                # Fallback to default browser
                webbrowser.open(f"file://{temp_path}")
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open in browser: {str(e)}"
            )


class SearchPage:
    """
    Manages the search/report viewer page functionality.
    
    Provides:
    - Search test logs by part numbers and serial numbers
    - Autocomplete from database values
    - View HTML test reports
    - Compare two reports side-by-side
    - Export and print functionality
    - Recent reports history
    """
    
    MAX_RECENT_REPORTS = 10
    
    def __init__(self, main_window, db_manager: DatabaseManager):
        """
        Initialize the search page.
        
        Args:
            main_window: Reference to the main application window
            db_manager: Database manager instance
        """
        self.main_window = main_window
        self.db = db_manager
        
        # State
        self.recent_reports: List[Dict] = []  # [{test_log_id, title, timestamp}, ...]
        self.compare_mode = False
        self.autocomplete_data: List[str] = []
        
        # Build the UI
        self.setup_ui()
        
        # Connect signals
        self.setup_connections()
        
        # Load autocomplete data
        self.load_autocomplete_data()
        
        logger.info("SearchPage initialized")
    
    def setup_ui(self):
        """Build the search page UI - loads from .ui file or creates programmatically."""
        from PyQt6 import uic
        from pathlib import Path
        
        mw = self.main_window
        
        # Get the search_page widget from the UI
        if not hasattr(mw, 'search_page'):
            logger.error("search_page widget not found in main window")
            return
        
        search_page = mw.search_page
        
        # Try to load from .ui file first
        ui_file = Path(__file__).parent.parent / 'user_interfaces' / 'search_page.ui'
        
        if ui_file.exists():
            try:
                # Clear any existing layout
                if search_page.layout():
                    QWidget().setLayout(search_page.layout())
                
                # Load UI
                loaded_widget = uic.loadUi(str(ui_file))
                
                # Create a layout for the search_page and add the loaded widget
                layout = QHBoxLayout(search_page)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
                layout.addWidget(loaded_widget)
                
                # Get references to widgets from the loaded UI
                self._get_ui_widgets(loaded_widget)
                
                # Setup WebEngine views (not in UI file - requires PyQt6-WebEngine)
                self._setup_web_views(loaded_widget)
                
                logger.info("SearchPage UI loaded from .ui file")
                return
                
            except Exception as e:
                logger.warning(f"Failed to load search_page.ui: {e}. Falling back to programmatic UI.")
        
        # Fallback: Create UI programmatically
        self._setup_ui_programmatic(search_page)
    
    def _get_ui_widgets(self, ui):
        """Get widget references from loaded UI file."""
        # Search controls
        self.search_input = ui.findChild(QLineEdit, 'search_input')
        self.search_btn = ui.findChild(QPushButton, 'search_btn')
        
        # Setup autocomplete on search input
        if self.search_input:
            self.completer = QCompleter()
            self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.search_input.setCompleter(self.completer)
        
        # Results list
        self.results_list = ui.findChild(QListWidget, 'results_list')
        self.result_count_label = ui.findChild(QLabel, 'result_count_label')
        
        # Compare mode controls
        self.compare_btn = ui.findChild(QPushButton, 'compare_btn')
        self.compare_selection_frame = ui.findChild(QFrame, 'compare_selection_frame')
        self.compare_left_label = ui.findChild(QLabel, 'compare_left_label')
        self.compare_right_label = ui.findChild(QLabel, 'compare_right_label')
        self.clear_compare_btn = ui.findChild(QPushButton, 'clear_compare_btn')
        
        # Recent reports
        self.recent_list = ui.findChild(QListWidget, 'recent_list')
        self.clear_recent_btn = ui.findChild(QPushButton, 'clear_recent_btn')
        
        # Labels
        self.page_title = ui.findChild(QLabel, 'page_title')
        self.page_subtitle = ui.findChild(QLabel, 'page_subtitle')
        
        # Viewer stack
        self.viewer_stack = ui.findChild(QStackedWidget, 'viewer_stack')
        
        # Single viewer toolbar controls
        self.report_info_label = ui.findChild(QLabel, 'report_info_label')
        self.zoom_out_btn = ui.findChild(QPushButton, 'zoom_out_btn')
        self.zoom_in_btn = ui.findChild(QPushButton, 'zoom_in_btn')
        self.zoom_reset_btn = ui.findChild(QPushButton, 'zoom_reset_btn')
        self.zoom_label = ui.findChild(QLabel, 'zoom_label')
        self.print_btn = ui.findChild(QPushButton, 'print_btn')
        self.export_html_btn = ui.findChild(QPushButton, 'export_html_btn')
        self.browser_btn = ui.findChild(QPushButton, 'browser_btn')
        
        # Compare state
        self._compare_left_id = None
        self._compare_right_id = None
    
    def _setup_web_views(self, ui):
        """Setup QWebEngineView widgets (added dynamically)."""
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            logger.warning("PyQt6-WebEngine not installed. HTML viewing will be limited.")
            return
        
        # Single viewer webview
        webview_container = ui.findChild(QWidget, 'webview_container')
        if webview_container:
            self.single_viewer = ReportViewerWidget()
            container_layout = webview_container.layout()
            if container_layout:
                container_layout.addWidget(self.single_viewer)
        
        # Compare viewers
        left_container = ui.findChild(QWidget, 'left_viewer_container')
        if left_container:
            self.left_viewer = ReportViewerWidget()
            container_layout = left_container.layout()
            if container_layout:
                container_layout.addWidget(self.left_viewer)
        
        right_container = ui.findChild(QWidget, 'right_viewer_container')
        if right_container:
            self.right_viewer = ReportViewerWidget()
            container_layout = right_container.layout()
            if container_layout:
                container_layout.addWidget(self.right_viewer)
    
    def _setup_ui_programmatic(self, search_page):
        """Fallback: Create UI programmatically if .ui file not available."""
        # Clear any existing layout
        if search_page.layout():
            QWidget().setLayout(search_page.layout())
        
        # Main horizontal layout
        main_layout = QHBoxLayout(search_page)
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
        
        # --- Search Section ---
        search_label = QLabel("Search Test Logs")
        search_label.setProperty('class', 'heading-3')
        sidebar_content_layout.addWidget(search_label)
        
        # Search input with autocomplete
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter serial # or part #...")
        self.search_input.setClearButtonEnabled(True)
        sidebar_content_layout.addWidget(self.search_input)
        
        # Setup autocomplete
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.search_input.setCompleter(self.completer)
        
        # Search button
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.setProperty('class', 'btn-primary')
        sidebar_content_layout.addWidget(self.search_btn)
        
        # Divider
        self._add_divider(sidebar_content_layout)
        
        # --- Search Results Section ---
        results_label = QLabel("Search Results")
        results_label.setProperty('class', 'heading-3')
        sidebar_content_layout.addWidget(results_label)
        
        self.results_list = QListWidget()
        self.results_list.setMaximumHeight(200)
        self.results_list.setAlternatingRowColors(True)
        sidebar_content_layout.addWidget(self.results_list)
        
        # Result count label
        self.result_count_label = QLabel("No results")
        self.result_count_label.setStyleSheet("color: #64748b; font-size: 11px;")
        sidebar_content_layout.addWidget(self.result_count_label)
        
        # Divider
        self._add_divider(sidebar_content_layout)
        
        # --- Compare Section ---
        compare_label = QLabel("Compare Reports")
        compare_label.setProperty('class', 'heading-3')
        sidebar_content_layout.addWidget(compare_label)
        
        self.compare_btn = QPushButton("📊 Compare Mode")
        self.compare_btn.setProperty('class', 'btn-secondary')
        self.compare_btn.setCheckable(True)
        self.compare_btn.setToolTip("Enable side-by-side comparison of two reports")
        sidebar_content_layout.addWidget(self.compare_btn)
        
        # Compare instructions
        self.compare_instructions = QLabel(
            "Enable compare mode, then select\ntwo reports from search results."
        )
        self.compare_instructions.setStyleSheet("color: #64748b; font-size: 11px;")
        self.compare_instructions.setWordWrap(True)
        sidebar_content_layout.addWidget(self.compare_instructions)
        
        # Compare selection display
        self.compare_selection_frame = QFrame()
        self.compare_selection_frame.setProperty('class', 'container-tertiary')
        self.compare_selection_frame.setVisible(False)
        compare_sel_layout = QVBoxLayout(self.compare_selection_frame)
        compare_sel_layout.setContentsMargins(8, 8, 8, 8)
        compare_sel_layout.setSpacing(4)
        
        self.compare_left_label = QLabel("Left: Not selected")
        self.compare_left_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        compare_sel_layout.addWidget(self.compare_left_label)
        
        self.compare_right_label = QLabel("Right: Not selected")
        self.compare_right_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        compare_sel_layout.addWidget(self.compare_right_label)
        
        self.clear_compare_btn = QPushButton("Clear Selection")
        self.clear_compare_btn.setProperty('class', 'btn-ghost btn-sm')
        compare_sel_layout.addWidget(self.clear_compare_btn)
        
        sidebar_content_layout.addWidget(self.compare_selection_frame)
        
        # Divider
        self._add_divider(sidebar_content_layout)
        
        # --- Recent Reports Section ---
        recent_label = QLabel("Recent Reports")
        recent_label.setProperty('class', 'heading-3')
        sidebar_content_layout.addWidget(recent_label)
        
        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(150)
        self.recent_list.setAlternatingRowColors(True)
        sidebar_content_layout.addWidget(self.recent_list)
        
        # Clear recent button
        self.clear_recent_btn = QPushButton("Clear History")
        self.clear_recent_btn.setProperty('class', 'btn-ghost btn-sm')
        sidebar_content_layout.addWidget(self.clear_recent_btn)
        
        # Spacer
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
        
        # Title
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        
        self.page_title = QLabel("Report Viewer")
        self.page_title.setProperty('class', 'heading-1')
        title_layout.addWidget(self.page_title)
        
        self.page_subtitle = QLabel("Search and view HTML test reports")
        self.page_subtitle.setStyleSheet("color: #94a3b8;")
        title_layout.addWidget(self.page_subtitle)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        content_layout.addLayout(header_layout)
        
        # --- Viewer Area ---
        # This will switch between single view and compare view
        self.viewer_stack = QStackedWidget()
        
        # Single viewer
        self.single_viewer = ReportViewerWidget()
        self.viewer_stack.addWidget(self.single_viewer)
        
        # Compare viewer (side-by-side)
        self.compare_widget = QWidget()
        compare_layout = QHBoxLayout(self.compare_widget)
        compare_layout.setContentsMargins(0, 0, 0, 0)
        compare_layout.setSpacing(10)
        
        self.compare_left_viewer = ReportViewerWidget()
        compare_layout.addWidget(self.compare_left_viewer)
        
        # Vertical divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setStyleSheet("background-color: #334155;")
        divider.setMaximumWidth(2)
        compare_layout.addWidget(divider)
        
        self.compare_right_viewer = ReportViewerWidget()
        compare_layout.addWidget(self.compare_right_viewer)
        
        self.viewer_stack.addWidget(self.compare_widget)
        
        content_layout.addWidget(self.viewer_stack)
        
        main_layout.addWidget(content_frame, stretch=1)
        
        # Store references
        mw.report_viewer = self.single_viewer
        mw.test_log_webViewer = self.single_viewer.web_view  # For compatibility
    
    def _add_divider(self, layout: QVBoxLayout):
        """Add a horizontal divider line to a layout."""
        divider = QFrame()
        divider.setMinimumHeight(2)
        divider.setMaximumHeight(2)
        divider.setStyleSheet("background-color: #334155;")
        layout.addWidget(divider)
    
    def setup_connections(self):
        """Connect UI signals to handlers."""
        # Search
        self.search_btn.clicked.connect(self.perform_search)
        self.search_input.returnPressed.connect(self.perform_search)
        
        # Results selection
        self.results_list.itemClicked.connect(self.on_result_selected)
        self.results_list.itemDoubleClicked.connect(self.on_result_double_clicked)
        
        # Compare mode
        self.compare_btn.toggled.connect(self.on_compare_mode_toggled)
        self.clear_compare_btn.clicked.connect(self.clear_compare_selection)
        
        # Recent reports
        self.recent_list.itemDoubleClicked.connect(self.on_recent_selected)
        self.clear_recent_btn.clicked.connect(self.clear_recent_reports)
        
        logger.info("SearchPage connections established")
    
    def load_autocomplete_data(self):
        """Load autocomplete data from database."""
        try:
            with self.db.session_scope() as session:
                autocomplete_values = set()
                
                # PIA serial numbers
                pia_serials = session.query(PCBABoard.serial_number).distinct().all()
                for (serial,) in pia_serials:
                    if serial:
                        autocomplete_values.add(serial)
                
                # PIA part numbers
                pia_parts = session.query(PCBABoard.part_number).distinct().all()
                for (part,) in pia_parts:
                    if part:
                        autocomplete_values.add(part)
                
                # PMT serial numbers
                pmt_serials = session.query(PMT.pmt_serial_number).distinct().all()
                for (serial,) in pmt_serials:
                    if serial:
                        autocomplete_values.add(serial)
                
                # PMT batch numbers
                pmt_batches = session.query(PMT.batch_number).distinct().all()
                for (batch,) in pmt_batches:
                    if batch:
                        autocomplete_values.add(batch)
                
                self.autocomplete_data = sorted(autocomplete_values)
                
                # Update completer model
                model = QStringListModel(self.autocomplete_data)
                self.completer.setModel(model)
                
                logger.info(f"Loaded {len(self.autocomplete_data)} autocomplete values")
                
        except Exception as e:
            logger.exception("Error loading autocomplete data")
    
    def perform_search(self):
        """Perform search based on input."""
        search_term = self.search_input.text().strip()
        
        if not search_term:
            QMessageBox.warning(
                self.main_window,
                "Empty Search",
                "Please enter a serial number or part number to search."
            )
            return
        
        try:
            with self.db.session_scope() as session:
                from sqlalchemy.orm import joinedload
                from sqlalchemy import or_, desc
                
                # Search across PIA serial, PIA part, PMT serial, PMT batch
                term = f"%{search_term}%"
                
                query = session.query(TestLog).options(
                    joinedload(TestLog.pia_board),
                    joinedload(TestLog.pmt_device)
                ).outerjoin(TestLog.pia_board).outerjoin(TestLog.pmt_device).filter(
                    or_(
                        PCBABoard.serial_number.ilike(term),
                        PCBABoard.part_number.ilike(term),
                        PMT.pmt_serial_number.ilike(term),
                        PMT.batch_number.ilike(term),
                        TestLog.name.ilike(term)
                    )
                ).order_by(desc(TestLog.created_at))
                
                results = query.all()
                
                # Populate results list
                self.results_list.clear()
                
                for test_log in results:
                    # Create display text
                    pia_serial = test_log.pia_board.serial_number if test_log.pia_board else "N/A"
                    pmt_serial = test_log.pmt_device.pmt_serial_number if test_log.pmt_device else "N/A"
                    date_str = test_log.created_at.strftime('%Y-%m-%d') if test_log.created_at else "N/A"
                    
                    display_text = f"{pia_serial} | {date_str}"
                    if test_log.name:
                        display_text = f"{test_log.name[:20]}... | {display_text}"
                    
                    item = QListWidgetItem(display_text)
                    item.setData(Qt.ItemDataRole.UserRole, test_log.id)
                    item.setToolTip(
                        f"Test: {test_log.name or 'N/A'}\n"
                        f"PIA: {pia_serial}\n"
                        f"PMT: {pmt_serial}\n"
                        f"Date: {test_log.created_at or 'N/A'}\n"
                        f"Result: {'PASS' if test_log.full_test_passed else 'FAIL' if test_log.full_test_passed is False else 'N/A'}"
                    )
                    self.results_list.addItem(item)
                
                # Update count
                self.result_count_label.setText(f"{len(results)} result(s) found")
                
                logger.info(f"Search for '{search_term}' found {len(results)} results")
                
        except Exception as e:
            logger.exception("Error performing search")
            QMessageBox.critical(
                self.main_window,
                "Search Error",
                f"Failed to search: {str(e)}"
            )
    
    def on_result_selected(self, item: QListWidgetItem):
        """Handle single click on a search result."""
        if self.compare_mode:
            self._handle_compare_selection(item)
        else:
            # Single click in normal mode - just highlight, don't load
            pass
    
    def on_result_double_clicked(self, item: QListWidgetItem):
        """Handle double click on a search result."""
        test_log_id = item.data(Qt.ItemDataRole.UserRole)
        if test_log_id:
            self.load_report(test_log_id)
    
    def _handle_compare_selection(self, item: QListWidgetItem):
        """Handle selection in compare mode."""
        test_log_id = item.data(Qt.ItemDataRole.UserRole)
        if not test_log_id:
            return
        
        # Check if left or right is empty
        left_id = self.compare_left_label.property('test_log_id')
        right_id = self.compare_right_label.property('test_log_id')
        
        if left_id is None:
            # Set left
            self.compare_left_label.setText(f"Left: {item.text()}")
            self.compare_left_label.setProperty('test_log_id', test_log_id)
            self._load_compare_report(test_log_id, 'left')
        elif right_id is None:
            # Set right
            self.compare_right_label.setText(f"Right: {item.text()}")
            self.compare_right_label.setProperty('test_log_id', test_log_id)
            self._load_compare_report(test_log_id, 'right')
        else:
            # Both filled, replace right
            self.compare_right_label.setText(f"Right: {item.text()}")
            self.compare_right_label.setProperty('test_log_id', test_log_id)
            self._load_compare_report(test_log_id, 'right')
    
    def _load_compare_report(self, test_log_id: int, side: str):
        """Load a report into the compare viewer."""
        try:
            with self.db.session_scope() as session:
                from sqlalchemy.orm import joinedload
                
                test_log = session.query(TestLog).options(
                    joinedload(TestLog.pia_board),
                    joinedload(TestLog.pmt_device)
                ).filter(TestLog.id == test_log_id).first()
                
                if not test_log:
                    return
                
                html_content = test_log.html_content
                
                # Detach for use outside session
                session.expunge(test_log)
                if test_log.pia_board:
                    session.expunge(test_log.pia_board)
                if test_log.pmt_device:
                    session.expunge(test_log.pmt_device)
                
                # Load into appropriate viewer
                if side == 'left':
                    self.compare_left_viewer.load_test_log(test_log, html_content)
                else:
                    self.compare_right_viewer.load_test_log(test_log, html_content)
                
        except Exception as e:
            logger.exception(f"Error loading compare report for {side}")
    
    def on_compare_mode_toggled(self, enabled: bool):
        """Handle compare mode toggle."""
        self.compare_mode = enabled
        self.compare_selection_frame.setVisible(enabled)
        
        if enabled:
            # Switch to compare view
            self.viewer_stack.setCurrentIndex(1)
            self.page_subtitle.setText("Compare mode: Click results to select reports")
            self.results_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        else:
            # Switch to single view
            self.viewer_stack.setCurrentIndex(0)
            self.page_subtitle.setText("Search and view HTML test reports")
            self.clear_compare_selection()
    
    def clear_compare_selection(self):
        """Clear compare mode selections."""
        self.compare_left_label.setText("Left: Not selected")
        self.compare_left_label.setProperty('test_log_id', None)
        self.compare_right_label.setText("Right: Not selected")
        self.compare_right_label.setProperty('test_log_id', None)
        
        self.compare_left_viewer.clear()
        self.compare_right_viewer.clear()
    
    def load_report(self, test_log_id: int):
        """Load a report into the single viewer."""
        try:
            with self.db.session_scope() as session:
                from sqlalchemy.orm import joinedload
                
                test_log = session.query(TestLog).options(
                    joinedload(TestLog.pia_board),
                    joinedload(TestLog.pmt_device)
                ).filter(TestLog.id == test_log_id).first()
                
                if not test_log:
                    QMessageBox.warning(
                        self.main_window,
                        "Not Found",
                        "Test log not found in database."
                    )
                    return
                
                html_content = test_log.html_content
                
                # Detach for use outside session
                session.expunge(test_log)
                if test_log.pia_board:
                    session.expunge(test_log.pia_board)
                if test_log.pmt_device:
                    session.expunge(test_log.pmt_device)
                
                # Ensure we're in single view mode
                if self.compare_mode:
                    self.compare_btn.setChecked(False)
                
                # Load into viewer
                self.single_viewer.load_test_log(test_log, html_content)
                
                # Add to recent reports
                self._add_to_recent(test_log)
                
                logger.info(f"Loaded report for test log {test_log_id}")
                
        except Exception as e:
            logger.exception("Error loading report")
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Failed to load report: {str(e)}"
            )
    
    def load_report_from_database_page(self, test_log_id: int):
        """
        Public method for loading a report from the database page.
        This navigates to the search page and loads the report.
        """
        # Navigate to search page
        mw = self.main_window
        if hasattr(mw, 'main_section_stackedWidget') and hasattr(mw, 'search_page'):
            mw.main_section_stackedWidget.setCurrentWidget(mw.search_page)
        
        # Load the report
        self.load_report(test_log_id)
    
    def _add_to_recent(self, test_log: TestLog):
        """Add a test log to recent reports history."""
        # Create entry
        pia_serial = test_log.pia_board.serial_number if test_log.pia_board else "N/A"
        date_str = test_log.created_at.strftime('%Y-%m-%d %H:%M') if test_log.created_at else "N/A"
        
        entry = {
            'test_log_id': test_log.id,
            'title': f"{pia_serial} | {date_str}",
            'timestamp': datetime.now()
        }
        
        # Remove if already exists
        self.recent_reports = [r for r in self.recent_reports if r['test_log_id'] != test_log.id]
        
        # Add to front
        self.recent_reports.insert(0, entry)
        
        # Trim to max
        self.recent_reports = self.recent_reports[:self.MAX_RECENT_REPORTS]
        
        # Update UI
        self._update_recent_list()
    
    def _update_recent_list(self):
        """Update the recent reports list widget."""
        self.recent_list.clear()
        
        for entry in self.recent_reports:
            item = QListWidgetItem(entry['title'])
            item.setData(Qt.ItemDataRole.UserRole, entry['test_log_id'])
            self.recent_list.addItem(item)
    
    def on_recent_selected(self, item: QListWidgetItem):
        """Handle double click on a recent report."""
        test_log_id = item.data(Qt.ItemDataRole.UserRole)
        if test_log_id:
            self.load_report(test_log_id)
    
    def clear_recent_reports(self):
        """Clear the recent reports history."""
        self.recent_reports.clear()
        self.recent_list.clear()
    
    def display_html(self, html_content: str, title: str = "Report"):
        """
        Display HTML content directly.
        Used by other pages to show reports.
        """
        # Ensure we're in single view mode
        if self.compare_mode:
            self.compare_btn.setChecked(False)
        
        self.single_viewer.load_html(html_content, title)
    
    def cleanup(self):
        """Clean up resources when page is destroyed."""
        logger.info("SearchPage cleaned up")
