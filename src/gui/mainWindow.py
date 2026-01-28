#!/usr/bin/env python3
"""
PCBA Analytics Application
Uses the main_window.user_interfaces with emerald theme
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt6 import uic

import logging

logger = logging.getLogger(__name__)

# Import page handlers
try:
    from src.gui.pages.graph_page import GraphPage
except ImportError:
    GraphPage = None
    logger.warning("GraphPage not found - graph functionality will be limited")

try:
    from src.gui.pages.database_page import DatabasePage
except ImportError:
    DatabasePage = None
    logger.warning("DatabasePage not found - database browser functionality will be limited")

try:
    from src.gui.pages.reports_page import ReportsPage
except ImportError:
    ReportsPage = None
    logger.warning("ReportsPage not found - reports functionality will be limited")

try:
    from src.gui.pages.search_page import SearchPage
except ImportError:
    SearchPage = None
    logger.warning("SearchPage not found - search/viewer functionality will be limited")


class Main_Window(QMainWindow):
    """PCBA Analytics Window with graph display and navigation."""

    def __init__(self, db_manager=None):
        super().__init__()

        # Store database manager
        self.db_manager = db_manager

        # Load UI file
        ui_path = Path(__file__).parent / "user_interfaces" / "main_window.ui"
        uic.loadUi(ui_path, self)

        # Set the window flag to remove the frame
        # self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        # Apply stylesheet
        self.load_stylesheet("ocean", "dark")

        # Initialize pages (only if db_manager provided)
        self.graph_page_handler = None
        if self.db_manager:
            self.setup_pages()

        # Connect signals
        self.setup_connections()

    def load_stylesheet(self, theme: str = "ocean", mode: str = "dark"):
        """Load and apply a QSS stylesheet."""
        theme_style = f"styles_{theme}_{mode}.qss"
        qss_path = Path(__file__).parent / "styling" / "generated" / theme_style

        try:
            with open(qss_path, "r") as f:
                stylesheet = f.read()
                self.setStyleSheet(stylesheet)
                print(f"✓ Loaded stylesheet: {theme} ({mode})")
        except FileNotFoundError:
            print(f"✗ Stylesheet not found: {qss_path}")
            print(f"  Run: cd styling && python generate_qss.py --theme {theme} --mode {mode}")

    def setup_pages(self):
        """Initialize page handlers with database manager."""
        try:
            if GraphPage and self.db_manager:
                self.graph_page_handler = GraphPage(self, self.db_manager)
                logger.info("GraphPage handler initialized")
            else:
                logger.warning("GraphPage handler not initialized (missing GraphPage or db_manager)")
            
            if DatabasePage and self.db_manager:
                self.database_page_handler = DatabasePage(self, self.db_manager)
                # Load fixture filter options after initialization
                self.database_page_handler.load_fixture_filter_options()
                logger.info("DatabasePage handler initialized")
            else:
                self.database_page_handler = None
                logger.warning("DatabasePage handler not initialized (missing DatabasePage or db_manager)")
            
            if ReportsPage and self.db_manager:
                self.reports_page_handler = ReportsPage(self, self.db_manager)
                logger.info("ReportsPage handler initialized")
            else:
                self.reports_page_handler = None
                logger.warning("ReportsPage handler not initialized (missing ReportsPage or db_manager)")
            
            if SearchPage and self.db_manager:
                self.search_page_handler = SearchPage(self, self.db_manager)
                logger.info("SearchPage handler initialized")
            else:
                self.search_page_handler = None
                logger.warning("SearchPage handler not initialized (missing SearchPage or db_manager)")
        except Exception as e:
            logger.error(f"Error setting up pages: {e}")
            print(f"Warning: Could not initialize pages - {e}")

    def setup_connections(self):
        """Connect button signals to slots."""
        # Navigation tabs
        try:
            self.databaseTabButton.clicked.connect(lambda: self.on_tab_change("database"))
            self.graphsTabButton.clicked.connect(lambda: self.on_tab_change("graphs"))
            self.reportsTabButton.clicked.connect(lambda: self.on_tab_change("reports"))
            self.searchTabButton.clicked.connect(lambda: self.on_tab_change("search"))
            self.settingsTabButton.clicked.connect(lambda: self.on_tab_change("settings"))
        except AttributeError as e:
            print(f"Navigation buttons not found: {e}")

        # Action buttons
        try:
            if hasattr(self, 'exportPngButton'):
                self.exportPngButton.clicked.connect(self.on_export_png)
            if hasattr(self, 'exportCsvButton'):
                self.exportCsvButton.clicked.connect(self.on_export_csv)
        except AttributeError as e:
            print(f"Action buttons not found: {e}")

    def on_tab_change(self, tab_name: str):
        """Handle tab navigation."""
        logger.info(f"Switched to: {tab_name}")

        # Update button states
        try:
            self.databaseTabButton.setProperty('class', 'nav-tab')
            self.graphsTabButton.setProperty('class', 'nav-tab')
            self.reportsTabButton.setProperty('class', 'nav-tab')
            self.searchTabButton.setProperty('class', 'nav-tab')
            self.settingsTabButton.setProperty('class', 'nav-tab')

            # Set active tab
            if tab_name == "Database":
                self.databaseTabButton.setProperty('class', 'nav-tab-active')
            elif tab_name == "Graphs":
                self.graphsTabButton.setProperty('class', 'nav-tab-active')
            elif tab_name == "Reports":
                self.reportsTabButton.setProperty('class', 'nav-tab-active')
            elif tab_name == "Search":
                self.searchTabButton.setProperty('class', 'nav-tab-active')
            elif tab_name == "Settings":
                self.settingsTabButton.setProperty('class', 'nav-tab-active')

            # Force style refresh
            for btn in [self.databaseTabButton, self.graphsTabButton,
                        self.reportsTabButton, self.searchTabButton, self.settingsTabButton]:
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                btn.update()

            # This dynamically gets the widget page EXAMPLE: self.settings_page
            target_page = getattr(self, f"{tab_name}_page")

            # Switch to the tab page
            self.main_section_stackedWidget.setCurrentWidget(target_page)


        except AttributeError as e:
            print(f"Error updating tab states: {e}")

    def on_export_png(self):
        """Export graph as PNG."""
        QMessageBox.information(self, "Export PNG", "Export PNG functionality will be implemented here.")
        print("Export PNG clicked")

    def on_export_csv(self):
        """Export data as CSV."""
        QMessageBox.information(self, "Export CSV", "Export CSV functionality will be implemented here.")
        print("Export CSV clicked")

    def change_theme(self, theme: str, mode: str = "dark"):
        """Change the current theme."""
        self.load_stylesheet(theme, mode)

    def closeEvent(self, event):
        """Clean up when window closes."""
        try:
            # Clean up page handlers
            if self.graph_page_handler:
                self.graph_page_handler.cleanup()
            
            if hasattr(self, 'database_page_handler') and self.database_page_handler:
                self.database_page_handler.cleanup()
            
            if hasattr(self, 'reports_page_handler') and self.reports_page_handler:
                self.reports_page_handler.cleanup()
            
            if hasattr(self, 'search_page_handler') and self.search_page_handler:
                self.search_page_handler.cleanup()

            # Close database manager
            if self.db_manager:
                self.db_manager.close()
                logger.info("Database manager closed")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        event.accept()