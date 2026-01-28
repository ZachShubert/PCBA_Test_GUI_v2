"""
Graph Page - Full implementation with GraphModeManager integration.

Supports:
- Standard mode: Scatter, Line, Histogram
- Comparison mode: Manufacturer, Difference, Test Fixture, PIA/PMT Batch
- Relational mode: Measurement vs Measurement (Scatter, Line)
- Plot Overlay mode: Overlaid line plots for waveform data
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from collections import defaultdict
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QMessageBox, QProgressDialog,
    QFileDialog, QApplication, QCompleter, QMenu
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QDate, QTimer, QPointF
from PyQt6.QtGui import QAction, QActionGroup
import pyqtgraph as pg

from src.database import DatabaseManager, PMT, TestLog, PCBABoard
from src.database.database_worker import DatabaseQueryWorker
from src.gui.graph_generation.graph_config import GraphConfig, GraphType, ColorScheme, ComparisonMode

logger = logging.getLogger(__name__)


class GraphMode:
    """Graph mode constants."""
    STANDARD = "Standard Plotting"
    COMPARISON = "Comparison Plotting"
    RELATIONAL = "Relational Plotting"
    PLOT_OVERLAY = "Plot Overlay"


class DisplayType:
    """Display type constants for each mode."""
    # Standard mode
    SCATTER = "Scatter Plot"
    LINE = "Line Plot"
    HISTOGRAM = "Histogram"

    # Comparison mode - visualization types (selected AFTER generating)
    DUMBBELL = "Dumbbell Plot"        # Side-by-side with connecting lines
    CORRELATION = "Correlation Plot"   # X=Compare value, Y=Ours with y=x line
    DIFFERENCE = "Difference Plot"     # Shows difference between values

    # Relational mode (uses SCATTER and LINE)

    # Plot Overlay mode
    OVERLAY = "Overlaid Line Plots"


class CompareBy:
    """What to compare against in Comparison mode (selected BEFORE generating)."""
    MANUFACTURER = "Manufacturer"
    TEST_FIXTURE = "Test Fixture"
    FIRST_LAST = "First vs Last Test"
    PIA_BATCH = "PIA Batch"
    PMT_BATCH = "PMT Batch"


class GraphPage:
    """
    Manages the graph page functionality with multi-mode support.

    Generates and caches multiple plot types for quick switching
    without re-querying the database.
    """

    def __init__(self, main_window, db_manager: DatabaseManager):
        """Initialize graph page with all UI connections."""
        self.main_window = main_window
        self.db = db_manager

        # Get reference to plot placeholder widget from UI
        self.plot_placeholder = main_window.plot1Placeholder

        # Create layout for plot placeholder
        self.plot_layout = QVBoxLayout(self.plot_placeholder)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)

        # Current plot widget
        self.current_plot = None

        # Cached plots for quick switching
        self.cached_plots: Dict[str, pg.PlotWidget] = {}

        # Current mode and state
        self.current_mode = GraphMode.STANDARD
        self.current_measurements = None
        self.current_x_measurements = None  # For relational/comparison modes

        # Workers
        self.query_worker = None
        self.query_thread = None
        self.x_query_worker = None
        self.x_query_thread = None

        # Progress dialog
        self.progress_dialog = None

        # Connect UI controls
        self.setup_connections()

        # Load initial data from database
        self.load_database_data()

        # Store current graph generator for post-generation modifications
        self.current_generator = None

        # Connect post-generation option controls
        self.setup_post_generation_connections()

        logger.info("GraphPage initialized with multi-mode support")

    def setup_connections(self):
        """Connect GUI controls to handlers."""
        try:
            mw = self.main_window

            # Generate graph button
            if hasattr(mw, 'generate_graph_button'):
                mw.generate_graph_button.clicked.connect(self.on_generate_graph)
                logger.info("Connected generate_graph_button")

            # Graph mode combo box (Standard/Comparison/Relational/Plot Overlay)
            if hasattr(mw, 'graph_type_comboBox'):
                mw.graph_type_comboBox.currentTextChanged.connect(self.on_graph_mode_changed)
                logger.info("Connected graph_type_comboBox")

            # Display type combo box (Scatter/Line/Histogram etc.)
            if hasattr(mw, 'display_graph_type_comboBox'):
                mw.display_graph_type_comboBox.currentTextChanged.connect(self.on_display_type_changed)
                logger.info("Connected display_graph_type_comboBox")

            # Y-axis measurement change (for updating paired X measurements)
            if hasattr(mw, 'graphs_y_axis_values_combobox'):
                mw.graphs_y_axis_values_combobox.currentTextChanged.connect(self.on_y_axis_changed)
                logger.info("Connected graphs_y_axis_values_combobox")

            logger.info("GraphPage connections established")

        except AttributeError as e:
            logger.error(f"Error setting up connections: {e}")

    def load_database_data(self):
        """Load all data from database to populate UI elements."""
        try:
            logger.info("Loading database data into UI...")

            # Load measurements for Y-axis
            self.load_y_axis_measurements()

            # Load X-axis options based on current mode
            self.load_x_axis_options()

            # Load grouping options
            self.load_grouping_options()

            # Load pairing options (for comparison mode)
            self.load_pairing_options()

            # Load filter options
            self.load_filter_options()

            # Setup initial display type options
            self.update_display_type_options()

            logger.info("Database data loaded successfully")

        except Exception as e:
            logger.error(f"Error loading database data: {e}")

    def load_y_axis_measurements(self):
        """Load measurements into Y-axis combo box based on current mode."""
        try:
            mw = self.main_window
            if not hasattr(mw, 'graphs_y_axis_values_combobox'):
                return

            mw.graphs_y_axis_values_combobox.clear()

            if self.current_mode == GraphMode.PLOT_OVERLAY:
                # Only show plot-type measurements
                spec_names = self.db.queries.specs.get_plot_spec_names()
                if spec_names:
                    mw.graphs_y_axis_values_combobox.addItems(sorted(spec_names))
                else:
                    mw.graphs_y_axis_values_combobox.addItem("No plot measurements available")
                    mw.graphs_y_axis_values_combobox.setEnabled(False)
            else:
                # Show all measurements
                spec_names = self.db.queries.specs.get_all_spec_names()
                mw.graphs_y_axis_values_combobox.addItems(sorted(spec_names))
                mw.graphs_y_axis_values_combobox.setEnabled(True)

            logger.info(f"Loaded {len(spec_names)} measurements into Y-axis")
        except Exception as e:
            logger.error(f"Error loading Y-axis measurements: {e}")

    def load_x_axis_options(self):
        """Load X-axis options based on current mode."""
        try:
            mw = self.main_window
            if not hasattr(mw, 'graphs_x_axis_values_combobox'):
                return

            mw.graphs_x_axis_values_combobox.clear()

            if self.current_mode == GraphMode.STANDARD:
                # Standard mode: grouping/ordering options
                x_axis_options = [
                    "Index (Default)",
                    "PIA Serial Number",
                    "PIA Part Number",
                    "PMT Serial Number",
                    "PMT Batch Number",
                    "PMT Generation",
                    "Test Fixture",
                    "Test Date"
                ]
                mw.graphs_x_axis_values_combobox.addItems(x_axis_options)
                mw.graphs_x_axis_values_combobox.setEnabled(True)

            elif self.current_mode == GraphMode.COMPARISON:
                # Comparison mode: SAME as standard - grouping/ordering options
                # (We compare our data vs manufacturer data, not two different specs)
                x_axis_options = [
                    "Index (Default)",
                    "PIA Serial Number",
                    "PIA Part Number",
                    "PMT Serial Number",
                    "PMT Batch Number",
                    "PMT Generation",
                    "Test Fixture",
                    "Test Date"
                ]
                mw.graphs_x_axis_values_combobox.addItems(x_axis_options)
                mw.graphs_x_axis_values_combobox.setEnabled(True)

            elif self.current_mode == GraphMode.RELATIONAL:
                # Relational mode: Show OTHER measurements to compare against Y
                self.load_paired_x_measurements()

            elif self.current_mode == GraphMode.PLOT_OVERLAY:
                # Plot overlay: X-axis not relevant
                mw.graphs_x_axis_values_combobox.addItem("N/A (Plot Data)")
                mw.graphs_x_axis_values_combobox.setEnabled(False)

            logger.info("Loaded X-axis options")
        except Exception as e:
            logger.error(f"Error loading X-axis options: {e}")

    def load_paired_x_measurements(self):
        """Load X-axis measurements that are paired with the selected Y measurement."""
        try:
            mw = self.main_window
            if not hasattr(mw, 'graphs_x_axis_values_combobox'):
                return

            mw.graphs_x_axis_values_combobox.clear()

            # Get selected Y-axis measurement
            y_measurement = None
            if hasattr(mw, 'graphs_y_axis_values_combobox'):
                y_measurement = mw.graphs_y_axis_values_combobox.currentText()

            if not y_measurement:
                spec_names = self.db.queries.specs.get_all_spec_names()
                mw.graphs_x_axis_values_combobox.addItems(sorted(spec_names))
                return

            # Get paired measurements
            paired_specs = self.db.queries.specs.get_paired_spec_names(y_measurement)

            if paired_specs:
                # Remove Y measurement from options
                paired_specs = [s for s in paired_specs if s != y_measurement]
                mw.graphs_x_axis_values_combobox.addItems(sorted(paired_specs))
                mw.graphs_x_axis_values_combobox.setEnabled(True)
            else:
                mw.graphs_x_axis_values_combobox.addItem("No paired measurements")
                mw.graphs_x_axis_values_combobox.setEnabled(False)

        except Exception as e:
            logger.error(f"Error loading paired X measurements: {e}")

    def load_grouping_options(self):
        """Load options for grouping data."""
        try:
            mw = self.main_window
            if hasattr(mw, 'graphs_group_values_by_combobox'):
                grouping_options = [
                    "None",
                    "PIA Serial Number",
                    "PIA Part Number",
                    "PMT Serial Number",
                    "PMT Batch Number",
                    "PMT Generation",
                    "Test Fixture",
                    "Test Date"
                ]
                mw.graphs_group_values_by_combobox.clear()
                mw.graphs_group_values_by_combobox.addItems(grouping_options)
        except Exception as e:
            logger.error(f"Error loading grouping options: {e}")

    def load_pairing_options(self):
        """Load pairing options for comparison mode."""
        try:
            mw = self.main_window
            if hasattr(mw, 'graphs_pair_values_by_combobox'):
                pairing_options = [
                    "PIA Serial Number",
                    "PMT Serial Number"
                ]
                mw.graphs_pair_values_by_combobox.clear()
                mw.graphs_pair_values_by_combobox.addItems(pairing_options)
        except Exception as e:
            logger.error(f"Error loading pairing options: {e}")

    def load_filter_options(self):
        """Load all filter combo boxes with database values."""
        try:
            mw = self.main_window

            pia_serials = self.db.queries.pias.get_all_serial_numbers()
            pia_parts = self.db.queries.pias.get_all_part_numbers()
            pmt_serials = self.db.queries.pmts.get_all_serial_numbers()
            pmt_batches = self.get_all_pmt_batches()

            self.populate_filter_combo(mw, 'graphs_filter_pia_serial_num_comboBox', pia_serials)
            self.populate_filter_combo(mw, 'graphs_filter_pia_part_num_comboBox', pia_parts)
            self.populate_filter_combo(mw, 'graphs_filter_pmt_serial_num_comboBox', pmt_serials)
            self.populate_filter_combo(mw, 'graphs_filter_pmt_batch_id_comboBox', pmt_batches)

        except Exception as e:
            logger.error(f"Error loading filter options: {e}")

    def get_all_pmt_batches(self) -> List[str]:
        """Get all unique PMT batches from database."""
        try:
            with self.db.session_scope() as session:
                from sqlalchemy import distinct
                batches = session.query(distinct(PMT.batch_number)).all()
                return sorted([b[0] for b in batches if b[0]])
        except Exception as e:
            logger.error(f"Error getting PMT batches: {e}")
            return []

    def populate_filter_combo(self, main_window, combo_name: str, items: List[str]):
        """Populate a filter combo box with items."""
        if hasattr(main_window, combo_name):
            combo = getattr(main_window, combo_name)
            combo.clear()
            combo.addItem("All")
            combo.addItems(items)

    def update_display_type_options(self):
        """Update display type combo box based on current mode."""
        mw = self.main_window
        if not hasattr(mw, 'display_graph_type_comboBox'):
            return

        mw.display_graph_type_comboBox.blockSignals(True)
        mw.display_graph_type_comboBox.clear()

        if self.current_mode == GraphMode.STANDARD:
            mw.display_graph_type_comboBox.addItems([
                DisplayType.SCATTER,
                DisplayType.LINE,
                DisplayType.HISTOGRAM
            ])
        elif self.current_mode == GraphMode.COMPARISON:
            # Comparison mode: visualization types (Dumbbell, Correlation, Difference)
            mw.display_graph_type_comboBox.addItems([
                DisplayType.DUMBBELL,
                DisplayType.CORRELATION,
                DisplayType.DIFFERENCE
            ])
        elif self.current_mode == GraphMode.RELATIONAL:
            mw.display_graph_type_comboBox.addItems([
                DisplayType.SCATTER,
                DisplayType.LINE
            ])
        elif self.current_mode == GraphMode.PLOT_OVERLAY:
            mw.display_graph_type_comboBox.addItems([
                DisplayType.OVERLAY
            ])

        mw.display_graph_type_comboBox.blockSignals(False)
        logger.info(f"Updated display types for mode: {self.current_mode}")

    # ==================== Event Handlers ====================

    def on_graph_mode_changed(self, mode_text: str):
        """Handle graph mode selection change."""
        logger.info(f"Graph mode changed to: {mode_text}")

        # Update current mode
        if "Standard" in mode_text:
            self.current_mode = GraphMode.STANDARD
        elif "Comparison" in mode_text:
            self.current_mode = GraphMode.COMPARISON
        elif "Relational" in mode_text:
            self.current_mode = GraphMode.RELATIONAL
        elif "Overlay" in mode_text or "Plot" in mode_text:
            self.current_mode = GraphMode.PLOT_OVERLAY

        # Clear cached plots when mode changes
        self.clear_cached_plots()

        # Update UI
        self.update_display_type_options()
        self.load_y_axis_measurements()
        self.load_x_axis_options()

        # Show/hide comparison controls
        self.update_comparison_controls_visibility()

    def on_display_type_changed(self, display_type: str):
        """Handle display type change - switch to cached plot."""
        if not display_type:
            return

        logger.info(f"Display type changed to: {display_type}")

        # Check if we have a cached plot for this type
        if display_type in self.cached_plots:
            self.display_plot(self.cached_plots[display_type])
        else:
            logger.warning(f"No cached plot for: {display_type}")

    def on_y_axis_changed(self, y_measurement: str):
        """Handle Y-axis measurement change."""
        if self.current_mode == GraphMode.RELATIONAL:
            # Update X-axis with paired measurements
            self.load_paired_x_measurements()

    def update_comparison_controls_visibility(self):
        """Show/hide and populate comparison-specific controls."""
        mw = self.main_window
        is_comparison = self.current_mode == GraphMode.COMPARISON

        # The pair_values_by combobox becomes the "Compare By" selector in comparison mode
        if hasattr(mw, 'graphs_pair_values_by_combobox'):
            mw.graphs_pair_values_by_combobox.setVisible(is_comparison)

            if is_comparison:
                # Populate with comparison options
                mw.graphs_pair_values_by_combobox.clear()
                mw.graphs_pair_values_by_combobox.addItems([
                    CompareBy.MANUFACTURER,
                    CompareBy.TEST_FIXTURE,
                    CompareBy.FIRST_LAST,
                    CompareBy.PIA_BATCH,
                    CompareBy.PMT_BATCH
                ])

        if hasattr(mw, 'graphs_pair_by_label'):
            mw.graphs_pair_by_label.setVisible(is_comparison)
            if is_comparison:
                mw.graphs_pair_by_label.setText("Compare By:")

    # ==================== Graph Generation ====================

    def on_generate_graph(self):
        """Handle generate graph button click."""
        mw = self.main_window

        # Get Y-axis measurement
        y_measurement = ""
        if hasattr(mw, 'graphs_y_axis_values_combobox'):
            y_measurement = mw.graphs_y_axis_values_combobox.currentText()

        if not y_measurement or y_measurement == "No plot measurements available":
            self.show_error("Error", "Please select a Y-axis measurement")
            return

        logger.info(f"Generating graph for Y-axis: {y_measurement}")

        # Show progress dialog
        self.progress_dialog = QProgressDialog(
            "Querying database...", "Cancel", 0, 100, self.main_window
        )
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        # Build filters
        filters = self.build_query_filters()

        # Clear cached plots
        self.clear_cached_plots()

        # Query based on mode
        if self.current_mode == GraphMode.RELATIONAL:
            # Relational mode: Need to query both Y and X measurements
            x_measurement = ""
            if hasattr(mw, 'graphs_x_axis_values_combobox'):
                x_measurement = mw.graphs_x_axis_values_combobox.currentText()

            if not x_measurement or x_measurement in ["N/A (Plot Data)", "No paired measurements"]:
                self.show_error("Error", "Please select an X-axis measurement")
                if self.progress_dialog:
                    self.progress_dialog.close()
                return

            self.query_both_measurements(y_measurement, x_measurement, filters)
        else:
            # Standard, Comparison, or Plot Overlay - only Y measurement needed
            # For Comparison mode, manufacturer data is fetched separately
            self.query_database(y_measurement, filters)

    def build_query_filters(self) -> dict:
        """Build filter dictionary from UI elements."""
        mw = self.main_window
        filters = {}

        # Full test only
        filters['full_test_only'] = False
        if hasattr(mw, 'graphs_full_test_only_checkbox'):
            filters['full_test_only'] = mw.graphs_full_test_only_checkbox.isChecked()

        # Test selection (all/first/last)
        filters['test_selection'] = 'all'
        if hasattr(mw, 'graph_all_tests_button') and mw.graph_all_tests_button.isChecked():
            filters['test_selection'] = 'all'
        elif hasattr(mw, 'graph_first_tests_button') and mw.graph_first_tests_button.isChecked():
            filters['test_selection'] = 'first'
        elif hasattr(mw, 'graph_last_tests_button') and mw.graph_last_tests_button.isChecked():
            filters['test_selection'] = 'last'

        # Date filter
        if hasattr(mw, 'graphs_filter_date_edit'):
            filter_date = mw.graphs_filter_date_edit.date()
            filters['from_date'] = datetime(filter_date.year(), filter_date.month(), filter_date.day())
        else:
            filters['from_date'] = datetime(2000, 1, 1)

        # Serial/part filters
        for attr, key in [
            ('graphs_filter_pia_serial_num_comboBox', 'pia_serial'),
            ('graphs_filter_pia_part_num_comboBox', 'pia_part'),
            ('graphs_filter_pmt_serial_num_comboBox', 'pmt_serial'),
            ('graphs_filter_pmt_batch_id_comboBox', 'pmt_batch')
        ]:
            if hasattr(mw, attr):
                value = getattr(mw, attr).currentText()
                if value and value != "All":
                    filters[key] = value

        logger.info(f"Built query filters: {filters}")
        return filters

    def query_database(self, spec_name: str, filters: dict):
        """Query database for single measurement."""
        try:
            # Build date filter tuple if from_date is provided
            date_filter = None
            if filters.get('from_date'):
                from_date = filters['from_date']
                # End date is today or far future
                end_date = datetime.now()
                date_filter = (from_date, end_date)

            stmt = self.db.queries.specs.get_statement(
                spec_name=spec_name,
                include_only_full_tests=filters.get('full_test_only', False),
                filter_by_pia_serial_number=filters.get('pia_serial'),
                filter_by_pia_part_number=filters.get('pia_part'),
                filter_by_pmt=filters.get('pmt_serial'),
                filter_by_pmt_batch=filters.get('pmt_batch'),
                filter_by_dates=date_filter
            )

            self.query_worker = DatabaseQueryWorker(stmt)
            self.query_thread = QThread()
            self.query_worker.moveToThread(self.query_thread)

            self.query_thread.started.connect(self.query_worker.run)
            self.query_worker.init_progress.connect(self.on_query_progress_init)
            self.query_worker.increment_progress.connect(self.on_query_progress_increment)
            self.query_worker.finished.connect(lambda m: self.on_query_finished(m, filters))
            self.query_worker.error.connect(self.on_query_error)

            if self.progress_dialog:
                self.progress_dialog.canceled.connect(self.query_worker.cancel)

            self.query_thread.start()
            logger.info(f"Started database query for: {spec_name}")

        except Exception as e:
            logger.exception("Error querying database")
            self.cleanup_query_thread()
            if self.progress_dialog:
                self.progress_dialog.close()
            self.show_error("Error", f"Database query failed: {e}")

    def query_both_measurements(self, y_spec: str, x_spec: str, filters: dict):
        """Query database for both Y and X measurements (comparison/relational mode)."""
        try:
            # Store X spec for later
            self._pending_x_spec = x_spec
            self._pending_filters = filters

            # Build date filter tuple if from_date is provided
            date_filter = None
            if filters.get('from_date'):
                from_date = filters['from_date']
                end_date = datetime.now()
                date_filter = (from_date, end_date)

            # Query Y measurement first
            stmt = self.db.queries.specs.get_statement(
                spec_name=y_spec,
                include_only_full_tests=filters.get('full_test_only', False),
                filter_by_pia_serial_number=filters.get('pia_serial'),
                filter_by_pia_part_number=filters.get('pia_part'),
                filter_by_pmt=filters.get('pmt_serial'),
                filter_by_pmt_batch=filters.get('pmt_batch'),
                filter_by_dates=date_filter
            )

            self.query_worker = DatabaseQueryWorker(stmt)
            self.query_thread = QThread()
            self.query_worker.moveToThread(self.query_thread)

            self.query_thread.started.connect(self.query_worker.run)
            self.query_worker.init_progress.connect(self.on_query_progress_init)
            self.query_worker.increment_progress.connect(self.on_query_progress_increment)
            self.query_worker.finished.connect(self.on_y_query_finished)
            self.query_worker.error.connect(self.on_query_error)

            if self.progress_dialog:
                self.progress_dialog.canceled.connect(self.query_worker.cancel)

            self.query_thread.start()
            logger.info(f"Started Y-axis query for: {y_spec}")

        except Exception as e:
            logger.exception("Error querying database")
            self.cleanup_query_thread()
            if self.progress_dialog:
                self.progress_dialog.close()
            self.show_error("Error", f"Database query failed: {e}")

    def on_y_query_finished(self, y_measurements: list):
        """Handle Y measurement query completion, then query X."""
        logger.info(f"Y-axis query finished: {len(y_measurements)} measurements")
        self.cleanup_query_thread()

        if not y_measurements:
            if self.progress_dialog:
                self.progress_dialog.close()
            self.show_info("No Data", "No Y-axis measurements found.")
            return

        # Store Y measurements
        self._pending_y_measurements = y_measurements

        # Now query X measurement
        if self.progress_dialog:
            self.progress_dialog.setLabelText("Querying X-axis data...")

        try:
            # Build date filter tuple
            date_filter = None
            if self._pending_filters.get('from_date'):
                from_date = self._pending_filters['from_date']
                end_date = datetime.now()
                date_filter = (from_date, end_date)

            stmt = self.db.queries.specs.get_statement(
                spec_name=self._pending_x_spec,
                include_only_full_tests=self._pending_filters.get('full_test_only', False),
                filter_by_pia_serial_number=self._pending_filters.get('pia_serial'),
                filter_by_pia_part_number=self._pending_filters.get('pia_part'),
                filter_by_pmt=self._pending_filters.get('pmt_serial'),
                filter_by_pmt_batch=self._pending_filters.get('pmt_batch'),
                filter_by_dates=date_filter
            )

            self.x_query_worker = DatabaseQueryWorker(stmt)
            self.x_query_thread = QThread()
            self.x_query_worker.moveToThread(self.x_query_thread)

            self.x_query_thread.started.connect(self.x_query_worker.run)
            self.x_query_worker.finished.connect(self.on_x_query_finished)
            self.x_query_worker.error.connect(self.on_query_error)

            self.x_query_thread.start()

        except Exception as e:
            logger.exception("Error querying X measurement")
            if self.progress_dialog:
                self.progress_dialog.close()
            self.show_error("Error", f"X-axis query failed: {e}")

    def on_x_query_finished(self, x_measurements: list):
        """Handle X measurement query completion."""
        logger.info(f"X-axis query finished: {len(x_measurements)} measurements")

        # Cleanup X query thread
        if self.x_query_thread:
            self.x_query_thread.quit()
            self.x_query_thread.wait()
            self.x_query_thread = None
            self.x_query_worker = None

        if not x_measurements:
            if self.progress_dialog:
                self.progress_dialog.close()
            self.show_info("No Data", "No X-axis measurements found.")
            return

        # Apply test selection filter
        y_measurements = self.apply_test_selection(self._pending_y_measurements, self._pending_filters)
        x_measurements = self.apply_test_selection(x_measurements, self._pending_filters)

        # Generate graph with both measurements
        self.generate_graphs(y_measurements, x_measurements)

    def on_query_progress_init(self, total: int):
        """Initialize progress bar."""
        if self.progress_dialog:
            self.progress_dialog.setMaximum(total)
            self.progress_dialog.setValue(0)

    def on_query_progress_increment(self):
        """Increment progress bar."""
        if self.progress_dialog:
            self.progress_dialog.setValue(self.progress_dialog.value() + 1)

    def on_query_finished(self, measurements: list, filters: dict):
        """Handle query completion for single measurement mode."""
        logger.info(f"Query finished: {len(measurements)} measurements")
        self.cleanup_query_thread()

        if not measurements:
            if self.progress_dialog:
                self.progress_dialog.close()
            self.show_info("No Data", "No measurements found.")
            return

        measurements = self.apply_test_selection(measurements, filters)

        if not measurements:
            if self.progress_dialog:
                self.progress_dialog.close()
            self.show_info("No Data", "No measurements after filtering.")
            return

        self.generate_graphs(measurements)

    def on_query_error(self, error_msg: str):
        """Handle query error."""
        logger.error(f"Query error: {error_msg}")
        self.cleanup_query_thread()
        if self.progress_dialog:
            self.progress_dialog.close()
        self.show_error("Database Error", f"Query failed: {error_msg}")

    def apply_test_selection(self, measurements: list, filters: dict) -> list:
        """Apply first/last test selection filter."""
        test_selection = filters.get('test_selection', 'all')

        if test_selection == 'all':
            return measurements

        device_tests = defaultdict(list)
        for m in measurements:
            device_id = self._get_device_id(m)
            if device_id:
                device_tests[device_id].append(m)

        filtered = []
        for device_id, device_measurements in device_tests.items():
            sorted_measurements = sorted(
                device_measurements,
                key=lambda m: m.created_at if m.created_at else datetime.min
            )
            if test_selection == 'first':
                filtered.append(sorted_measurements[0])
            elif test_selection == 'last':
                filtered.append(sorted_measurements[-1])

        logger.info(f"Test selection '{test_selection}': {len(measurements)} -> {len(filtered)}")
        return filtered

    def _get_device_id(self, measurement) -> Optional[str]:
        """Get device identifier from measurement."""
        try:
            if hasattr(measurement, 'sub_test') and measurement.sub_test:
                if hasattr(measurement.sub_test, 'test_log') and measurement.sub_test.test_log:
                    if hasattr(measurement.sub_test.test_log, 'pia_board') and measurement.sub_test.test_log.pia_board:
                        return measurement.sub_test.test_log.pia_board.serial_number
        except:
            pass
        return None

    def cleanup_query_thread(self):
        """Clean up query thread."""
        if self.query_thread:
            self.query_thread.quit()
            self.query_thread.wait()
            self.query_thread = None
            self.query_worker = None

    # ==================== Graph Generation ====================

    def generate_graphs(self, y_measurements: list, x_measurements: list = None):
        """Generate all plot types for the current mode."""
        try:
            self.current_measurements = y_measurements
            self.current_x_measurements = x_measurements

            if self.progress_dialog:
                self.progress_dialog.setLabelText("Generating plots...")
            QApplication.processEvents()

            # Clear existing cached plots
            self.clear_cached_plots()

            # Generate plots based on mode
            if self.current_mode == GraphMode.STANDARD:
                self._generate_standard_plots(y_measurements)
            elif self.current_mode == GraphMode.COMPARISON:
                self._generate_comparison_plots(y_measurements, x_measurements)
            elif self.current_mode == GraphMode.RELATIONAL:
                self._generate_relational_plots(y_measurements, x_measurements)
            elif self.current_mode == GraphMode.PLOT_OVERLAY:
                self._generate_overlay_plot(y_measurements)

            # Close progress dialog
            if self.progress_dialog:
                self.progress_dialog.close()

            # Display the first/default plot
            self._display_default_plot()

            # Populate spec line selectors
            if y_measurements:
                self.populate_spec_line_selectors(y_measurements)

            # Update page subtitle
            self.update_page_subtitle()

            logger.info("Graph generation complete")

        except Exception as e:
            logger.exception("Error generating graphs")
            if self.progress_dialog:
                self.progress_dialog.close()
            self.show_error("Error", f"Failed to generate graph: {e}")

    def _generate_standard_plots(self, measurements: list):
        """Generate Scatter, Line, and Histogram plots."""
        from src.gui.graph_generation.graph_generator import MeasurementGraphGenerator

        base_config = self._build_base_config(measurements)

        # Scatter plot
        if self.progress_dialog:
            self.progress_dialog.setLabelText("Generating Scatter Plot...")
        QApplication.processEvents()

        scatter_config = GraphConfig(**{**base_config, 'graph_type': GraphType.SCATTER})
        self.cached_plots[DisplayType.SCATTER] = self._create_plot(scatter_config)

        # Line plot
        if self.progress_dialog:
            self.progress_dialog.setLabelText("Generating Line Plot...")
        QApplication.processEvents()

        line_config = GraphConfig(**{**base_config, 'graph_type': GraphType.LINE})
        self.cached_plots[DisplayType.LINE] = self._create_plot(line_config)

        # Histogram
        if self.progress_dialog:
            self.progress_dialog.setLabelText("Generating Histogram...")
        QApplication.processEvents()

        histogram_config = GraphConfig(**{**base_config, 'graph_type': GraphType.HISTOGRAM})
        self.cached_plots[DisplayType.HISTOGRAM] = self._create_plot(histogram_config)

        logger.info("Generated standard plots: Scatter, Line, Histogram")

    def _generate_comparison_plots(self, y_measurements: list, x_measurements: list = None):
        """
        Generate comparison plots for comparing our measurements vs manufacturer data.

        Creates plot types:
        1. Dumbbell Plot: Side-by-side our data vs comparison (Image 2 style)
        2. Correlation Plot: X=Compare value, Y=Our value with y=x line
        3. Difference Plot: Shows difference between values

        The "Compare By" selection determines what we compare against:
        - Manufacturer: Our data vs manufacturer specs
        - Test Fixture: Compare measurements between fixtures (e.g., Fixture A vs Fixture B)
        - First vs Last: Compare first test vs last test for each device
        - PIA/PMT Batch: Compare between batches

        Supports grouping/coloring by field (test fixture, batch, etc.)
        X-axis ordering follows the X-axis combobox selection.
        """
        mw = self.main_window

        # Get the spec name we're comparing
        spec_name = y_measurements[0].name if y_measurements else None
        if not spec_name:
            logger.warning("No measurement name for comparison")
            return

        # Get "Compare By" selection
        compare_by = CompareBy.MANUFACTURER  # Default
        if hasattr(mw, 'graphs_pair_values_by_combobox'):
            compare_by = mw.graphs_pair_values_by_combobox.currentText()

        # Get X-axis ordering option
        x_axis_field = 'index'  # Default
        x_axis_label = 'Device Index'
        if hasattr(mw, 'graphs_x_axis_values_combobox'):
            x_axis_text = mw.graphs_x_axis_values_combobox.currentText()
            x_axis_mapping = {
                "Index (Default)": ("index", "Device Index"),
                "PIA Serial Number": ("pia_serial", "PIA Serial Number"),
                "PIA Part Number": ("pia_part", "PIA Part Number"),
                "PMT Serial Number": ("pmt_serial", "PMT Serial Number"),
                "PMT Batch Number": ("pmt_batch", "PMT Batch Number"),
                "PMT Generation": ("pmt_generation", "PMT Generation"),
                "Test Fixture": ("test_fixture", "Test Fixture"),
                "Test Date": ("test_date", "Test Date")
            }
            if x_axis_text in x_axis_mapping:
                x_axis_field, x_axis_label = x_axis_mapping[x_axis_text]

        # Get grouping option
        group_by_field = None
        if hasattr(mw, 'graphs_group_values_by_combobox'):
            group_by_text = mw.graphs_group_values_by_combobox.currentText()
            if group_by_text and group_by_text != "None":
                group_mapping = {
                    "PIA Serial Number": "pia_serial",
                    "PIA Part Number": "pia_part",
                    "PMT Serial Number": "pmt_serial",
                    "PMT Batch Number": "pmt_batch",
                    "PMT Generation": "pmt_generation",
                    "Test Fixture": "test_fixture",
                    "Test Date": "test_date"
                }
                group_by_field = group_mapping.get(group_by_text)

        logger.info(f"Generating comparison plots - Compare By: {compare_by}, Group By: {group_by_field}, X-Axis: {x_axis_field}")

        # Get spec limits from our measurements
        lower_limit = None
        upper_limit = None
        y_unit = y_measurements[0].unit if y_measurements else ""
        for m in y_measurements:
            if m.lower_limit is not None:
                lower_limit = m.lower_limit
            if m.upper_limit is not None:
                upper_limit = m.upper_limit
            if lower_limit and upper_limit:
                break

        # Generate paired data based on Compare By selection
        paired_data = None
        compare_label = "Comparison"
        our_label = "Our Measurements"
        other_label = "Comparison"

        if compare_by == CompareBy.MANUFACTURER:
            # Compare against manufacturer data
            manufacturer_data = self._get_manufacturer_data_for_spec(spec_name)
            paired_data = self._pair_with_manufacturer_data(y_measurements, manufacturer_data)
            compare_label = "Manufacturer"
            other_label = "Manufacturer Expected"

        elif compare_by == CompareBy.TEST_FIXTURE:
            # Compare between test fixtures
            paired_data = self._pair_by_test_fixture(y_measurements)
            compare_label = "Test Fixture"
            our_label = "Fixture A"
            other_label = "Fixture B"

        elif compare_by == CompareBy.FIRST_LAST:
            # Compare first vs last test for each device
            paired_data = self._pair_first_last_tests(y_measurements)
            compare_label = "First vs Last"
            our_label = "Last Test"
            other_label = "First Test"

        elif compare_by == CompareBy.PIA_BATCH:
            # Compare between PIA batches
            paired_data = self._pair_by_batch(y_measurements, 'pia')
            compare_label = "PIA Batch"
            our_label = "Batch A"
            other_label = "Batch B"

        elif compare_by == CompareBy.PMT_BATCH:
            # Compare between PMT batches
            paired_data = self._pair_by_batch(y_measurements, 'pmt')
            compare_label = "PMT Batch"
            our_label = "Batch A"
            other_label = "Batch B"

        if not paired_data:
            logger.warning(f"No paired data available for {compare_by} comparison")
            self.show_info("No Data", f"Could not find paired data for {compare_by} comparison.\n\n"
                          f"Make sure you have the required data in your database.")
            return

        # Add grouping info to paired data
        if group_by_field:
            self._add_grouping_to_paired_data(paired_data, group_by_field)

        # Add X-axis ordering info to paired data
        self._add_x_axis_ordering_to_paired_data(paired_data, x_axis_field)

        # 1. Dumbbell Plot (Side-by-side with connecting lines)
        if self.progress_dialog:
            self.progress_dialog.setLabelText("Generating Dumbbell Plot...")
        QApplication.processEvents()

        dumbbell_plot = self._create_dumbbell_plot(
            paired_data,
            title=f"{compare_label} Comparison: {spec_name}",
            y_label=f"{spec_name} ({y_unit})" if y_unit else spec_name,
            x_label=x_axis_label,
            our_label=our_label,
            other_label=other_label,
            lower_limit=lower_limit,
            upper_limit=upper_limit,
            group_by_field=group_by_field,
            x_axis_field=x_axis_field
        )
        if dumbbell_plot:
            self.cached_plots[DisplayType.DUMBBELL] = dumbbell_plot

        # 2. Correlation Plot (X=Other, Y=Ours with y=x line)
        if self.progress_dialog:
            self.progress_dialog.setLabelText("Generating Correlation Plot...")
        QApplication.processEvents()

        correlation_plot = self._create_correlation_plot(
            paired_data,
            title=f"{spec_name} Correlation ({compare_label})",
            x_label=f"{other_label} - {spec_name} ({y_unit})" if y_unit else f"{other_label} - {spec_name}",
            y_label=f"{our_label} - {spec_name} ({y_unit})" if y_unit else f"{our_label} - {spec_name}",
            lower_limit=lower_limit,
            upper_limit=upper_limit,
            group_by_field=group_by_field
        )
        if correlation_plot:
            self.cached_plots[DisplayType.CORRELATION] = correlation_plot

        # 3. Difference Plot
        if self.progress_dialog:
            self.progress_dialog.setLabelText("Generating Difference Plot...")
        QApplication.processEvents()

        diff_plot = self._create_difference_plot_v2(
            paired_data,
            title=f"Difference Plot: {spec_name} ({our_label} - {other_label})",
            y_label=f"Difference ({y_unit})" if y_unit else "Difference",
            x_label=x_axis_label,
            group_by_field=group_by_field,
            x_axis_field=x_axis_field
        )
        if diff_plot:
            self.cached_plots[DisplayType.DIFFERENCE] = diff_plot

        logger.info(f"Generated comparison plots for {compare_by}")

    def _add_grouping_to_paired_data(self, paired_data: list, group_by_field: str):
        """Add grouping information to paired data based on the group_by_field."""
        for pair in paired_data:
            our_m = pair.get('our_measurement')
            if our_m:
                group_value = self._get_group_value(our_m, group_by_field)
                pair['group'] = group_value if group_value else 'Unknown'
            else:
                pair['group'] = 'Unknown'

    def _add_x_axis_ordering_to_paired_data(self, paired_data: list, x_axis_field: str):
        """Add X-axis ordering/label information to paired data based on the field."""
        for pair in paired_data:
            our_m = pair.get('our_measurement')
            if our_m and x_axis_field != 'index':
                x_value = self._get_group_value(our_m, x_axis_field)
                pair['x_axis_value'] = x_value if x_value else pair.get('device_id', 'Unknown')
            else:
                pair['x_axis_value'] = pair.get('device_id', 'Unknown')

    def _get_group_value(self, measurement, group_by_field: str) -> Optional[str]:
        """Extract the group value from a measurement based on the field."""
        try:
            if not hasattr(measurement, 'sub_test') or not measurement.sub_test:
                return None
            if not hasattr(measurement.sub_test, 'test_log') or not measurement.sub_test.test_log:
                return None

            tl = measurement.sub_test.test_log

            if group_by_field == 'pia_serial':
                return tl.pia_board.serial_number if tl.pia_board else None
            elif group_by_field == 'pia_part':
                return tl.pia_board.part_number if tl.pia_board else None
            elif group_by_field == 'pmt_serial':
                return tl.pmt_device.pmt_serial_number if tl.pmt_device else None
            elif group_by_field == 'pmt_batch':
                return tl.pmt_device.batch_number if tl.pmt_device else None
            elif group_by_field == 'pmt_generation':
                return str(tl.pmt_device.generation) if tl.pmt_device and tl.pmt_device.generation else None
            elif group_by_field == 'test_fixture':
                return tl.test_fixture
            elif group_by_field == 'test_date':
                return tl.created_at.strftime('%Y-%m-%d') if tl.created_at else None
        except Exception as e:
            logger.error(f"Error getting group value: {e}")
        return None

    def _get_manufacturer_data_for_spec(self, spec_name: str) -> List[Dict]:
        """
        Get manufacturer data from the manufacturer tables for a given spec name.

        Returns list of dicts with:
            - device_serial: Device serial number
            - measurement: Manufacturer's measurement value
            - manufacturer_name: Name of manufacturer
        """
        try:
            from src.database.database_manufacturer_tables import ManufacturerSpec

            with self.db.session_scope() as session:
                mfr_specs = session.query(ManufacturerSpec).filter(
                    ManufacturerSpec.spec_name == spec_name
                ).all()

                result = []
                for ms in mfr_specs:
                    if ms.device_serial and ms.measurement is not None:
                        result.append({
                            'device_serial': ms.device_serial,
                            'measurement': ms.measurement,
                            'manufacturer_name': ms.manufacturer.name if ms.manufacturer else 'Unknown'
                        })

                logger.info(f"Found {len(result)} manufacturer specs for '{spec_name}'")
                return result

        except Exception as e:
            logger.warning(f"Could not get manufacturer data: {e}")
            return []

    def _pair_with_manufacturer_data(self, our_measurements: list, manufacturer_data: list) -> List[Dict]:
        """
        Pair our measurements with manufacturer data by device serial number.

        Returns list of dicts with:
            - device_id: Device serial number
            - our_value: Our measured value
            - mfr_value: Manufacturer's value
            - our_measurement: Full measurement object
        """
        if not manufacturer_data:
            return []

        # Build lookup by device serial
        mfr_by_serial = {m['device_serial']: m for m in manufacturer_data}

        # Pair with our measurements
        paired = []
        for our_m in our_measurements:
            serial = self._get_device_serial(our_m)
            if serial and serial in mfr_by_serial:
                mfr_data = mfr_by_serial[serial]

                our_value = our_m.measurement if hasattr(our_m, 'measurement') else None
                mfr_value = mfr_data['measurement']

                if our_value is not None and mfr_value is not None:
                    paired.append({
                        'device_id': serial,
                        'our_value': our_value,
                        'mfr_value': mfr_value,
                        'our_measurement': our_m,
                        'manufacturer_name': mfr_data.get('manufacturer_name', 'Manufacturer')
                    })

        logger.info(f"Paired {len(paired)} measurements with manufacturer data")
        return paired

    def _pair_by_test_fixture(self, measurements: list) -> List[Dict]:
        """
        Pair measurements by test fixture for fixture-to-fixture comparison.

        Groups measurements by device, then pairs across different fixtures.
        Returns pairs where we have the same device tested on different fixtures.
        """
        # Group by device and fixture
        device_fixture_data = defaultdict(dict)

        for m in measurements:
            serial = self._get_device_serial(m)
            fixture = self._get_test_fixture(m)

            if serial and fixture and m.measurement is not None:
                if fixture not in device_fixture_data[serial]:
                    device_fixture_data[serial][fixture] = m

        # Find devices tested on multiple fixtures
        paired = []
        for device_id, fixtures in device_fixture_data.items():
            fixture_names = list(fixtures.keys())
            if len(fixture_names) >= 2:
                # Use first two fixtures for comparison
                fixture_a = fixture_names[0]
                fixture_b = fixture_names[1]
                m_a = fixtures[fixture_a]
                m_b = fixtures[fixture_b]

                paired.append({
                    'device_id': device_id,
                    'our_value': m_a.measurement,
                    'mfr_value': m_b.measurement,  # Using mfr_value for consistency
                    'our_measurement': m_a,
                    'other_measurement': m_b,
                    'fixture_a': fixture_a,
                    'fixture_b': fixture_b
                })

        logger.info(f"Paired {len(paired)} measurements by test fixture")
        return paired

    def _pair_first_last_tests(self, measurements: list) -> List[Dict]:
        """
        Pair first and last tests for each device.

        Returns pairs comparing the first test vs the last test for each device.
        """
        # Group by device
        device_measurements = defaultdict(list)
        for m in measurements:
            serial = self._get_device_serial(m)
            if serial and m.measurement is not None:
                device_measurements[serial].append(m)

        paired = []
        for device_id, device_ms in device_measurements.items():
            if len(device_ms) >= 2:
                # Sort by date
                sorted_ms = sorted(
                    device_ms,
                    key=lambda m: m.created_at if m.created_at else datetime.min
                )
                first_m = sorted_ms[0]
                last_m = sorted_ms[-1]

                if first_m.measurement is not None and last_m.measurement is not None:
                    paired.append({
                        'device_id': device_id,
                        'our_value': last_m.measurement,  # Last test is "our" current value
                        'mfr_value': first_m.measurement,  # First test is comparison
                        'our_measurement': last_m,
                        'other_measurement': first_m,
                        'first_date': first_m.created_at,
                        'last_date': last_m.created_at
                    })

        logger.info(f"Paired {len(paired)} first/last test measurements")
        return paired

    def _pair_by_batch(self, measurements: list, batch_type: str) -> List[Dict]:
        """
        Pair measurements by batch for batch-to-batch comparison.

        Args:
            measurements: List of measurements
            batch_type: 'pia' or 'pmt'

        Returns pairs comparing devices from different batches.
        """
        # Group by batch
        batch_measurements = defaultdict(list)

        for m in measurements:
            if batch_type == 'pia':
                batch = self._get_pia_batch(m)
            else:
                batch = self._get_pmt_batch(m)

            if batch and m.measurement is not None:
                batch_measurements[batch].append(m)

        batch_names = list(batch_measurements.keys())

        if len(batch_names) < 2:
            logger.warning(f"Need at least 2 {batch_type} batches for comparison, found {len(batch_names)}")
            return []

        # Compare first two batches with the most data
        sorted_batches = sorted(batch_names, key=lambda b: len(batch_measurements[b]), reverse=True)
        batch_a = sorted_batches[0]
        batch_b = sorted_batches[1]

        # Calculate averages for each batch
        avg_a = sum(m.measurement for m in batch_measurements[batch_a]) / len(batch_measurements[batch_a])
        avg_b = sum(m.measurement for m in batch_measurements[batch_b]) / len(batch_measurements[batch_b])

        # Create paired data - one entry per device in batch A, compared to batch B average
        paired = []
        for m in batch_measurements[batch_a]:
            serial = self._get_device_serial(m)
            paired.append({
                'device_id': serial or f"Device {len(paired)+1}",
                'our_value': m.measurement,
                'mfr_value': avg_b,  # Compare against batch B average
                'our_measurement': m,
                'batch_a': batch_a,
                'batch_b': batch_b,
                'batch_b_avg': avg_b
            })

        logger.info(f"Paired {len(paired)} measurements for {batch_type} batch comparison ({batch_a} vs {batch_b})")
        return paired

    def _get_test_fixture(self, measurement) -> Optional[str]:
        """Get test fixture from measurement."""
        try:
            if hasattr(measurement, 'sub_test') and measurement.sub_test:
                if hasattr(measurement.sub_test, 'test_log') and measurement.sub_test.test_log:
                    return measurement.sub_test.test_log.test_fixture
        except Exception as e:
            logger.error(f"Error getting test fixture: {e}")
        return None

    def _get_pia_batch(self, measurement) -> Optional[str]:
        """Get PIA part number (used as batch) from measurement."""
        try:
            if hasattr(measurement, 'sub_test') and measurement.sub_test:
                if hasattr(measurement.sub_test, 'test_log') and measurement.sub_test.test_log:
                    if measurement.sub_test.test_log.pia_board:
                        return measurement.sub_test.test_log.pia_board.part_number
        except Exception as e:
            logger.error(f"Error getting PIA batch: {e}")
        return None

    def _get_pmt_batch(self, measurement) -> Optional[str]:
        """Get PMT batch number from measurement."""
        try:
            if hasattr(measurement, 'sub_test') and measurement.sub_test:
                if hasattr(measurement.sub_test, 'test_log') and measurement.sub_test.test_log:
                    if measurement.sub_test.test_log.pmt_device:
                        return measurement.sub_test.test_log.pmt_device.batch_number
        except Exception as e:
            logger.error(f"Error getting PMT batch: {e}")
        return None

    def _create_first_last_difference_plot(self, measurements: list, title: str,
                                            y_label: str) -> Optional[pg.PlotWidget]:
        """
        Create difference plot showing (Last test - First test) for each device.
        """
        try:
            # Group measurements by device
            device_measurements = defaultdict(list)
            for m in measurements:
                serial = self._get_device_serial(m)
                if serial:
                    device_measurements[serial].append(m)

            # Calculate first-last differences
            paired_data = []
            for device_id, device_ms in device_measurements.items():
                if len(device_ms) >= 2:
                    # Sort by date
                    sorted_ms = sorted(
                        device_ms,
                        key=lambda m: m.created_at if m.created_at else datetime.min
                    )
                    first_m = sorted_ms[0]
                    last_m = sorted_ms[-1]

                    if first_m.measurement is not None and last_m.measurement is not None:
                        paired_data.append({
                            'device_id': device_id,
                            'first_value': first_m.measurement,
                            'last_value': last_m.measurement,
                            'difference': last_m.measurement - first_m.measurement
                        })

            if not paired_data:
                logger.warning("Not enough data for first/last difference plot")
                return None

            plot_widget = pg.PlotWidget()
            plot_widget.setBackground('#1e1e1e')
            plot_widget.showGrid(x=True, y=True, alpha=0.3)

            # Sort by device ID
            sorted_data = sorted(paired_data, key=lambda p: p['device_id'])

            x_indices = list(range(len(sorted_data)))
            differences = [p['difference'] for p in sorted_data]
            device_ids = [p['device_id'] for p in sorted_data]

            # Color points based on sign (green=positive/improving, red=negative/degrading)
            colors = ['#4CAF50' if d >= 0 else '#FF4444' for d in differences]
            brushes = [pg.mkBrush(c) for c in colors]

            # Create scatter plot
            scatter = pg.ScatterPlotItem(
                x=x_indices, y=differences,
                pen=pg.mkPen('#888888', width=1),
                brush=brushes,
                size=12
            )
            plot_widget.addItem(scatter)

            # Add zero reference line
            zero_line = pg.InfiniteLine(
                pos=0, angle=0,
                pen=pg.mkPen('#FFFFFF', width=2, style=Qt.PenStyle.DashLine),
                label='Zero', labelOpts={'position': 0.05, 'color': '#FFFFFF'}
            )
            plot_widget.addItem(zero_line)

            # Set labels and title
            plot_widget.setTitle(title, color='#e0e0e0')
            plot_widget.setLabel('bottom', 'Device', color='#e0e0e0')
            plot_widget.setLabel('left', y_label, color='#e0e0e0')

            # Set X-axis ticks
            if len(device_ids) <= 30:
                ax = plot_widget.getAxis('bottom')
                ax.setTicks([[(i, device_ids[i][-8:] if len(device_ids[i]) > 8 else device_ids[i])
                             for i in range(len(device_ids))]])

            plot_widget.graph_page = self
            return plot_widget

        except Exception as e:
            logger.error(f"Error creating first/last difference plot: {e}")
            return None

    def _get_device_serial(self, measurement) -> Optional[str]:
        """Get device serial number from measurement."""
        try:
            # For our Spec measurements
            if hasattr(measurement, 'sub_test') and measurement.sub_test:
                if hasattr(measurement.sub_test, 'test_log') and measurement.sub_test.test_log:
                    tl = measurement.sub_test.test_log
                    if hasattr(tl, 'pia_board') and tl.pia_board:
                        return tl.pia_board.serial_number
                    if hasattr(tl, 'pmt_device') and tl.pmt_device:
                        return tl.pmt_device.pmt_serial_number

            # For ManufacturerSpec
            if hasattr(measurement, 'device_serial'):
                return measurement.device_serial

        except Exception as e:
            logger.error(f"Error getting device serial: {e}")
        return None

    def _create_correlation_plot(self, paired_data: list, title: str, x_label: str,
                                  y_label: str, lower_limit: float = None,
                                  upper_limit: float = None,
                                  group_by_field: str = None) -> Optional[pg.PlotWidget]:
        """
        Create correlation plot: X = Comparison value, Y = Our value.

        Like Image 1 - Fixture Correlation plot with y=x reference line.
        Supports grouping/coloring by field.
        Includes all interactive features: tooltips, hover, spec line toggles, etc.
        """
        try:
            plot_widget = pg.PlotWidget()
            plot_widget.setBackground('#1e1e1e')
            plot_widget.showGrid(x=True, y=True, alpha=0.3)

            # Extract data
            x_values = [p['mfr_value'] for p in paired_data]
            y_values = [p['our_value'] for p in paired_data]

            if not x_values:
                return None

            # Create legend FIRST so it captures all items added after
            legend = plot_widget.addLegend()
            legend.setBrush(pg.mkBrush(30, 30, 30, 235))
            legend.setOffset((10, 10))

            # Store paired data for tooltips
            plot_widget.paired_data = paired_data
            plot_widget.plot_type = 'correlation'

            # Color palette for groups
            group_colors = [
                '#2196F3', '#4CAF50', '#FF9800', '#E91E63', '#9C27B0',
                '#00BCD4', '#FFEB3B', '#795548', '#607D8B', '#F44336'
            ]

            # Get unique groups if grouping is enabled
            if group_by_field:
                groups = list(set(p.get('group', 'Unknown') for p in paired_data))
                groups.sort()
                group_to_color = {g: group_colors[i % len(group_colors)] for i, g in enumerate(groups)}

                # Create scatter plots per group for legend
                for group in groups:
                    color = group_to_color[group]
                    # Get data for this group
                    group_x = [p['mfr_value'] for p in paired_data if p.get('group') == group]
                    group_y = [p['our_value'] for p in paired_data if p.get('group') == group]
                    group_indices = [i for i, p in enumerate(paired_data) if p.get('group') == group]

                    scatter = pg.ScatterPlotItem(
                        x=group_x, y=group_y,
                        pen=pg.mkPen(color, width=1),
                        brush=pg.mkBrush(color),
                        size=12,
                        name=group
                    )
                    scatter.paired_indices = group_indices
                    scatter.group = group
                    plot_widget.addItem(scatter)
            else:
                # No grouping - single color
                scatter = pg.ScatterPlotItem(
                    x=x_values, y=y_values,
                    pen=pg.mkPen('#2196F3', width=1),
                    brush=pg.mkBrush('#2196F3'),
                    size=12,
                    name='Measurements'
                )
                scatter.paired_indices = list(range(len(paired_data)))
                plot_widget.addItem(scatter)

            # Add y=x reference line (dashed gray)
            all_values = x_values + y_values
            min_val = min(all_values) * 0.95
            max_val = max(all_values) * 1.05

            ref_line = pg.PlotDataItem(
                x=[min_val, max_val], y=[min_val, max_val],
                pen=pg.mkPen('#888888', width=2, style=Qt.PenStyle.DashLine),
                name='y = x'
            )
            plot_widget.addItem(ref_line)

            # Add spec lines if available (with spec_line attribute for toggling)
            if lower_limit is not None:
                # Horizontal lower limit (for Y-axis / our measurements)
                lower_h = pg.InfiniteLine(
                    pos=lower_limit, angle=0,
                    pen=pg.mkPen('#FFA500', width=2, style=Qt.PenStyle.DashLine),
                    label='Lower Limit', labelOpts={'position': 0.95, 'color': '#FFA500'}
                )
                lower_h.spec_line = True
                lower_h.spec_line_type = 'lower'
                plot_widget.addItem(lower_h)

                # Vertical lower limit (for X-axis / manufacturer)
                lower_v = pg.InfiniteLine(
                    pos=lower_limit, angle=90,
                    pen=pg.mkPen('#FFA500', width=1, style=Qt.PenStyle.DotLine)
                )
                lower_v.spec_line = True
                lower_v.spec_line_type = 'lower'
                plot_widget.addItem(lower_v)

            if upper_limit is not None:
                # Horizontal upper limit
                upper_h = pg.InfiniteLine(
                    pos=upper_limit, angle=0,
                    pen=pg.mkPen('#FF4444', width=2, style=Qt.PenStyle.DashLine),
                    label='Upper Limit', labelOpts={'position': 0.95, 'color': '#FF4444'}
                )
                upper_h.spec_line = True
                upper_h.spec_line_type = 'upper'
                plot_widget.addItem(upper_h)

                # Vertical upper limit
                upper_v = pg.InfiniteLine(
                    pos=upper_limit, angle=90,
                    pen=pg.mkPen('#FF4444', width=1, style=Qt.PenStyle.DotLine)
                )
                upper_v.spec_line = True
                upper_v.spec_line_type = 'upper'
                plot_widget.addItem(upper_v)

            # Set labels and title
            plot_widget.setTitle(title, color='#e0e0e0')
            plot_widget.setLabel('bottom', x_label, color='#e0e0e0')
            plot_widget.setLabel('left', y_label, color='#e0e0e0')

            # Setup interactive features
            self._setup_comparison_plot_interactivity(plot_widget)

            plot_widget.graph_page = self
            return plot_widget

        except Exception as e:
            logger.error(f"Error creating correlation plot: {e}")
            return None

    def _create_dumbbell_plot(self, paired_data: list, title: str,
                               y_label: str, x_label: str = "Device Index",
                               our_label: str = "Our Measurements",
                               other_label: str = "Comparison",
                               lower_limit: float = None,
                               upper_limit: float = None,
                               group_by_field: str = None,
                               x_axis_field: str = 'index') -> Optional[pg.PlotWidget]:
        """
        Create dumbbell plot with side-by-side values connected by lines.

        Shows two sets of values (e.g., ours vs manufacturer, first vs last test)
        with dotted lines connecting paired points.
        Supports grouping/coloring by field with grouping boxes.
        X-axis ordering follows the x_axis_field selection.
        Includes all interactive features: tooltips, hover, spec line toggles, etc.
        """
        try:
            plot_widget = pg.PlotWidget()
            plot_widget.setBackground('#1e1e1e')
            plot_widget.showGrid(x=True, y=True, alpha=0.3)

            if not paired_data:
                return None

            # Create legend FIRST so it captures all items added after
            legend = plot_widget.addLegend()
            legend.setBrush(pg.mkBrush(30, 30, 30, 235))
            legend.setOffset((10, 10))

            # Sort data based on x_axis_field
            if x_axis_field == 'index':
                sorted_data = sorted(paired_data, key=lambda p: p['device_id'])
            else:
                # Sort by x_axis_value, then by device_id for consistency within groups
                sorted_data = sorted(paired_data, key=lambda p: (p.get('x_axis_value', ''), p.get('device_id', '')))

            # Store paired data for tooltips
            plot_widget.paired_data = sorted_data
            plot_widget.plot_type = 'dumbbell'
            plot_widget.our_label = our_label
            plot_widget.other_label = other_label

            # Color palette for groups
            group_colors = [
                '#2196F3', '#4CAF50', '#FF9800', '#E91E63', '#9C27B0',
                '#00BCD4', '#FFEB3B', '#795548', '#607D8B', '#F44336'
            ]

            x_indices = list(range(len(sorted_data)))
            our_values = [p['our_value'] for p in sorted_data]
            other_values = [p['mfr_value'] for p in sorted_data]
            x_tick_labels = [p.get('x_axis_value', p['device_id']) for p in sorted_data]

            # Get unique groups if grouping is enabled
            if group_by_field:
                groups = list(set(p.get('group', 'Unknown') for p in sorted_data))
                groups.sort()
                group_to_color = {g: group_colors[i % len(group_colors)] for i, g in enumerate(groups)}

                # Add grouping boxes FIRST (behind everything)
                self._add_comparison_grouping_boxes(plot_widget, sorted_data, x_indices,
                                                    our_values + other_values, group_to_color)

                # Draw connecting lines
                for i, (our_v, other_v) in enumerate(zip(our_values, other_values)):
                    group = sorted_data[i].get('group', 'Unknown')
                    line_color = group_to_color.get(group, '#666666')

                    line = pg.PlotDataItem(
                        x=[i, i], y=[our_v, other_v],
                        pen=pg.mkPen(line_color, width=1, style=Qt.PenStyle.DotLine)
                    )
                    line.connecting_line = True
                    plot_widget.addItem(line)

                # Create scatter plots per group - COMBINED legend entry
                for group in groups:
                    color = group_to_color[group]

                    # Get indices for this group
                    group_indices = [i for i, p in enumerate(sorted_data) if p.get('group') == group]
                    group_x = [x_indices[i] for i in group_indices]
                    group_our = [our_values[i] for i in group_indices]
                    group_other = [other_values[i] for i in group_indices]

                    # Our measurements for this group - circles (WITH legend entry)
                    our_scatter = pg.ScatterPlotItem(
                        x=group_x, y=group_our,
                        pen=pg.mkPen(color, width=1),
                        brush=pg.mkBrush(color),
                        size=12,
                        symbol='o',
                        name=f"{group}"  # Single combined legend entry
                    )
                    our_scatter.paired_indices = group_indices
                    our_scatter.data_type = 'our'
                    our_scatter.group = group
                    plot_widget.addItem(our_scatter)

                    # Other values for this group - triangles (NO legend entry - combined above)
                    other_scatter = pg.ScatterPlotItem(
                        x=group_x, y=group_other,
                        pen=pg.mkPen(color, width=1),
                        brush=pg.mkBrush(color),
                        size=12,
                        symbol='t'
                        # No 'name' parameter - won't appear in legend
                    )
                    other_scatter.paired_indices = group_indices
                    other_scatter.data_type = 'other'
                    other_scatter.group = group
                    plot_widget.addItem(other_scatter)
            else:
                # No grouping - single color for each series
                # Draw connecting lines
                for i, (our_v, other_v) in enumerate(zip(our_values, other_values)):
                    line = pg.PlotDataItem(
                        x=[i, i], y=[our_v, other_v],
                        pen=pg.mkPen('#666666', width=1, style=Qt.PenStyle.DotLine)
                    )
                    line.connecting_line = True
                    plot_widget.addItem(line)

                # Our measurements - blue circles
                our_scatter = pg.ScatterPlotItem(
                    x=x_indices, y=our_values,
                    pen=pg.mkPen('#2196F3', width=1),
                    brush=pg.mkBrush('#2196F3'),
                    size=12,
                    symbol='o',
                    name=our_label
                )
                our_scatter.paired_indices = list(range(len(sorted_data)))
                our_scatter.data_type = 'our'
                plot_widget.addItem(our_scatter)

                # Other values - green triangles
                other_scatter = pg.ScatterPlotItem(
                    x=x_indices, y=other_values,
                    pen=pg.mkPen('#4CAF50', width=1),
                    brush=pg.mkBrush('#4CAF50'),
                    size=12,
                    symbol='t',
                    name=other_label
                )
                other_scatter.paired_indices = list(range(len(sorted_data)))
                other_scatter.data_type = 'other'
                plot_widget.addItem(other_scatter)

            # Add spec lines with spec_line attribute for toggling
            if lower_limit is not None:
                lower_line = pg.InfiniteLine(
                    pos=lower_limit, angle=0,
                    pen=pg.mkPen('#FFA500', width=2, style=Qt.PenStyle.DashLine),
                    label='Lower Limit', labelOpts={'position': 0.95, 'color': '#FFA500'}
                )
                lower_line.spec_line = True
                lower_line.spec_line_type = 'lower'
                plot_widget.addItem(lower_line)

            if upper_limit is not None:
                upper_line = pg.InfiniteLine(
                    pos=upper_limit, angle=0,
                    pen=pg.mkPen('#FF4444', width=2, style=Qt.PenStyle.DashLine),
                    label='Upper Limit', labelOpts={'position': 0.95, 'color': '#FF4444'}
                )
                upper_line.spec_line = True
                upper_line.spec_line_type = 'upper'
                plot_widget.addItem(upper_line)

            # Set labels and title
            plot_widget.setTitle(title, color='#e0e0e0')
            plot_widget.setLabel('bottom', x_label, color='#e0e0e0')
            plot_widget.setLabel('left', y_label, color='#e0e0e0')

            # Set X-axis ticks based on x_tick_labels (if not too many)
            if len(x_tick_labels) <= 30:
                ax = plot_widget.getAxis('bottom')
                # Truncate long labels
                tick_labels = []
                for i, lbl in enumerate(x_tick_labels):
                    lbl_str = str(lbl) if lbl else str(i)
                    if len(lbl_str) > 10:
                        lbl_str = lbl_str[-10:]  # Show last 10 chars
                    tick_labels.append((i, lbl_str))
                ax.setTicks([tick_labels])

            # Setup interactive features
            self._setup_comparison_plot_interactivity(plot_widget)

            plot_widget.graph_page = self
            return plot_widget

        except Exception as e:
            logger.error(f"Error creating manufacturer comparison plot: {e}")
            return None

    def _create_difference_plot_v2(self, paired_data: list, title: str,
                                    y_label: str, x_label: str = "Device Index",
                                    group_by_field: str = None,
                                    x_axis_field: str = 'index') -> Optional[pg.PlotWidget]:
        """
        Create difference plot showing (Our value - Comparison value) for each device.
        Supports grouping/coloring by field.
        X-axis ordering follows the x_axis_field selection.
        Includes all interactive features: tooltips, hover, etc.
        """
        try:
            plot_widget = pg.PlotWidget()
            plot_widget.setBackground('#1e1e1e')
            plot_widget.showGrid(x=True, y=True, alpha=0.3)

            if not paired_data:
                return None

            # Create legend FIRST so it captures all items added after
            legend = plot_widget.addLegend()
            legend.setBrush(pg.mkBrush(30, 30, 30, 235))
            legend.setOffset((10, 10))

            # Sort data based on x_axis_field
            if x_axis_field == 'index':
                sorted_data = sorted(paired_data, key=lambda p: p['device_id'])
            else:
                sorted_data = sorted(paired_data, key=lambda p: (p.get('x_axis_value', ''), p.get('device_id', '')))

            # Store paired data for tooltips
            plot_widget.paired_data = sorted_data
            plot_widget.plot_type = 'difference'

            x_indices = list(range(len(sorted_data)))
            differences = [p['our_value'] - p['mfr_value'] for p in sorted_data]
            x_tick_labels = [p.get('x_axis_value', p['device_id']) for p in sorted_data]

            # Store differences in paired data for tooltip access
            for i, p in enumerate(sorted_data):
                p['difference'] = differences[i]

            # Color palette for groups
            group_colors = [
                '#2196F3', '#4CAF50', '#FF9800', '#E91E63', '#9C27B0',
                '#00BCD4', '#FFEB3B', '#795548', '#607D8B', '#F44336'
            ]

            if group_by_field:
                # Get unique groups
                groups = list(set(p.get('group', 'Unknown') for p in sorted_data))
                groups.sort()
                group_to_color = {g: group_colors[i % len(group_colors)] for i, g in enumerate(groups)}

                # Add grouping boxes FIRST (behind everything)
                self._add_comparison_grouping_boxes(plot_widget, sorted_data, x_indices,
                                                    differences, group_to_color)

                # Draw connecting lines to zero (behind points)
                for i, diff in enumerate(differences):
                    group = sorted_data[i].get('group', 'Unknown')
                    line_color = group_to_color.get(group, '#666666')

                    line = pg.PlotDataItem(
                        x=[i, i], y=[0, diff],
                        pen=pg.mkPen(line_color, width=1, style=Qt.PenStyle.DotLine)
                    )
                    line.connecting_line = True
                    plot_widget.addItem(line)

                # Create scatter plots per group for legend
                for group in groups:
                    color = group_to_color[group]

                    # Get data for this group
                    group_indices = [i for i, p in enumerate(sorted_data) if p.get('group') == group]
                    group_x = [x_indices[i] for i in group_indices]
                    group_diff = [differences[i] for i in group_indices]

                    scatter = pg.ScatterPlotItem(
                        x=group_x, y=group_diff,
                        pen=pg.mkPen(color, width=1),
                        brush=pg.mkBrush(color),
                        size=12,
                        name=group
                    )
                    scatter.paired_indices = group_indices
                    scatter.group = group
                    plot_widget.addItem(scatter)
            else:
                # Draw connecting lines to zero (behind points)
                # Color based on sign: green for positive, red for negative
                for i, diff in enumerate(differences):
                    line_color = '#4CAF50' if diff >= 0 else '#FF4444'

                    line = pg.PlotDataItem(
                        x=[i, i], y=[0, diff],
                        pen=pg.mkPen(line_color, width=1, style=Qt.PenStyle.DotLine)
                    )
                    line.connecting_line = True
                    plot_widget.addItem(line)

                # Color points based on sign (green=positive, red=negative)
                colors = ['#4CAF50' if d >= 0 else '#FF4444' for d in differences]
                brushes = [pg.mkBrush(c) for c in colors]

                # Create scatter plot
                scatter = pg.ScatterPlotItem(
                    x=x_indices, y=differences,
                    pen=pg.mkPen('#888888', width=1),
                    brush=brushes,
                    size=12
                )
                scatter.paired_indices = list(range(len(sorted_data)))
                plot_widget.addItem(scatter)

            # Add zero reference line
            zero_line = pg.InfiniteLine(
                pos=0, angle=0,
                pen=pg.mkPen('#FFFFFF', width=2, style=Qt.PenStyle.DashLine),
                label='Zero', labelOpts={'position': 0.05, 'color': '#FFFFFF'}
            )
            plot_widget.addItem(zero_line)

            # Set labels and title
            plot_widget.setTitle(title, color='#e0e0e0')
            plot_widget.setLabel('bottom', x_label, color='#e0e0e0')
            plot_widget.setLabel('left', y_label, color='#e0e0e0')

            # Set X-axis ticks based on x_tick_labels (if not too many)
            if len(x_tick_labels) <= 30:
                ax = plot_widget.getAxis('bottom')
                # Truncate long labels
                tick_labels = []
                for i, lbl in enumerate(x_tick_labels):
                    lbl_str = str(lbl) if lbl else str(i)
                    if len(lbl_str) > 10:
                        lbl_str = lbl_str[-10:]  # Show last 10 chars
                    tick_labels.append((i, lbl_str))
                ax.setTicks([tick_labels])

            # Setup interactive features
            self._setup_comparison_plot_interactivity(plot_widget)

            plot_widget.graph_page = self
            return plot_widget

        except Exception as e:
            logger.error(f"Error creating difference plot: {e}")
            return None

    def _add_comparison_grouping_boxes(self, plot_widget: pg.PlotWidget, sorted_data: list,
                                        x_indices: list, all_y_values: list,
                                        group_to_color: dict):
        """
        Add grouping boxes to comparison plots.

        Creates dashed rectangular boxes around each group of points with labels.
        """
        plot_item = plot_widget.getPlotItem()

        if not group_to_color or len(group_to_color) <= 1:
            return

        # Get Y range
        y_min = min(all_y_values)
        y_max = max(all_y_values)
        y_range = y_max - y_min
        y_min_box = y_min - y_range * 0.1
        y_max_box = y_max + y_range * 0.15  # Extra space for label

        # Group indices by group name
        group_indices = defaultdict(list)
        for i, p in enumerate(sorted_data):
            group = p.get('group', 'Unknown')
            group_indices[group].append(i)

        for group_name, indices in group_indices.items():
            if not indices:
                continue

            color = group_to_color.get(group_name, '#888888')

            # Calculate box bounds
            x_min_box = min(indices) - 0.4
            x_max_box = max(indices) + 0.4
            x_center = (x_min_box + x_max_box) / 2

            # Create dashed box using LinearRegionItem or custom path
            # Use a simple approach with lines
            pen = pg.mkPen(color=color, width=1, style=Qt.PenStyle.DashLine)

            # Left vertical line
            left_line = pg.PlotDataItem(
                x=[x_min_box, x_min_box], y=[y_min_box, y_max_box],
                pen=pen
            )
            left_line.grouping_box = True
            plot_item.addItem(left_line)

            # Right vertical line
            right_line = pg.PlotDataItem(
                x=[x_max_box, x_max_box], y=[y_min_box, y_max_box],
                pen=pen
            )
            right_line.grouping_box = True
            plot_item.addItem(right_line)

            # Top horizontal line
            top_line = pg.PlotDataItem(
                x=[x_min_box, x_max_box], y=[y_max_box, y_max_box],
                pen=pen
            )
            top_line.grouping_box = True
            plot_item.addItem(top_line)

            # Bottom horizontal line
            bottom_line = pg.PlotDataItem(
                x=[x_min_box, x_max_box], y=[y_min_box, y_min_box],
                pen=pen
            )
            bottom_line.grouping_box = True
            plot_item.addItem(bottom_line)

            # Add label on top
            label = pg.TextItem(
                text=group_name,
                color=color,
                anchor=(0.5, 1.0)
            )
            label.setPos(x_center, y_max_box)

            # Make label bold
            font = label.textItem.font()
            font.setBold(True)
            font.setPointSize(9)
            label.textItem.setFont(font)

            label.grouping_box_label = True
            plot_item.addItem(label)

    def _setup_comparison_plot_interactivity(self, plot_widget: pg.PlotWidget):
        """
        Setup interactive features for comparison plots.

        Includes:
        - Tooltips on hover/click
        - Hover highlighting
        - Crosshairs
        - Context menu with grid density options
        - Point click handling
        """
        plot_item = plot_widget.getPlotItem()

        # Setup tooltip
        tooltip_label = pg.TextItem(anchor=(0, 1))
        tooltip_label.setColor('#e0e0e0')
        tooltip_label.fill = pg.mkBrush(30, 30, 30, 235)
        tooltip_label.border = pg.mkPen('#606060', width=2)
        tooltip_label.setVisible(False)
        plot_item.addItem(tooltip_label)
        plot_widget.tooltip_label = tooltip_label

        # Setup crosshairs
        v_line = pg.InfiniteLine(angle=90, movable=False)
        h_line = pg.InfiniteLine(angle=0, movable=False)
        plot_item.addItem(v_line, ignoreBounds=True)
        plot_item.addItem(h_line, ignoreBounds=True)

        pen = pg.mkPen(color='#888888', width=1, style=Qt.PenStyle.DashLine)
        v_line.setPen(pen)
        h_line.setPen(pen)
        v_line.setVisible(False)
        h_line.setVisible(False)

        plot_widget.crosshair_v = v_line
        plot_widget.crosshair_h = h_line
        plot_widget.crosshairs_enabled = True

        # Track hover state
        plot_widget.hover_item = None
        plot_widget.hover_idx = None
        plot_widget.original_sizes = {}

        # Mouse move handler for hover and crosshairs
        def on_mouse_moved(pos):
            if isinstance(pos, tuple):
                pos = pos[0]

            # Update crosshairs
            if getattr(plot_widget, 'crosshairs_enabled', True):
                if plot_item.sceneBoundingRect().contains(pos):
                    mouse_point = plot_item.vb.mapSceneToView(pos)
                    v_line.setPos(mouse_point.x())
                    h_line.setPos(mouse_point.y())
                    v_line.setVisible(True)
                    h_line.setVisible(True)
                else:
                    v_line.setVisible(False)
                    h_line.setVisible(False)

            # Handle hover highlighting
            if not plot_item.sceneBoundingRect().contains(pos):
                self._clear_comparison_hover(plot_widget)
                return

            nearest_item, nearest_idx, distance = self._find_comparison_nearest_point(pos, plot_widget)

            if nearest_item is not None and nearest_idx is not None:
                self._apply_comparison_hover(nearest_item, nearest_idx, plot_widget)
            else:
                self._clear_comparison_hover(plot_widget)

        # Mouse click handler for tooltips and context menu
        def on_mouse_clicked(evt):
            pos = evt.scenePos()

            # Right-click handling
            if evt.button() == Qt.MouseButton.RightButton:
                nearest_item, nearest_idx, distance = self._find_comparison_nearest_point(pos, plot_widget)
                if nearest_item is not None:
                    self._show_comparison_point_menu(evt, nearest_item, nearest_idx, plot_widget)
                    return

            # Left-click for tooltip
            if evt.button() == Qt.MouseButton.LeftButton:
                nearest_item, nearest_idx, distance = self._find_comparison_nearest_point(pos, plot_widget)
                if nearest_item is not None and nearest_idx is not None:
                    self._show_comparison_tooltip(nearest_item, nearest_idx, plot_widget)
                else:
                    tooltip_label.setVisible(False)

        # Connect signals
        proxy = pg.SignalProxy(plot_widget.scene().sigMouseMoved, rateLimit=60, slot=on_mouse_moved)
        plot_widget.mouse_proxy = proxy
        plot_widget.scene().sigMouseClicked.connect(on_mouse_clicked)

        # Extend context menu with grid density options
        self._extend_comparison_context_menu(plot_widget)

    def _find_comparison_nearest_point(self, scene_pos, plot_widget, threshold=20):
        """Find nearest scatter point to cursor position."""
        plot_item = plot_widget.getPlotItem()
        nearest_item, nearest_idx, min_distance = None, None, float('inf')

        for item in plot_item.items:
            if isinstance(item, pg.ScatterPlotItem):
                points = item.getData()
                if points is None or len(points[0]) == 0:
                    continue

                x_data, y_data = points

                for i, (x, y) in enumerate(zip(x_data, y_data)):
                    screen_pos = plot_item.vb.mapViewToScene(QPointF(x, y))
                    dist = ((screen_pos.x() - scene_pos.x())**2 +
                           (screen_pos.y() - scene_pos.y())**2)**0.5

                    if dist < threshold and dist < min_distance:
                        min_distance = dist
                        nearest_item = item
                        nearest_idx = i

        return nearest_item, nearest_idx, min_distance

    def _apply_comparison_hover(self, item, idx, plot_widget):
        """Apply hover highlight to a point."""
        # Clear previous hover
        self._clear_comparison_hover(plot_widget)

        # Store original size
        if item not in plot_widget.original_sizes:
            plot_widget.original_sizes[item] = item.opts.get('size', 12)

        # Get current sizes and increase the hovered point
        original_size = plot_widget.original_sizes[item]

        # Create new size array with highlighted point
        x_data, y_data = item.getData()
        sizes = [original_size] * len(x_data)
        sizes[idx] = original_size * 1.5

        item.setSize(sizes)

        plot_widget.hover_item = item
        plot_widget.hover_idx = idx

    def _clear_comparison_hover(self, plot_widget):
        """Clear hover highlight."""
        if plot_widget.hover_item is not None:
            original_size = plot_widget.original_sizes.get(plot_widget.hover_item, 12)
            plot_widget.hover_item.setSize(original_size)
            plot_widget.hover_item = None
            plot_widget.hover_idx = None

    def _show_comparison_tooltip(self, item, idx, plot_widget):
        """Show tooltip for a comparison plot point."""
        tooltip_label = plot_widget.tooltip_label
        paired_data = getattr(plot_widget, 'paired_data', None)
        plot_type = getattr(plot_widget, 'plot_type', 'unknown')

        # Get labels from plot_widget or use defaults
        our_label = getattr(plot_widget, 'our_label', 'Our Value')
        other_label = getattr(plot_widget, 'other_label', 'Comparison')

        if paired_data is None or idx >= len(paired_data):
            return

        pair = paired_data[idx]

        # Build tooltip text based on plot type
        lines = []
        lines.append(f"<b>Device:</b> {pair.get('device_id', 'N/A')}")

        if plot_type == 'correlation':
            lines.append(f"<b>{our_label}:</b> {pair.get('our_value', 0):.4f}")
            lines.append(f"<b>{other_label}:</b> {pair.get('mfr_value', 0):.4f}")
            diff = pair.get('our_value', 0) - pair.get('mfr_value', 0)
            lines.append(f"<b>Difference:</b> {diff:.4f}")
        elif plot_type in ['dumbbell', 'manufacturer_comparison']:
            data_type = getattr(item, 'data_type', 'unknown')
            if data_type == 'our':
                lines.append(f"<b>{our_label}:</b> {pair.get('our_value', 0):.4f}")
            elif data_type in ['other', 'manufacturer']:
                lines.append(f"<b>{other_label}:</b> {pair.get('mfr_value', 0):.4f}")
            lines.append(f"<b>Difference:</b> {pair.get('our_value', 0) - pair.get('mfr_value', 0):.4f}")
        elif plot_type == 'difference':
            lines.append(f"<b>Difference:</b> {pair.get('difference', 0):.4f}")
            lines.append(f"<b>{our_label}:</b> {pair.get('our_value', 0):.4f}")
            lines.append(f"<b>{other_label}:</b> {pair.get('mfr_value', 0):.4f}")

        # Get measurement info if available
        our_m = pair.get('our_measurement')
        if our_m:
            if hasattr(our_m, 'sub_test') and our_m.sub_test:
                if hasattr(our_m.sub_test, 'test_log') and our_m.sub_test.test_log:
                    tl = our_m.sub_test.test_log
                    if tl.test_fixture:
                        lines.append(f"<b>Fixture:</b> {tl.test_fixture}")
                    if tl.created_at:
                        lines.append(f"<b>Date:</b> {tl.created_at.strftime('%Y-%m-%d')}")

        tooltip_text = "<br>".join(lines)
        tooltip_label.setHtml(f"<div style='padding: 5px;'>{tooltip_text}</div>")

        # Position tooltip near the point
        x_data, y_data = item.getData()
        tooltip_label.setPos(x_data[idx], y_data[idx])
        tooltip_label.setVisible(True)

    def _show_comparison_point_menu(self, event, item, idx, plot_widget):
        """Show context menu for a comparison point."""
        paired_data = getattr(plot_widget, 'paired_data', None)
        if paired_data is None or idx >= len(paired_data):
            return

        pair = paired_data[idx]

        menu = QMenu()

        # View test log action
        view_log_action = menu.addAction("View Test Log")

        # Copy values action
        copy_action = menu.addAction("Copy Values")

        # Show at cursor
        action = menu.exec(event.screenPos().toPoint())

        if action == view_log_action:
            our_m = pair.get('our_measurement')
            if our_m and hasattr(our_m, 'sub_test') and our_m.sub_test:
                if hasattr(our_m.sub_test, 'test_log') and our_m.sub_test.test_log:
                    html_content = our_m.sub_test.test_log.html_content
                    if html_content:
                        self.view_test_log_html(html_content)
        elif action == copy_action:
            our_label = getattr(plot_widget, 'our_label', 'Our Value')
            other_label = getattr(plot_widget, 'other_label', 'Comparison')
            text = f"Device: {pair.get('device_id')}\n"
            text += f"{our_label}: {pair.get('our_value', 0):.4f}\n"
            text += f"{other_label}: {pair.get('mfr_value', 0):.4f}\n"
            text += f"Difference: {pair.get('our_value', 0) - pair.get('mfr_value', 0):.4f}"
            QApplication.clipboard().setText(text)

    def _extend_comparison_context_menu(self, plot_widget):
        """Extend the default context menu with grid density options."""
        plot_item = plot_widget.getPlotItem()
        vb = plot_item.vb

        # Get the default ViewBox menu
        default_menu = vb.menu

        # Add separator
        default_menu.addSeparator()

        # Create Grid Density submenu
        grid_density_menu = default_menu.addMenu("Grid Density")

        # X-Axis density
        x_density_menu = grid_density_menu.addMenu("X-Axis")
        for density_name in ['Sparse', 'Normal', 'Dense']:
            action = QAction(density_name, x_density_menu)
            action.triggered.connect(
                lambda checked, d=density_name.lower(): self._set_comparison_grid_density(plot_widget, 'x', d)
            )
            x_density_menu.addAction(action)

        # Y-Axis density
        y_density_menu = grid_density_menu.addMenu("Y-Axis")
        for density_name in ['Sparse', 'Normal', 'Dense']:
            action = QAction(density_name, y_density_menu)
            action.triggered.connect(
                lambda checked, d=density_name.lower(): self._set_comparison_grid_density(plot_widget, 'y', d)
            )
            y_density_menu.addAction(action)

        # Both Axes density
        both_density_menu = grid_density_menu.addMenu("Both Axes")
        for density_name in ['Sparse', 'Normal', 'Dense']:
            action = QAction(density_name, both_density_menu)
            action.triggered.connect(
                lambda checked, d=density_name.lower(): self._set_comparison_grid_density(plot_widget, 'both', d)
            )
            both_density_menu.addAction(action)

    def _set_comparison_grid_density(self, plot_widget, axis: str, density: str):
        """Set grid density for comparison plots."""
        plot_item = plot_widget.getPlotItem()
        x_axis = plot_item.getAxis('bottom')
        y_axis = plot_item.getAxis('left')

        view_range = plot_item.viewRange()
        x_range = abs(view_range[0][1] - view_range[0][0])
        y_range = abs(view_range[1][1] - view_range[1][0])

        if density == 'sparse':
            x_major, y_major = x_range / 3, y_range / 3
        elif density == 'dense':
            x_major, y_major = x_range / 15, y_range / 15
        else:  # normal
            x_major, y_major = None, None

        if axis in ['x', 'both']:
            if x_major:
                x_axis.setTickSpacing(major=x_major, minor=x_major/2)
            else:
                x_axis.setTickSpacing()

        if axis in ['y', 'both']:
            if y_major:
                y_axis.setTickSpacing(major=y_major, minor=y_major/2)
            else:
                y_axis.setTickSpacing()

        plot_widget.update()

    def _setup_relational_plot_interactivity(self, plot_widget: pg.PlotWidget):
        """Setup interactive features for relational plots."""
        plot_item = plot_widget.getPlotItem()

        # Setup tooltip
        tooltip_label = pg.TextItem(anchor=(0, 1))
        tooltip_label.setColor('#e0e0e0')
        tooltip_label.fill = pg.mkBrush(30, 30, 30, 235)
        tooltip_label.border = pg.mkPen('#606060', width=1)
        tooltip_label.setVisible(False)
        plot_item.addItem(tooltip_label)
        plot_widget.tooltip_label = tooltip_label

        # Setup crosshairs
        v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#888888', width=1, style=Qt.PenStyle.DashLine))
        h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('#888888', width=1, style=Qt.PenStyle.DashLine))
        v_line.setVisible(False)
        h_line.setVisible(False)
        plot_item.addItem(v_line, ignoreBounds=True)
        plot_item.addItem(h_line, ignoreBounds=True)
        plot_widget.crosshair_v = v_line
        plot_widget.crosshair_h = h_line

        # Track hover state
        plot_widget.hover_item = None
        plot_widget.hover_idx = None
        plot_widget.original_sizes = {}

        def on_mouse_moved(evt):
            pos = evt[0] if isinstance(evt, tuple) else evt
            if not plot_item.sceneBoundingRect().contains(pos):
                v_line.setVisible(False)
                h_line.setVisible(False)
                self._clear_comparison_hover(plot_widget)
                return

            mouse_point = plot_item.vb.mapSceneToView(pos)
            v_line.setPos(mouse_point.x())
            h_line.setPos(mouse_point.y())
            v_line.setVisible(True)
            h_line.setVisible(True)

            # Hover highlight
            nearest_item, nearest_idx, distance = self._find_comparison_nearest_point(pos, plot_widget)
            if nearest_item is not None and nearest_idx is not None:
                self._apply_comparison_hover(nearest_item, nearest_idx, plot_widget)
            else:
                self._clear_comparison_hover(plot_widget)

        def on_mouse_clicked(evt):
            pos = evt.scenePos()
            if not plot_item.sceneBoundingRect().contains(pos):
                return

            if evt.button() == Qt.MouseButton.LeftButton:
                nearest_item, nearest_idx, distance = self._find_comparison_nearest_point(pos, plot_widget)
                if nearest_item is not None and nearest_idx is not None:
                    self._show_relational_tooltip(nearest_item, nearest_idx, plot_widget)
                else:
                    tooltip_label.setVisible(False)

            elif evt.button() == Qt.MouseButton.RightButton:
                nearest_item, nearest_idx, distance = self._find_comparison_nearest_point(pos, plot_widget)
                if nearest_item is not None:
                    self._show_relational_point_menu(evt, nearest_item, nearest_idx, plot_widget)

        proxy = pg.SignalProxy(plot_widget.scene().sigMouseMoved, rateLimit=60, slot=on_mouse_moved)
        plot_widget.mouse_proxy = proxy
        plot_widget.scene().sigMouseClicked.connect(on_mouse_clicked)

    def _show_relational_tooltip(self, item, idx, plot_widget):
        """Show tooltip for relational plot point."""
        tooltip_label = plot_widget.tooltip_label
        paired_data = getattr(plot_widget, 'paired_data', [])

        # Get the actual data index
        if hasattr(item, 'paired_indices'):
            data_idx = item.paired_indices[idx] if idx < len(item.paired_indices) else idx
        else:
            data_idx = idx

        if data_idx >= len(paired_data):
            return

        pair = paired_data[data_idx]

        # Build tooltip
        lines = []
        lines.append(f"Device: {pair.get('device_id', 'Unknown')}")
        lines.append(f"X Value: {pair.get('x_value', 0):.4f}")
        lines.append(f"Y Value: {pair.get('y_value', 0):.4f}")

        if 'group' in pair:
            lines.append(f"Group: {pair['group']}")

        # Get measurement info
        y_m = pair.get('y_measurement')
        if y_m and hasattr(y_m, 'sub_test') and y_m.sub_test:
            if hasattr(y_m.sub_test, 'test_log') and y_m.sub_test.test_log:
                tl = y_m.sub_test.test_log
                if tl.created_at:
                    lines.append(f"Date: {tl.created_at.strftime('%Y-%m-%d %H:%M')}")

        tooltip_label.setText('\n'.join(lines))

        x_data, y_data = item.getData()
        tooltip_label.setPos(x_data[idx], y_data[idx])
        tooltip_label.setVisible(True)

    def _show_relational_point_menu(self, evt, item, idx, plot_widget):
        """Show context menu for relational plot point."""
        paired_data = getattr(plot_widget, 'paired_data', [])

        if hasattr(item, 'paired_indices'):
            data_idx = item.paired_indices[idx] if idx < len(item.paired_indices) else idx
        else:
            data_idx = idx

        if data_idx >= len(paired_data):
            return

        pair = paired_data[data_idx]

        menu = QMenu()

        # View Test Log
        view_log_action = QAction("View Test Log", menu)
        y_m = pair.get('y_measurement')
        if y_m:
            view_log_action.triggered.connect(lambda: self._view_measurement_test_log(y_m))
        else:
            view_log_action.setEnabled(False)
        menu.addAction(view_log_action)

        menu.addSeparator()

        # Copy Values
        copy_action = QAction("Copy Values", menu)
        copy_action.triggered.connect(lambda: self._copy_relational_values(pair))
        menu.addAction(copy_action)

        menu.exec(evt.screenPos().toPoint())

    def _copy_relational_values(self, pair):
        """Copy relational point values to clipboard."""
        from PyQt6.QtWidgets import QApplication
        text = f"Device: {pair.get('device_id', 'Unknown')}\n"
        text += f"X Value: {pair.get('x_value', 0):.6f}\n"
        text += f"Y Value: {pair.get('y_value', 0):.6f}"
        QApplication.clipboard().setText(text)

    def _setup_overlay_plot_interactivity(self, plot_widget: pg.PlotWidget):
        """Setup interactive features for overlay plots."""
        plot_item = plot_widget.getPlotItem()

        # Setup tooltip
        tooltip_label = pg.TextItem(anchor=(0, 1))
        tooltip_label.setColor('#e0e0e0')
        tooltip_label.fill = pg.mkBrush(30, 30, 30, 235)
        tooltip_label.border = pg.mkPen('#606060', width=1)
        tooltip_label.setVisible(False)
        plot_item.addItem(tooltip_label)
        plot_widget.tooltip_label = tooltip_label

        # Setup crosshairs
        v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#888888', width=1, style=Qt.PenStyle.DashLine))
        h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('#888888', width=1, style=Qt.PenStyle.DashLine))
        v_line.setVisible(False)
        h_line.setVisible(False)
        plot_item.addItem(v_line, ignoreBounds=True)
        plot_item.addItem(h_line, ignoreBounds=True)
        plot_widget.crosshair_v = v_line
        plot_widget.crosshair_h = h_line

        def on_mouse_moved(evt):
            pos = evt[0] if isinstance(evt, tuple) else evt
            if not plot_item.sceneBoundingRect().contains(pos):
                v_line.setVisible(False)
                h_line.setVisible(False)
                return

            mouse_point = plot_item.vb.mapSceneToView(pos)
            v_line.setPos(mouse_point.x())
            h_line.setPos(mouse_point.y())
            v_line.setVisible(True)
            h_line.setVisible(True)

        def on_mouse_clicked(evt):
            pos = evt.scenePos()
            if not plot_item.sceneBoundingRect().contains(pos):
                return

            if evt.button() == Qt.MouseButton.LeftButton:
                mouse_point = plot_item.vb.mapSceneToView(pos)
                self._show_overlay_tooltip(mouse_point, plot_widget)

        proxy = pg.SignalProxy(plot_widget.scene().sigMouseMoved, rateLimit=60, slot=on_mouse_moved)
        plot_widget.mouse_proxy = proxy
        plot_widget.scene().sigMouseClicked.connect(on_mouse_clicked)

    def _show_overlay_tooltip(self, mouse_point, plot_widget):
        """Show tooltip for overlay plot at cursor position."""
        tooltip_label = plot_widget.tooltip_label
        overlay_data = getattr(plot_widget, 'overlay_data', [])

        if not overlay_data:
            return

        x_pos = mouse_point.x()

        # Find values at this X position for each series
        lines = [f"Index: {int(x_pos)}"]

        for series in overlay_data:
            x_data = series.get('x_data', [])
            y_data = series.get('y_data', [])
            label = series.get('label', 'Series')

            # Find nearest X index
            if x_data and y_data:
                idx = int(round(x_pos))
                if 0 <= idx < len(y_data):
                    lines.append(f"{label}: {y_data[idx]:.4f}")

        if len(lines) > 1:
            tooltip_label.setText('\n'.join(lines))
            tooltip_label.setPos(mouse_point.x(), mouse_point.y())
            tooltip_label.setVisible(True)
        else:
            tooltip_label.setVisible(False)

    def _view_measurement_test_log(self, measurement):
        """Navigate to test log for a measurement."""
        try:
            if hasattr(measurement, 'sub_test') and measurement.sub_test:
                if hasattr(measurement.sub_test, 'test_log') and measurement.sub_test.test_log:
                    test_log = measurement.sub_test.test_log
                    if hasattr(self, 'graph_page') and hasattr(self.graph_page, 'main_window'):
                        mw = self.graph_page.main_window
                        if hasattr(mw, 'navigate_to_test_log'):
                            mw.navigate_to_test_log(test_log.id)
                            return
                    elif hasattr(self, 'main_window'):
                        if hasattr(self.main_window, 'navigate_to_test_log'):
                            self.main_window.navigate_to_test_log(test_log.id)
                            return
            logger.warning("Could not navigate to test log")
        except Exception as e:
            logger.error(f"Error viewing test log: {e}")

    def _generate_relational_plots(self, y_measurements: list, x_measurements: list):
        """
        Generate relational Scatter and Line plots with full features.

        Compares two different measurements for the same devices.
        Y-axis: First measurement (selected in Y-axis combobox)
        X-axis: Second measurement (selected in X-axis combobox)

        Includes: grouping, legend, tooltips, menu, spec lines
        """
        mw = self.main_window

        paired_data = self._pair_measurements(y_measurements, x_measurements)

        if not paired_data:
            logger.warning("No paired data for relational plots")
            self.show_info("No Data", "Could not pair measurements. Make sure both measurements exist for the same devices.")
            return

        # Get grouping option
        group_by_field = None
        if hasattr(mw, 'graphs_group_values_by_combobox'):
            group_by_text = mw.graphs_group_values_by_combobox.currentText()
            if group_by_text and group_by_text != "None":
                group_mapping = {
                    "PIA Serial Number": "pia_serial",
                    "PIA Part Number": "pia_part",
                    "PMT Serial Number": "pmt_serial",
                    "PMT Batch Number": "pmt_batch",
                    "PMT Generation": "pmt_generation",
                    "Test Fixture": "test_fixture",
                    "Test Date": "test_date"
                }
                group_by_field = group_mapping.get(group_by_text)

        # Add grouping info to paired data
        if group_by_field:
            for pair in paired_data:
                y_m = pair.get('y_measurement')
                if y_m:
                    group_value = self._get_group_value(y_m, group_by_field)
                    pair['group'] = group_value if group_value else 'Unknown'
                else:
                    pair['group'] = 'Unknown'

        # Get spec limits from measurements
        y_lower, y_upper = None, None
        x_lower, x_upper = None, None

        for m in y_measurements:
            if m.lower_limit is not None:
                y_lower = m.lower_limit
            if m.upper_limit is not None:
                y_upper = m.upper_limit

        for m in x_measurements:
            if m.lower_limit is not None:
                x_lower = m.lower_limit
            if m.upper_limit is not None:
                x_upper = m.upper_limit

        # Build config
        y_name = y_measurements[0].name if y_measurements else "Y"
        y_unit = y_measurements[0].unit if y_measurements else ""
        x_name = x_measurements[0].name if x_measurements else "X"
        x_unit = x_measurements[0].unit if x_measurements else ""

        config = {
            'title': f"{y_name} vs {x_name}",
            'y_label': f"{y_name} ({y_unit})" if y_unit else y_name,
            'x_label': f"{x_name} ({x_unit})" if x_unit else x_name,
            'y_lower': y_lower,
            'y_upper': y_upper,
            'x_lower': x_lower,
            'x_upper': x_upper,
            'group_by_field': group_by_field
        }

        # Relational Scatter
        if self.progress_dialog:
            self.progress_dialog.setLabelText("Generating Relational Scatter Plot...")
        QApplication.processEvents()

        scatter_plot = self._create_relational_plot(paired_data, config, GraphType.SCATTER)
        if scatter_plot:
            self.cached_plots[DisplayType.SCATTER] = scatter_plot

        # Relational Line
        if self.progress_dialog:
            self.progress_dialog.setLabelText("Generating Relational Line Plot...")
        QApplication.processEvents()

        line_plot = self._create_relational_plot(paired_data, config, GraphType.LINE)
        if line_plot:
            self.cached_plots[DisplayType.LINE] = line_plot

        logger.info("Generated relational plots: Scatter, Line")

    def _generate_overlay_plot(self, measurements: list):
        """
        Generate overlaid line plot for plot-type measurements.

        Includes: legend, tooltips, spec lines, interactivity
        """
        if self.progress_dialog:
            self.progress_dialog.setLabelText("Generating Overlay Plot...")
        QApplication.processEvents()

        mw = self.main_window

        # Create plot widget
        plot_widget = pg.PlotWidget()
        plot_widget.setBackground('#1e1e1e')
        plot_widget.showGrid(x=True, y=True, alpha=0.3)

        # Create legend FIRST
        legend = plot_widget.addLegend()
        legend.setBrush(pg.mkBrush(30, 30, 30, 235))
        legend.setOffset((10, 10))

        # Color palette
        colors = ['#2196F3', '#4CAF50', '#FF9800', '#E91E63', '#9C27B0',
                  '#00BCD4', '#FFEB3B', '#795548', '#607D8B', '#F44336']
        color_idx = 0

        # Store plot data for tooltips
        plot_widget.overlay_data = []

        # Get spec limits
        lower_limit = None
        upper_limit = None
        y_unit = ""

        for measurement in measurements:
            if hasattr(measurement, 'lower_limit') and measurement.lower_limit is not None:
                lower_limit = measurement.lower_limit
            if hasattr(measurement, 'upper_limit') and measurement.upper_limit is not None:
                upper_limit = measurement.upper_limit
            if hasattr(measurement, 'unit') and measurement.unit:
                y_unit = measurement.unit

        for measurement in measurements:
            # Try to get plot_data from the measurement
            plot_data = None
            if hasattr(measurement, 'plot_data') and measurement.plot_data:
                plot_data = measurement.plot_data
            elif hasattr(measurement, 'get_plot_data'):
                plot_data = measurement.get_plot_data()

            if plot_data:
                # Handle different plot_data formats
                if isinstance(plot_data, dict):
                    # Format: {'x': [...], 'y': [...], 'label': '...'}
                    x_data = plot_data.get('x', list(range(len(plot_data.get('y', [])))))
                    y_data = plot_data.get('y', [])
                    label = plot_data.get('label', measurement.name if hasattr(measurement, 'name') else f"Series {color_idx}")

                    if y_data:
                        color = colors[color_idx % len(colors)]
                        pen = pg.mkPen(color=color, width=2)
                        line = plot_widget.plot(x_data, y_data, pen=pen, name=label)

                        # Store for tooltips
                        plot_widget.overlay_data.append({
                            'x_data': x_data,
                            'y_data': y_data,
                            'label': label,
                            'measurement': measurement,
                            'color': color
                        })
                        color_idx += 1

                elif isinstance(plot_data, list):
                    # Format: list of y values or list of dicts
                    if plot_data and isinstance(plot_data[0], (int, float)):
                        # Simple list of y values
                        x_data = list(range(len(plot_data)))
                        y_data = plot_data
                        label = measurement.name if hasattr(measurement, 'name') else f"Series {color_idx}"

                        color = colors[color_idx % len(colors)]
                        pen = pg.mkPen(color=color, width=2)
                        line = plot_widget.plot(x_data, y_data, pen=pen, name=label)

                        plot_widget.overlay_data.append({
                            'x_data': x_data,
                            'y_data': y_data,
                            'label': label,
                            'measurement': measurement,
                            'color': color
                        })
                        color_idx += 1
                    else:
                        # List of series dicts
                        for series in plot_data:
                            if isinstance(series, dict):
                                x_data = series.get('x', list(range(len(series.get('y', [])))))
                                y_data = series.get('y', [])
                                label = series.get('label', f"Series {color_idx}")

                                if y_data:
                                    color = colors[color_idx % len(colors)]
                                    pen = pg.mkPen(color=color, width=2)
                                    line = plot_widget.plot(x_data, y_data, pen=pen, name=label)

                                    plot_widget.overlay_data.append({
                                        'x_data': x_data,
                                        'y_data': y_data,
                                        'label': label,
                                        'measurement': measurement,
                                        'color': color
                                    })
                                    color_idx += 1

        # Add spec lines (horizontal)
        if lower_limit is not None:
            lower_line = pg.InfiniteLine(
                pos=lower_limit, angle=0,
                pen=pg.mkPen('#FFA500', width=2, style=Qt.PenStyle.DashLine),
                label=f'Lower: {lower_limit:.3f}',
                labelOpts={'position': 0.05, 'color': '#FFA500'}
            )
            lower_line.spec_line = True
            lower_line.spec_line_type = 'lower'
            plot_widget.addItem(lower_line)

        if upper_limit is not None:
            upper_line = pg.InfiniteLine(
                pos=upper_limit, angle=0,
                pen=pg.mkPen('#FF4444', width=2, style=Qt.PenStyle.DashLine),
                label=f'Upper: {upper_limit:.3f}',
                labelOpts={'position': 0.05, 'color': '#FF4444'}
            )
            upper_line.spec_line = True
            upper_line.spec_line_type = 'upper'
            plot_widget.addItem(upper_line)

        # Set labels
        title = f"Plot Overlay: {measurements[0].name}" if measurements else "Plot Overlay"
        plot_widget.setTitle(title, color='#e0e0e0')
        plot_widget.setLabel('left', f"Value ({y_unit})" if y_unit else "Value", color='#e0e0e0')
        plot_widget.setLabel('bottom', 'Index', color='#e0e0e0')

        # Setup interactivity for overlay plot
        self._setup_overlay_plot_interactivity(plot_widget)

        plot_widget.graph_page = self
        plot_widget.plot_type = 'overlay'
        self.cached_plots[DisplayType.OVERLAY] = plot_widget

        logger.info(f"Generated overlay plot with {color_idx} series")

    def _pair_measurements(self, y_measurements: list, x_measurements: list) -> List[Dict]:
        """Pair Y and X measurements by device serial number."""
        # Build lookup by device ID
        x_by_device = {}
        for m in x_measurements:
            device_id = self._get_device_id(m)
            if device_id:
                # Use test_log_id for exact matching within same test
                test_log_id = None
                if hasattr(m, 'sub_test') and m.sub_test:
                    if hasattr(m.sub_test, 'test_log') and m.sub_test.test_log:
                        test_log_id = m.sub_test.test_log.id

                key = (device_id, test_log_id) if test_log_id else device_id
                x_by_device[key] = m

        # Pair with Y measurements
        paired = []
        for y_m in y_measurements:
            device_id = self._get_device_id(y_m)
            if device_id:
                test_log_id = None
                if hasattr(y_m, 'sub_test') and y_m.sub_test:
                    if hasattr(y_m.sub_test, 'test_log') and y_m.sub_test.test_log:
                        test_log_id = y_m.sub_test.test_log.id

                key = (device_id, test_log_id) if test_log_id else device_id
                x_m = x_by_device.get(key)

                if x_m:
                    paired.append({
                        'device_id': device_id,
                        'y_measurement': y_m,
                        'x_measurement': x_m,
                        'y_value': y_m.measurement,
                        'x_value': x_m.measurement
                    })

        logger.info(f"Paired {len(paired)} measurements from {len(y_measurements)} Y and {len(x_measurements)} X")
        return paired

    def _create_plot(self, config: GraphConfig) -> Optional[pg.PlotWidget]:
        """Create a single plot from config."""
        try:
            from src.gui.graph_generation.graph_generator import MeasurementGraphGenerator

            generator = MeasurementGraphGenerator(config)
            generator.prepare_data()
            plot_widget = generator.create_plot_widget()
            generator.plot_data(plot_widget)
            generator.apply_styling(plot_widget)
            generator.setup_interactivity(plot_widget)

            plot_widget.graph_page = self
            return plot_widget
        except Exception as e:
            logger.error(f"Error creating plot: {e}")
            return None

    def _create_relational_plot(self, paired_data: list, config: dict, graph_type: GraphType) -> Optional[pg.PlotWidget]:
        """
        Create a relational plot (Y vs X measurement) with full features.

        Includes: grouping, legend, tooltips, menu, spec lines
        """
        try:
            plot_widget = pg.PlotWidget()
            plot_widget.setBackground('#1e1e1e')
            plot_widget.showGrid(x=True, y=True, alpha=0.3)

            # Filter valid pairs
            valid_pairs = [p for p in paired_data if p['x_value'] is not None and p['y_value'] is not None]

            if not valid_pairs:
                return None

            # Create legend FIRST
            legend = plot_widget.addLegend()
            legend.setBrush(pg.mkBrush(30, 30, 30, 235))
            legend.setOffset((10, 10))

            # Store data for tooltips
            plot_widget.paired_data = valid_pairs
            plot_widget.plot_type = 'relational_scatter' if graph_type == GraphType.SCATTER else 'relational_line'

            # Color palette for groups
            group_colors = [
                '#2196F3', '#4CAF50', '#FF9800', '#E91E63', '#9C27B0',
                '#00BCD4', '#FFEB3B', '#795548', '#607D8B', '#F44336'
            ]

            group_by_field = config.get('group_by_field')

            if group_by_field:
                # Get unique groups
                groups = list(set(p.get('group', 'Unknown') for p in valid_pairs))
                groups.sort()
                group_to_color = {g: group_colors[i % len(group_colors)] for i, g in enumerate(groups)}

                if graph_type == GraphType.SCATTER:
                    # Create scatter per group
                    for group in groups:
                        color = group_to_color[group]
                        group_pairs = [p for p in valid_pairs if p.get('group') == group]
                        x_vals = [p['x_value'] for p in group_pairs]
                        y_vals = [p['y_value'] for p in group_pairs]

                        scatter = pg.ScatterPlotItem(
                            x=x_vals, y=y_vals,
                            pen=pg.mkPen(color, width=1),
                            brush=pg.mkBrush(color),
                            size=10,
                            name=group
                        )
                        # Store indices for tooltips
                        scatter.paired_indices = [i for i, p in enumerate(valid_pairs) if p.get('group') == group]
                        scatter.group = group
                        plot_widget.addItem(scatter)
                else:
                    # Create lines per group
                    for group in groups:
                        color = group_to_color[group]
                        group_pairs = [p for p in valid_pairs if p.get('group') == group]

                        # Sort by X for proper line
                        sorted_pairs = sorted(group_pairs, key=lambda p: p['x_value'])
                        x_vals = [p['x_value'] for p in sorted_pairs]
                        y_vals = [p['y_value'] for p in sorted_pairs]

                        line = pg.PlotDataItem(
                            x=x_vals, y=y_vals,
                            pen=pg.mkPen(color, width=2),
                            name=group
                        )
                        plot_widget.addItem(line)
            else:
                # No grouping - single color
                x_values = [p['x_value'] for p in valid_pairs]
                y_values = [p['y_value'] for p in valid_pairs]

                if graph_type == GraphType.SCATTER:
                    scatter = pg.ScatterPlotItem(
                        x=x_values, y=y_values,
                        pen=pg.mkPen('#2196F3', width=1),
                        brush=pg.mkBrush('#2196F3'),
                        size=10,
                        name='Data'
                    )
                    scatter.paired_indices = list(range(len(valid_pairs)))
                    plot_widget.addItem(scatter)
                else:
                    # Sort by X for proper line
                    sorted_pairs = sorted(zip(x_values, y_values), key=lambda p: p[0])
                    x_sorted = [p[0] for p in sorted_pairs]
                    y_sorted = [p[1] for p in sorted_pairs]

                    line = pg.PlotDataItem(
                        x=x_sorted, y=y_sorted,
                        pen=pg.mkPen('#2196F3', width=2),
                        name='Data'
                    )
                    plot_widget.addItem(line)

            # Add y=x reference line
            all_vals = [p['x_value'] for p in valid_pairs] + [p['y_value'] for p in valid_pairs]
            min_val = min(all_vals) * 0.95
            max_val = max(all_vals) * 1.05

            ref_line = pg.PlotDataItem(
                x=[min_val, max_val], y=[min_val, max_val],
                pen=pg.mkPen('#888888', width=2, style=Qt.PenStyle.DashLine),
                name='y = x'
            )
            plot_widget.addItem(ref_line)

            # Add spec lines
            y_lower = config.get('y_lower')
            y_upper = config.get('y_upper')
            x_lower = config.get('x_lower')
            x_upper = config.get('x_upper')

            if y_lower is not None:
                line = pg.InfiniteLine(pos=y_lower, angle=0,
                    pen=pg.mkPen('#FFA500', width=2, style=Qt.PenStyle.DashLine),
                    label=f'Y Lower: {y_lower:.3f}', labelOpts={'position': 0.05, 'color': '#FFA500'})
                line.spec_line = True
                line.spec_line_type = 'lower'
                plot_widget.addItem(line)

            if y_upper is not None:
                line = pg.InfiniteLine(pos=y_upper, angle=0,
                    pen=pg.mkPen('#FF4444', width=2, style=Qt.PenStyle.DashLine),
                    label=f'Y Upper: {y_upper:.3f}', labelOpts={'position': 0.05, 'color': '#FF4444'})
                line.spec_line = True
                line.spec_line_type = 'upper'
                plot_widget.addItem(line)

            if x_lower is not None:
                line = pg.InfiniteLine(pos=x_lower, angle=90,
                    pen=pg.mkPen('#FFA500', width=1, style=Qt.PenStyle.DotLine))
                line.spec_line = True
                plot_widget.addItem(line)

            if x_upper is not None:
                line = pg.InfiniteLine(pos=x_upper, angle=90,
                    pen=pg.mkPen('#FF4444', width=1, style=Qt.PenStyle.DotLine))
                line.spec_line = True
                plot_widget.addItem(line)

            # Set labels and title
            plot_widget.setTitle(config.get('title', 'Relational Plot'), color='#e0e0e0')
            plot_widget.setLabel('left', config.get('y_label', 'Y'), color='#e0e0e0')
            plot_widget.setLabel('bottom', config.get('x_label', 'X'), color='#e0e0e0')

            # Setup interactivity
            self._setup_relational_plot_interactivity(plot_widget)

            plot_widget.graph_page = self
            return plot_widget
        except Exception as e:
            logger.error(f"Error creating relational plot: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _build_base_config(self, measurements: list) -> dict:
        """Build base configuration from UI settings."""
        mw = self.main_window

        title = measurements[0].name if measurements else "Graph"
        x_label = "Test Index"
        y_label = f"{measurements[0].name} ({measurements[0].unit})" if measurements else "Value"

        if hasattr(mw, 'graphs_title_lineEdit') and mw.graphs_title_lineEdit.text():
            title = mw.graphs_title_lineEdit.text()
        if hasattr(mw, 'graphs_x_label_lineEdit') and mw.graphs_x_label_lineEdit.text():
            x_label = mw.graphs_x_label_lineEdit.text()
        if hasattr(mw, 'graphs_y_label_lineEdit') and mw.graphs_y_label_lineEdit.text():
            y_label = mw.graphs_y_label_lineEdit.text()

        group_by_field = None
        enable_grouping_boxes = False
        if hasattr(mw, 'graphs_group_values_by_combobox'):
            group_by_text = mw.graphs_group_values_by_combobox.currentText()
            if group_by_text and group_by_text != "None":
                group_mapping = {
                    "PIA Serial Number": "pia_serial",
                    "PIA Part Number": "pia_part",
                    "PMT Serial Number": "pmt_serial",
                    "PMT Batch Number": "pmt_batch",
                    "PMT Generation": "pmt_generation",
                    "Test Fixture": "test_fixture",
                    "Test Date": "test_date"
                }
                group_by_field = group_mapping.get(group_by_text)
                if hasattr(mw, 'show_box_groupings_pushButton'):
                    enable_grouping_boxes = mw.show_box_groupings_pushButton.isChecked()

        return {
            'measurements': measurements,
            'color_scheme': ColorScheme.DARK_NORMAL,
            'comparison_mode': ComparisonMode.NONE,
            'group_by_field': group_by_field,
            'enable_grouping_boxes': enable_grouping_boxes,
            'x_axis_use_indices': True,
            'enable_tooltips': True,
            'enable_hover_highlight': True,
            'enable_point_deletion': True,
            'show_spec_lines': True,
            'show_legend': True,
            'auto_overlay_plots': True,
            'legend_bg_opacity': 255,
            'title': title,
            'x_label': x_label,
            'y_label': y_label,
            'point_info_callback': self.get_point_info
        }

    def _display_default_plot(self):
        """Display the first/default plot type."""
        mw = self.main_window

        if hasattr(mw, 'display_graph_type_comboBox') and mw.display_graph_type_comboBox.count() > 0:
            first_type = mw.display_graph_type_comboBox.currentText()
            if first_type in self.cached_plots:
                self.display_plot(self.cached_plots[first_type])

    def display_plot(self, plot_widget: pg.PlotWidget):
        """Display a plot widget in the placeholder."""
        # Remove old plot
        if self.current_plot:
            self.plot_layout.removeWidget(self.current_plot)
            self.current_plot.setParent(None)
            # Don't delete - it might be cached

        # Add new plot
        self.current_plot = plot_widget
        plot_widget.setParent(self.plot_placeholder)
        self.plot_layout.addWidget(plot_widget)

        plot_widget.setVisible(True)
        plot_widget.show()
        plot_widget.update()

        self.plot_layout.activate()
        self.plot_placeholder.update()

        logger.info("Plot displayed")

    def clear_cached_plots(self):
        """Clear all cached plots."""
        for key, plot in self.cached_plots.items():
            if plot and plot != self.current_plot:
                plot.deleteLater()
        self.cached_plots = {}

    # ==================== Post-Generation Controls ====================

    def setup_post_generation_connections(self):
        """Connect post-generation option controls."""
        try:
            mw = self.main_window

            if hasattr(mw, 'enable_spec_lines_pushButton'):
                mw.enable_spec_lines_pushButton.setChecked(True)
                mw.enable_spec_lines_pushButton.toggled.connect(self.on_spec_lines_toggled)

            if hasattr(mw, 'lower_spec_line_combobox'):
                mw.lower_spec_line_combobox.currentIndexChanged.connect(self.on_spec_line_changed)

            if hasattr(mw, 'upper_spec_line_combobox'):
                mw.upper_spec_line_combobox.currentIndexChanged.connect(self.on_spec_line_changed)

            if hasattr(mw, 'enable_cross_hairs_pushButton'):
                mw.enable_cross_hairs_pushButton.setChecked(True)
                mw.enable_cross_hairs_pushButton.toggled.connect(self.on_crosshairs_toggled)

            if hasattr(mw, 'show_box_groupings_pushButton'):
                mw.show_box_groupings_pushButton.setChecked(True)
                mw.show_box_groupings_pushButton.toggled.connect(self.on_box_groupings_toggled)

            if hasattr(mw, 'show_box_grouping_names_pushButton'):
                mw.show_box_grouping_names_pushButton.setChecked(True)
                mw.show_box_grouping_names_pushButton.toggled.connect(self.on_box_grouping_names_toggled)

            if hasattr(mw, 'show_legend_pushButton'):
                mw.show_legend_pushButton.setChecked(True)
                mw.show_legend_pushButton.toggled.connect(self.on_legend_toggled)

            logger.info("Post-generation connections established")

        except Exception as e:
            logger.error(f"Error setting up post-generation connections: {e}")

    def populate_spec_line_selectors(self, measurements: list):
        """Populate spec line combo boxes."""
        try:
            if not measurements:
                return

            mw = self.main_window
            lower_limits = set()
            upper_limits = set()

            for m in measurements:
                if m.lower_limit is not None:
                    lower_limits.add(float(m.lower_limit))
                if m.upper_limit is not None:
                    upper_limits.add(float(m.upper_limit))

            if hasattr(mw, 'lower_spec_line_combobox'):
                mw.lower_spec_line_combobox.clear()
                for limit in sorted(lower_limits):
                    mw.lower_spec_line_combobox.addItem(f"{limit:.4f}", limit)

            if hasattr(mw, 'upper_spec_line_combobox'):
                mw.upper_spec_line_combobox.clear()
                for limit in sorted(upper_limits):
                    mw.upper_spec_line_combobox.addItem(f"{limit:.4f}", limit)

            logger.info(f"Found {len(lower_limits)} lower, {len(upper_limits)} upper limits")

        except Exception as e:
            logger.error(f"Error populating spec line selectors: {e}")

    def on_spec_lines_toggled(self, checked: bool):
        """Toggle spec lines visibility."""
        if not self.current_plot:
            return

        plot_item = self.current_plot.getPlotItem()

        # Iterate over all items in the plot
        for item in plot_item.items[:]:  # Use slice copy to avoid iteration issues
            if hasattr(item, 'spec_line') and item.spec_line:
                item.setVisible(checked)

        logger.info(f"Spec lines {'shown' if checked else 'hidden'}")

    def on_spec_line_changed(self, index):
        """Handle spec line value change."""
        pass  # TODO: Update spec line position

    def on_crosshairs_toggled(self, checked: bool):
        """Toggle crosshairs."""
        if not self.current_plot:
            return

        self.current_plot.crosshairs_enabled = checked

        if hasattr(self.current_plot, 'crosshair_v'):
            if not checked:
                self.current_plot.crosshair_v.setVisible(False)
                self.current_plot.crosshair_h.setVisible(False)

        logger.info(f"Crosshairs {'enabled' if checked else 'disabled'}")

    def on_box_groupings_toggled(self, checked: bool):
        """Toggle box groupings visibility."""
        if not self.current_plot:
            return

        plot_item = self.current_plot.getPlotItem()

        for item in plot_item.items[:]:
            if hasattr(item, 'grouping_box') and item.grouping_box:
                item.setVisible(checked)

        logger.info(f"Box groupings {'shown' if checked else 'hidden'}")

    def on_box_grouping_names_toggled(self, checked: bool):
        """Toggle box grouping names visibility."""
        if not self.current_plot:
            return

        plot_item = self.current_plot.getPlotItem()

        for item in plot_item.items[:]:
            if hasattr(item, 'grouping_box_label') and item.grouping_box_label:
                item.setVisible(checked)

        logger.info(f"Box grouping names {'shown' if checked else 'hidden'}")

    def on_legend_toggled(self, checked: bool):
        """Toggle legend visibility."""
        if not self.current_plot:
            return

        plot_item = self.current_plot.getPlotItem()

        if plot_item.legend:
            plot_item.legend.setVisible(checked)

        logger.info(f"Legend {'shown' if checked else 'hidden'}")

    def update_page_subtitle(self):
        """Update the page subtitle."""
        try:
            mw = self.main_window

            if not hasattr(mw, 'graph_page_subtitle'):
                return

            if not self.current_measurements:
                mw.graph_page_subtitle.setText("No data")
                return

            parts = []
            parts.append(self.current_measurements[0].name)
            parts.append(f"({len(self.current_measurements)} points)")

            if hasattr(mw, 'graphs_group_values_by_combobox'):
                group_by = mw.graphs_group_values_by_combobox.currentText()
                if group_by and group_by != "None":
                    parts.append(f"grouped by {group_by}")

            mw.graph_page_subtitle.setText(" ".join(parts))

        except Exception as e:
            logger.error(f"Error updating subtitle: {e}")

    # ==================== Utilities ====================

    def get_point_info(self, measurement) -> dict:
        """Get info dict for tooltip display."""
        info = {}
        try:
            info['Value'] = f"{measurement.measurement:.4f} {measurement.unit or ''}"

            if hasattr(measurement, 'sub_test') and measurement.sub_test:
                if hasattr(measurement.sub_test, 'test_log') and measurement.sub_test.test_log:
                    tl = measurement.sub_test.test_log
                    if tl.pia_board:
                        info['PIA'] = tl.pia_board.serial_number
                    if tl.pmt_device:
                        info['PMT'] = tl.pmt_device.pmt_serial_number
                    if tl.test_fixture:
                        info['Fixture'] = tl.test_fixture
                    if tl.created_at:
                        info['Date'] = tl.created_at.strftime("%Y-%m-%d %H:%M")
        except Exception as e:
            info['Error'] = str(e)

        return info

    def view_test_log_html(self, html_content: str):
        """Display test log HTML in the search page viewer."""
        try:
            mw = self.main_window

            if hasattr(mw, 'main_section_stackedWidget'):
                stacked_widget = mw.main_section_stackedWidget
                for i in range(stacked_widget.count()):
                    page = stacked_widget.widget(i)
                    if page.objectName() == 'search_page':
                        stacked_widget.setCurrentIndex(i)
                        break

            if hasattr(mw, 'test_log_webViewer'):
                mw.test_log_webViewer.setHtml(html_content)

        except Exception as e:
            logger.error(f"Error viewing test log: {e}")

    def show_error(self, title: str, message: str):
        """Show error message."""
        QMessageBox.critical(self.main_window, title, message)

    def show_info(self, title: str, message: str):
        """Show info message."""
        QMessageBox.information(self.main_window, title, message)

    def cleanup(self):
        """Clean up resources."""
        self.cleanup_query_thread()
        self.clear_cached_plots()
        if self.current_plot:
            self.current_plot.deleteLater()
        logger.info("GraphPage cleaned up")