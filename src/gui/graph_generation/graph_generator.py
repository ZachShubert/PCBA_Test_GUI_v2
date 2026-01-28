"""
Main graph generator for measurement data visualization - V4 Enhanced.

V4 Features:
    1. Click-to-show tooltips (hover only highlights) 
    2. Styled tooltips with solid themed background
    3. Integer X-axis for scatter (no overlap)
    4. Fixed axis margins (10%)
    5. Auto-overlay plot measurements
    6. Full-height colored grouping boxes
    7. Unified context menu
    8. Device-based pairing (PIA/PMT)
    9. Diagonal comparison line
    10. Styled legend
    11. Fixed prepare_data for comparison
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from datetime import datetime
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QAction, QActionGroup
from PyQt6.QtWidgets import QMenu

from .graph_config import (
    GraphConfig, GraphType, ComparisonMode, ColorScheme
)
from .graph_utils import (
    get_color_palette, configure_plot_theme, detect_outliers,
    get_grouped_data, create_dashed_box_item,
    hex_to_rgb, is_dark_mode, calculate_point_size, calculate_line_width,
    calculate_bar_width
)


class MeasurementGraphGenerator:
    """V4-Enhanced measurement graph generator."""

    def __init__(self, config: GraphConfig):
        self.config = config
        self.prepared_data: Dict[str, Any] = {}
        self.color_palette = get_color_palette(config.color_scheme)
        self.deleted_items: set = set()
        self.original_data: Optional[Dict[str, Any]] = None

        # V4: Separate hover (highlight only) and click (show tooltip)
        self.hover_item: Optional[Any] = None
        self.hover_index: Optional[int] = None
        self.selected_item: Optional[Any] = None
        self.selected_index: Optional[int] = None
        self.tooltip_label: Optional[pg.TextItem] = None

        self.point_measurement_map: Dict[Tuple[int, int], Any] = {}

        # Histogram data for tooltips
        self.histogram_data: Optional[Dict[str, Any]] = None

    def prepare_data(self):
        """V4 FEATURE 11: Fixed comparison mode - no grouping."""
        measurements = self.config.measurements

        if not measurements:
            raise ValueError("No measurements provided")

        # V4 FEATURE 11: Skip grouping in comparison mode
        if self.config.comparison_mode != ComparisonMode.NONE:
            groups = {'All Data': measurements}
        elif self.config.group_by_field:
            # Group if group_by_field is set (regardless of enable_grouping_boxes)
            groups = get_grouped_data(measurements, self.config.group_by_field)
            print(f"!!! Grouping by {self.config.group_by_field}, got {len(groups)} groups: {list(groups.keys())}")
        else:
            groups = {'All Data': measurements}

        prepared_groups = {}
        has_plots = False
        total_points = 0
        global_x_index = 0  # Global counter for X-axis ordering

        for group_name, group_measurements in groups.items():
            group_data = self._prepare_group_data(group_measurements, global_x_index)

            if group_data.get('has_plots'):
                has_plots = True

            if group_data.get('x_data'):
                num_points = len(group_data['x_data'])
                total_points += num_points
                global_x_index += num_points + 1  # +1 for gap between groups

            prepared_groups[group_name] = group_data

        self.prepared_data = {
            'groups': prepared_groups,
            'metadata': {
                'x_label': self._generate_x_label(),
                'y_label': self._generate_y_label(),
                'has_plots': has_plots,
                'total_points': total_points
            }
        }

        self.original_data = self._deep_copy_data(self.prepared_data)

    def _prepare_group_data(self, measurements: List[Any], start_x_index: int = 0) -> Dict[str, Any]:
        """Prepare data for a single group."""
        # Separate plot and scalar measurements for V4 FEATURE 5
        plot_measurements = []
        scalar_measurements = []

        for m in measurements:
            if m.has_plot and m.plot_data and self.config.auto_overlay_plots:
                plot_measurements.append(m)
            else:
                scalar_measurements.append(m)

        group_data = {
            'measurements': measurements,
            'plot_measurements': plot_measurements,
            'scalar_measurements': scalar_measurements,
            'has_plots': len(plot_measurements) > 0
        }

        # Extract data based on comparison mode
        if self.config.comparison_mode == ComparisonMode.NONE:
            group_data.update(self._extract_standard_data(measurements, start_x_index))
        elif self.config.comparison_mode == ComparisonMode.SAME_MEASUREMENT:
            group_data.update(self._extract_comparison_same(measurements))
        elif self.config.comparison_mode == ComparisonMode.DIFFERENT_MEASUREMENTS:
            group_data.update(self._extract_comparison_different(measurements))

        return group_data

    def _extract_standard_data(self, measurements: List[Any], start_x_index: int = 0) -> Dict[str, List]:
        """V4 FEATURE 3: Integer X-axis for scatter plots."""
        x_data = []
        y_data = []
        x_labels = []  # V4: Store actual values for tick labels
        measurement_indices = []

        current_x = start_x_index  # Start from global index

        for idx, m in enumerate(measurements):
            if m.has_plot and m.plot_data:
                continue

            # V4 FEATURE 3: Use integer index for X if enabled
            if self.config.x_axis_use_indices and self.config.graph_type == GraphType.SCATTER:
                x_val = current_x  # Use global index
                current_x += 1
                # Store actual value for label
                actual_val = self._get_x_value(m)
                x_labels.append(actual_val)
            else:
                x_val = self._get_x_value(m)
                x_labels.append(x_val)

            y_val = float(m.measurement) if m.measurement is not None else np.nan

            x_data.append(x_val)
            y_data.append(y_val)
            measurement_indices.append(idx)

        # Detect outliers
        is_outlier = [False] * len(y_data)
        if self.config.remove_outliers:
            is_outlier = detect_outliers(y_data)

        return {
            'x_data': x_data,
            'y_data': y_data,
            'x_labels': x_labels,  # V4: For custom tick labels
            'is_outlier': is_outlier,
            'measurement_indices': measurement_indices
        }

    def _extract_comparison_same(self, measurements: List[Any]) -> Dict[str, List]:
        """V4 FEATURE 8: Device-based pairing for comparison."""
        from collections import defaultdict

        target_measurement = self.config.x_axis_measurement
        x_field = self.config.x_axis_field

        # V4 FEATURE 8: Pair by device serial number
        pairing_key_func = self._get_pairing_key

        # Group by device
        device_measurements = defaultdict(list)

        for m in measurements:
            if m.name != target_measurement or m.measurement is None:
                continue

            device_key = pairing_key_func(m)
            if device_key:
                fixture = self._get_field_value(m, x_field)
                device_measurements[device_key].append((fixture, m))

        # Pair measurements from different fixtures
        x_data = []
        y_data = []
        measurement_pairs = []

        for device_key, fixture_measurements in device_measurements.items():
            fixtures_dict = {}
            for fixture, m in fixture_measurements:
                if fixture not in fixtures_dict:
                    fixtures_dict[fixture] = []
                fixtures_dict[fixture].append(m)

            fixtures = sorted(fixtures_dict.keys())
            if len(fixtures) >= 2:
                x_fixture, y_fixture = fixtures[0], fixtures[1]

                # V4 FEATURE 8: Apply pairing strategy
                x_meas = self._apply_pairing_strategy(fixtures_dict[x_fixture])
                y_meas = self._apply_pairing_strategy(fixtures_dict[y_fixture])

                if x_meas and y_meas:
                    x_data.append(float(x_meas.measurement))
                    y_data.append(float(y_meas.measurement))
                    measurement_pairs.append((x_meas, y_meas))

        is_outlier = [False] * len(x_data)
        if self.config.remove_outliers and len(x_data) > 0:
            x_outliers = detect_outliers(x_data)
            y_outliers = detect_outliers(y_data)
            is_outlier = [x or y for x, y in zip(x_outliers, y_outliers)]

        return {
            'x_data': x_data,
            'y_data': y_data,
            'is_outlier': is_outlier,
            'measurement_indices': list(range(len(x_data))),
            'measurement_pairs': measurement_pairs
        }

    def _get_pairing_key(self, measurement: Any) -> Optional[str]:
        """V4 FEATURE 8: Get device serial for pairing."""
        try:
            if self.config.pairing_device == 'pia':
                return measurement.pia.serial_number if measurement.pia else None
            elif self.config.pairing_device == 'pmt':
                return measurement.pmt.pmt_serial_number if measurement.pmt else None
        except AttributeError:
            return None
        return None

    def _apply_pairing_strategy(self, measurements: List[Any]) -> Optional[Any]:
        """V4 FEATURE 8: Apply strategy to select measurement from list."""
        if not measurements:
            return None

        if self.config.pairing_strategy == 'first':
            return measurements[0]
        elif self.config.pairing_strategy == 'last':
            return measurements[-1]
        elif self.config.pairing_strategy == 'best':
            # Return measurement closest to nominal
            best = None
            best_score = float('inf')
            for m in measurements:
                if m.nominal is not None:
                    score = abs(m.measurement - m.nominal)
                    if score < best_score:
                        best_score = score
                        best = m
            return best if best else measurements[-1]

        return measurements[-1]

    def _extract_comparison_different(self, measurements: List[Any]) -> Dict[str, List]:
        """Extract data for different-measurement comparison."""
        x_measurements = {}
        y_measurements = {}

        for m in measurements:
            test_id = m.sub_test.test_id if hasattr(m, 'sub_test') else str(m.created_at)

            if m.name == self.config.x_axis_measurement and m.measurement is not None:
                x_measurements[test_id] = (m, float(m.measurement))
            elif m.name == self.config.y_axis_measurement and m.measurement is not None:
                y_measurements[test_id] = (m, float(m.measurement))

        x_data, y_data, measurement_pairs = [], [], []

        for test_id in x_measurements:
            if test_id in y_measurements:
                x_meas, x_val = x_measurements[test_id]
                y_meas, y_val = y_measurements[test_id]
                x_data.append(x_val)
                y_data.append(y_val)
                measurement_pairs.append((x_meas, y_meas))

        is_outlier = [False] * len(x_data)
        if self.config.remove_outliers:
            x_outliers = detect_outliers(x_data)
            y_outliers = detect_outliers(y_data)
            is_outlier = [x or y for x, y in zip(x_outliers, y_outliers)]

        return {
            'x_data': x_data,
            'y_data': y_data,
            'is_outlier': is_outlier,
            'measurement_indices': list(range(len(x_data))),
            'measurement_pairs': measurement_pairs
        }

    def _get_field_value(self, measurement: Any, field_path: str) -> Any:
        """Extract field value using dot notation."""
        value = measurement
        for attr in field_path.split('.'):
            value = getattr(value, attr, None)
            if value is None:
                break
        return value

    def _get_x_value(self, measurement: Any) -> float:
        """Extract X-axis value from measurement."""
        x_field = self.config.x_axis_field
        value = measurement

        for attr in x_field.split('.'):
            value = getattr(value, attr, None)
            if value is None:
                return 0.0

        if isinstance(value, datetime):
            return value.timestamp()

        return float(value)

    def _generate_x_label(self) -> str:
        """Generate X-axis label."""
        if self.config.x_label:
            return self.config.x_label

        if self.config.comparison_mode == ComparisonMode.SAME_MEASUREMENT:
            return f"{self.config.x_axis_measurement} ({self.config.x_axis_field})"

        if self.config.comparison_mode == ComparisonMode.DIFFERENT_MEASUREMENTS:
            return self.config.x_axis_measurement or "X"

        if self.config.x_axis_field == 'created_at':
            return "Time"

        return self.config.x_axis_field.replace('_', ' ').title()

    def _generate_y_label(self) -> str:
        """Generate Y-axis label."""
        if self.config.y_label:
            return self.config.y_label

        if self.config.comparison_mode != ComparisonMode.NONE:
            y_field = self.config.y_axis_field or self.config.x_axis_field
            return f"{self.config.y_axis_measurement or self.config.x_axis_measurement} ({y_field})"

        if self.config.measurements:
            first_m = self.config.measurements[0]
            if hasattr(first_m, 'unit') and first_m.unit:
                name = first_m.name if hasattr(first_m, 'name') else "Measurement"
                return f"{name} ({first_m.unit})"

        return "Measurement Value"

    def _deep_copy_data(self, data: Dict) -> Dict:
        """Deep copy data for undo."""
        import copy
        return copy.deepcopy(data)

    def create_plot_widget(self) -> pg.PlotWidget:
        """Create and configure plot widget."""
        plot_widget = pg.PlotWidget()
        configure_plot_theme(plot_widget, self.config.color_scheme)

        plot_item = plot_widget.getPlotItem()
        plot_item.setLabel('bottom', self.prepared_data['metadata']['x_label'])
        plot_item.setLabel('left', self.prepared_data['metadata']['y_label'])

        if self.config.title:
            plot_item.setTitle(self.config.title)

        plot_widget.setMouseEnabled(x=True, y=True)

        # Configure grid
        self._configure_grid(plot_widget)

        return plot_widget

    def _configure_grid(self, plot_widget: pg.PlotWidget):
        """Configure grid lines with density and alpha settings."""
        plot_item = plot_widget.getPlotItem()

        # Set grid alpha
        alpha = int(self.config.grid_alpha * 255)

        # Get grid color based on theme
        if is_dark_mode(self.config.color_scheme):
            grid_color = (255, 255, 255, alpha)
        else:
            grid_color = (0, 0, 0, alpha)

        # Enable grid
        plot_item.showGrid(x=True, y=True, alpha=self.config.grid_alpha)

        # Adjust tick spacing based on density
        # Note: This affects how many grid lines appear
        x_axis = plot_item.getAxis('bottom')
        y_axis = plot_item.getAxis('left')

        if self.config.grid_density == 'sparse':
            # Fewer grid lines
            x_axis.setTickSpacing(major=10, minor=5)
            y_axis.setTickSpacing(major=10, minor=5)
        elif self.config.grid_density == 'dense':
            # More grid lines
            x_axis.setTickSpacing(major=2, minor=1)
            y_axis.setTickSpacing(major=2, minor=1)
        # 'normal' uses auto spacing (default)

    def plot_data(self, plot_widget: pg.PlotWidget):
        """Plot the prepared data."""
        if self.config.graph_type == GraphType.SCATTER:
            self._plot_scatter(plot_widget)
        elif self.config.graph_type == GraphType.LINE:
            self._plot_line(plot_widget)
        elif self.config.graph_type == GraphType.HISTOGRAM:
            self._plot_histogram(plot_widget)
        else:
            raise ValueError(f"Unsupported graph type: {self.config.graph_type}")

    def _plot_scatter(self, plot_widget: pg.PlotWidget):
        """Create scatter plot with proper markings for toggling."""
        plot_item = plot_widget.getPlotItem()
        groups = self.prepared_data['groups']
        color_index = 0

        total_points = self.prepared_data['metadata']['total_points']
        point_size = calculate_point_size(total_points) if self.config.enable_size_scaling else 8

        # Get plot boundaries for boxes
        all_x = []
        all_y = []

        for group_name, group_data in groups.items():
            color = self.color_palette[color_index % len(self.color_palette)]
            color_rgb = hex_to_rgb(color)

            # Plot scatter data
            if group_data.get('x_data'):
                x_data = group_data['x_data']
                y_data = group_data['y_data']

                all_x.extend(x_data)
                all_y.extend(y_data)

                scatter = pg.ScatterPlotItem(
                    x=x_data,
                    y=y_data,
                    size=point_size,
                    pen=pg.mkPen(None),
                    brush=pg.mkBrush(*color_rgb),
                    name=group_name
                )

                plot_item.addItem(scatter)

                # Store for interactivity - map (scatter_id, point_index) -> measurement
                for idx, (x, y) in enumerate(zip(x_data, y_data)):
                    meas_idx = group_data['measurement_indices'][idx]
                    # Store just the measurement, not a tuple
                    self.point_measurement_map[(id(scatter), idx)] = group_data['measurements'][meas_idx]

            color_index += 1

        # Note: Grouping boxes are added in apply_styling() -> _add_grouping_boxes()
        # to avoid duplication

        # Note: Spec lines are added in apply_styling() -> _add_spec_lines()
        # to avoid duplication

        # Set axis limits with 10% margin
        if all_x and all_y:
            x_range = max(all_x) - min(all_x)
            y_range = max(all_y) - min(all_y)

            plot_item.setXRange(
                min(all_x) - x_range * 0.1,
                max(all_x) + x_range * 0.1,
                padding=0
            )
            plot_item.setYRange(
                min(all_y) - y_range * 0.1,
                max(all_y) + y_range * 0.1,
                padding=0
            )


    # def _plot_scatter(self, plot_widget: pg.PlotWidget):
    #     """Create scatter plot."""
    #     plot_item = plot_widget.getPlotItem()
    #     groups = self.prepared_data['groups']
    #     color_index = 0
    #
    #     total_points = self.prepared_data['metadata']['total_points']
    #     point_size = calculate_point_size(total_points) if self.config.enable_size_scaling else 8
    #
    #     for group_name, group_data in groups.items():
    #         color = self.color_palette[color_index % len(self.color_palette)]
    #         color_rgb = hex_to_rgb(color)
    #
    #         if group_data.get('x_data') and group_data.get('y_data'):
    #             x_data = group_data['x_data']
    #             y_data = group_data['y_data']
    #             is_outlier = group_data.get('is_outlier', [False] * len(x_data))
    #             measurements = group_data['measurements']
    #             indices = group_data.get('measurement_indices', list(range(len(x_data))))
    #
    #             if self.config.remove_outliers:
    #                 filtered_data = [(x, y, i) for x, y, out, i in zip(x_data, y_data, is_outlier, indices) if not out]
    #                 if filtered_data:
    #                     x_filtered, y_filtered, indices_filtered = zip(*filtered_data)
    #                 else:
    #                     x_filtered, y_filtered, indices_filtered = [], [], []
    #             else:
    #                 x_filtered, y_filtered, indices_filtered = x_data, y_data, indices
    #
    #             if not x_filtered:
    #                 continue
    #
    #             scatter = pg.ScatterPlotItem(
    #                 x=x_filtered,
    #                 y=y_filtered,
    #                 pen=None,
    #                 brush=pg.mkBrush(*color_rgb, 200),
    #                 size=point_size,
    #                 name=group_name,
    #                 hoverable=True,
    #                 hoverSize=point_size * 1.5 if self.config.enable_hover_highlight else point_size
    #             )
    #
    #             item_id = id(scatter)
    #             for plot_idx, data_idx in enumerate(indices_filtered):
    #                 if 'measurement_pairs' in group_data:
    #                     self.point_measurement_map[(item_id, plot_idx)] = group_data['measurement_pairs'][data_idx]
    #                 else:
    #                     self.point_measurement_map[(item_id, plot_idx)] = measurements[data_idx]
    #
    #             scatter.opts['data'] = {'group': group_name, 'type': 'scalar'}
    #             plot_item.addItem(scatter)
    #
    #         # V4 FEATURE 5: Auto-overlay plot measurements
    #         if group_data.get('has_plots') and self.config.auto_overlay_plots:
    #             self._plot_overlaid_plots(plot_item, group_data['plot_measurements'], color, group_name)
    #
    #         color_index += 1
    #
    #     # V4 FEATURE 3: Set custom X-axis labels if using indices
    #     if self.config.x_axis_use_indices and self.config.graph_type == GraphType.SCATTER:
    #         self._set_custom_x_labels(plot_widget)

    def _set_custom_x_labels(self, plot_widget: pg.PlotWidget):
        """V4 FEATURE 3: Set custom X-axis tick labels."""
        plot_item = plot_widget.getPlotItem()
        groups = self.prepared_data['groups']

        # Collect all x_labels
        for group_data in groups.values():
            if 'x_labels' in group_data and group_data['x_labels']:
                x_labels = group_data['x_labels']
                x_indices = list(range(len(x_labels)))

                # Sample labels if too many
                if len(x_labels) > 20:
                    step = len(x_labels) // 20
                    ticks = [(i, str(x_labels[i])) for i in range(0, len(x_labels), step)]
                else:
                    ticks = [(i, str(x_labels[i])) for i in x_indices]

                axis = plot_item.getAxis('bottom')
                axis.setTicks([ticks])
                break

    def _plot_line(self, plot_widget: pg.PlotWidget):
        """Create line plot."""
        plot_item = plot_widget.getPlotItem()
        groups = self.prepared_data['groups']
        color_index = 0

        total_points = self.prepared_data['metadata']['total_points']
        line_width = calculate_line_width(total_points) if self.config.enable_size_scaling else 2

        for group_name, group_data in groups.items():
            color = self.color_palette[color_index % len(self.color_palette)]

            if group_data.get('x_data') and group_data.get('y_data'):
                x_data, y_data = group_data['x_data'], group_data['y_data']
                is_outlier = group_data.get('is_outlier', [False] * len(x_data))

                if self.config.remove_outliers:
                    x_filtered = [x for x, out in zip(x_data, is_outlier) if not out]
                    y_filtered = [y for y, out in zip(y_data, is_outlier) if not out]
                else:
                    x_filtered, y_filtered = x_data, y_data

                if not x_filtered:
                    continue

                sorted_pairs = sorted(zip(x_filtered, y_filtered))
                x_sorted = [p[0] for p in sorted_pairs]
                y_sorted = [p[1] for p in sorted_pairs]

                pen = pg.mkPen(color=color, width=line_width)
                line_plot = pg.PlotDataItem(x=x_sorted, y=y_sorted, pen=pen, name=group_name)
                line_plot.opts['data'] = {'group': group_name, 'type': 'scalar'}
                plot_item.addItem(line_plot)

            # V4 FEATURE 5: Overlay plots
            if group_data.get('has_plots') and self.config.auto_overlay_plots:
                self._plot_overlaid_plots(plot_item, group_data['plot_measurements'], color, group_name)

            color_index += 1

    def _plot_histogram(self, plot_widget: pg.PlotWidget):
        """Create histogram with combined data from all groups."""
        plot_item = plot_widget.getPlotItem()
        groups = self.prepared_data['groups']

        # Combine all values from all groups
        all_values = []
        for group_data in groups.values():
            if group_data.get('y_data'):
                is_outlier = group_data.get('is_outlier', [False] * len(group_data['y_data']))
                filtered = [y for y, out in zip(group_data['y_data'], is_outlier) if not out] if self.config.remove_outliers else group_data['y_data']
                all_values.extend(filtered)

        if not all_values:
            print("!!! _plot_histogram: No values to plot")
            return

        print(f"!!! _plot_histogram: Plotting {len(all_values)} combined values, range: [{min(all_values):.4f}, {max(all_values):.4f}]")

        # Calculate bins - ensure reasonable number
        num_bins = min(50, max(10, len(all_values) // 5))
        if num_bins < 5:
            num_bins = min(len(all_values), 10)

        # Use primary color
        color = self.color_palette[0] if self.color_palette else '#2196F3'
        color_rgb = hex_to_rgb(color)

        # Calculate histogram for combined data
        hist, bin_edges = np.histogram(all_values, bins=num_bins)
        x = (bin_edges[:-1] + bin_edges[1:]) / 2
        width = bin_edges[1] - bin_edges[0]

        print(f"!!! _plot_histogram: {num_bins} bins, width={width:.4f}, max_count={max(hist)}")

        # Scale bar width - use 90% of bin width
        display_width = width * 0.9

        # Create single combined histogram
        bar_item = pg.BarGraphItem(
            x=x,
            height=hist,
            width=display_width,
            brush=pg.mkBrush(*color_rgb, 200),
            pen=pg.mkPen(color, width=1),
            name='Distribution'
        )
        plot_item.addItem(bar_item)

        # Store histogram data for tooltips
        self.histogram_data = {
            'x': x,  # bin centers
            'heights': hist,  # counts
            'bin_edges': bin_edges,
            'width': width,
            'total_count': len(all_values)
        }

        # Set axis labels for histogram
        plot_item.setLabel('bottom', self.config.y_label if self.config.y_label else 'Value')
        plot_item.setLabel('left', 'Count')

        print(f"!!! _plot_histogram: Added bar graph with {num_bins} bins, {len(hist)} bars")

    def _plot_overlaid_plots(self, plot_item: pg.PlotItem, plot_measurements: List[Any], color: str, group_name: str):
        """V4 FEATURE 5: Overlay plot-type measurements."""
        total_points = self.prepared_data['metadata']['total_points']
        line_width = calculate_line_width(total_points) if self.config.enable_size_scaling else 2

        for idx, measurement in enumerate(plot_measurements):
            if not measurement.plot_data:
                continue

            y_data = measurement.plot_data
            x_data = list(range(len(y_data)))

            pen_style = pg.QtCore.Qt.PenStyle.SolidLine
            if idx > 0:
                styles = [pg.QtCore.Qt.PenStyle.DashLine, pg.QtCore.Qt.PenStyle.DotLine, pg.QtCore.Qt.PenStyle.DashDotLine]
                pen_style = styles[(idx - 1) % len(styles)]

            pen = pg.mkPen(color=color, width=line_width, style=pen_style)
            plot_name = f"{group_name} - {measurement.name}"
            if len(plot_measurements) > 1:
                plot_name += f" #{idx + 1}"

            line_plot = pg.PlotDataItem(x=x_data, y=y_data, pen=pen, name=plot_name)
            line_plot.opts['data'] = {'group': group_name, 'type': 'plot', 'measurement_id': measurement.id}
            plot_item.addItem(line_plot)

    def apply_styling(self, plot_widget: pg.PlotWidget):
        """Apply styling with v4 enhancements."""
        plot_item = plot_widget.getPlotItem()

        if self.config.show_spec_lines:
            # Use vertical spec lines for histogram, horizontal for others
            if self.config.graph_type == GraphType.HISTOGRAM:
                self._add_spec_lines_vertical(plot_item)
            else:
                self._add_spec_lines(plot_item)

        # Only add grouping boxes for SCATTER plots (not LINE or HISTOGRAM)
        if self.config.enable_grouping_boxes and self.config.graph_type == GraphType.SCATTER:
            self._add_grouping_boxes(plot_item)

        # V4 FEATURE 9: Add comparison line
        if self.config.comparison_mode != ComparisonMode.NONE and self.config.show_comparison_line:
            self._add_comparison_reference_line(plot_item)

        # V4 FEATURE 10: Add styled legend
        if self.config.show_legend:
            self._add_styled_legend(plot_item)

        # V4 FEATURE 4: Set fixed axis ranges
        self._set_axis_ranges(plot_widget)

    def _add_spec_lines(self, plot_item: pg.PlotItem):
        """Add specification limit lines with bold label on left side, no background."""
        groups = self.prepared_data['groups']
        spec_limits = set()

        for group_data in groups.values():
            for measurement in group_data['measurements']:
                if hasattr(measurement, 'upper_limit') and measurement.upper_limit is not None:
                    spec_limits.add(('upper', float(measurement.upper_limit)))
                if hasattr(measurement, 'lower_limit') and measurement.lower_limit is not None:
                    spec_limits.add(('lower', float(measurement.lower_limit)))

        print(f"!!! _add_spec_lines: Found {len(spec_limits)} spec limits: {spec_limits}")

        for limit_type, limit_value in spec_limits:
            if limit_type == 'upper':
                color = '#ff4444' if is_dark_mode(self.config.color_scheme) else '#cc0000'
                label_text = f'Upper: {limit_value:.3f}'
            else:
                color = '#ff8800' if is_dark_mode(self.config.color_scheme) else '#ff6600'
                label_text = f'Lower: {limit_value:.3f}'

            pen = pg.mkPen(color=color, width=2, style=pg.QtCore.Qt.PenStyle.DashLine)

            # Create line with bold label, no background
            line = pg.InfiniteLine(
                pos=limit_value,
                angle=0,
                pen=pen,
                label=label_text,
                labelOpts={
                    'position': 0.05,
                    'color': color,
                    'fill': None,  # No background
                    'movable': False
                }
            )

            # Make label bold by accessing the label's text item
            if line.label is not None:
                font = line.label.textItem.font()
                font.setBold(True)
                line.label.textItem.setFont(font)

            # Mark for toggling
            line.spec_line = True
            line.spec_line_type = limit_type

            plot_item.addItem(line)
            print(f"!!! Added spec line: {label_text} at y={limit_value}")

    def _add_spec_lines_vertical(self, plot_item: pg.PlotItem):
        """Add vertical specification limit lines for histogram plots."""
        groups = self.prepared_data['groups']
        spec_limits = set()

        for group_data in groups.values():
            for measurement in group_data['measurements']:
                if hasattr(measurement, 'upper_limit') and measurement.upper_limit is not None:
                    spec_limits.add(('upper', float(measurement.upper_limit)))
                if hasattr(measurement, 'lower_limit') and measurement.lower_limit is not None:
                    spec_limits.add(('lower', float(measurement.lower_limit)))

        print(f"!!! _add_spec_lines_vertical: Found {len(spec_limits)} spec limits: {spec_limits}")

        for limit_type, limit_value in spec_limits:
            if limit_type == 'upper':
                color = '#ff4444' if is_dark_mode(self.config.color_scheme) else '#cc0000'
                label_text = f'Upper: {limit_value:.3f}'
            else:
                color = '#ff8800' if is_dark_mode(self.config.color_scheme) else '#ff6600'
                label_text = f'Lower: {limit_value:.3f}'

            pen = pg.mkPen(color=color, width=2, style=pg.QtCore.Qt.PenStyle.DashLine)

            # Create VERTICAL line (angle=90) for histogram
            line = pg.InfiniteLine(
                pos=limit_value,
                angle=90,  # Vertical line
                pen=pen,
                label=label_text,
                labelOpts={
                    'position': 0.95,
                    'color': color,
                    'fill': None,
                    'movable': False
                }
            )

            # Make label bold
            if line.label is not None:
                font = line.label.textItem.font()
                font.setBold(True)
                line.label.textItem.setFont(font)

            # Mark for toggling
            line.spec_line_type = limit_type
            line.spec_line = True

            plot_item.addItem(line)
            print(f"!!! Added vertical spec line: {label_text} at x={limit_value}")

    def _add_grouping_boxes(self, plot_item: pg.PlotItem):
        """V4 FEATURE 6: Full-height colored grouping boxes with labels."""
        groups = self.prepared_data['groups']

        if len(groups) <= 1:
            return

        # Get full Y-axis range
        y_min, y_max = float('inf'), float('-inf')
        for group_data in groups.values():
            if group_data.get('y_data'):
                y_min = min(y_min, min(group_data['y_data']))
                y_max = max(y_max, max(group_data['y_data']))

        if y_min == float('inf'):
            return

        # Add 10% padding to Y range
        y_range_val = y_max - y_min
        y_min_box = y_min - y_range_val * 0.1
        y_max_box = y_max + y_range_val * 0.1

        color_index = 0
        for group_name, group_data in groups.items():
            if not group_data.get('x_data'):
                continue

            x_data = group_data['x_data']
            if not x_data:
                continue

            x_min_box = min(x_data) - 0.5
            x_max_box = max(x_data) + 0.5
            x_center = (x_min_box + x_max_box) / 2

            # Get color for this group
            color = self.color_palette[color_index % len(self.color_palette)]

            # Create box with correct parameters
            box = create_dashed_box_item(
                x_range=(x_min_box, x_max_box),
                y_range=(y_min_box, y_max_box),
                color=color
            )
            box.grouping_box = True  # Mark for toggling boxes
            plot_item.addItem(box)

            # Add label on top of box (separate toggle)
            label = pg.TextItem(
                text=group_name,
                color=color,
                anchor=(0.5, 1.0)  # Center horizontally, anchor at bottom of text
            )
            label.setPos(x_center, y_max_box)

            # Make label bold
            font = label.textItem.font()
            font.setBold(True)
            font.setPointSize(9)
            label.textItem.setFont(font)

            label.grouping_box_label = True  # Separate attribute for label toggling
            plot_item.addItem(label)

            print(f"!!! Added grouping box for '{group_name}': x=[{x_min_box:.1f}, {x_max_box:.1f}]")

            color_index += 1

    def _add_comparison_reference_line(self, plot_item: pg.PlotItem):
        """V4 FEATURE 9: Add diagonal y=x line."""
        groups = self.prepared_data['groups']

        all_values = []
        for group_data in groups.values():
            if group_data.get('x_data'):
                all_values.extend(group_data['x_data'])
            if group_data.get('y_data'):
                all_values.extend(group_data['y_data'])

        if not all_values:
            return

        min_val, max_val = min(all_values), max(all_values)

        color = '#888888'
        pen = pg.mkPen(color=color, width=2, style=pg.QtCore.Qt.PenStyle.DashLine)

        line = pg.PlotDataItem(
            x=[min_val, max_val],
            y=[min_val, max_val],
            pen=pen,
            name='y=x'
        )
        plot_item.addItem(line)

    def _add_styled_legend(self, plot_item: pg.PlotItem):
        """V4 FEATURE 10: Styled legend with solid background to hide grid lines."""
        legend = plot_item.addLegend()

        # V4: Apply solid background (fully opaque to hide grid)
        if is_dark_mode(self.config.color_scheme):
            legend.setLabelTextColor('#e0e0e0')
            legend.setBrush(pg.mkBrush(30, 30, 30, 255))  # Fully opaque dark background
            legend.setPen(pg.mkPen('#606060', width=self.config.legend_border_width))
        else:
            legend.setLabelTextColor('#000000')
            legend.setBrush(pg.mkBrush(255, 255, 255, 255))  # Fully opaque white background
            legend.setPen(pg.mkPen('#808080', width=self.config.legend_border_width))

        # Explicitly add items to legend (pyqtgraph doesn't always auto-detect)
        for item in plot_item.items:
            name = None

            # Handle ScatterPlotItem
            if isinstance(item, pg.ScatterPlotItem):
                name = item.opts.get('name', None)
            # Handle PlotDataItem (line plots)
            elif isinstance(item, pg.PlotDataItem):
                name = item.opts.get('name', None)
            # Handle BarGraphItem (histogram)
            elif isinstance(item, pg.BarGraphItem):
                name = item.opts.get('name', None)

            if name and name not in ['All Data', 'y=x', 'y = x']:  # Skip certain names
                legend.addItem(item, name)
                print(f"!!! Added to legend: {name} ({type(item).__name__})")

        # V4: Position legend
        positions = {
            'top-left': (0, 0),
            'top-right': (1, 0),
            'bottom-left': (0, 1),
            'bottom-right': (1, 1)
        }
        offset = positions.get(self.config.legend_position, (1, 0))
        legend.setOffset(offset)

        print(f"!!! Legend now has {len(legend.items)} items")

    def _set_axis_ranges(self, plot_widget: pg.PlotWidget):
        """V4 FEATURE 4: Set fixed axis ranges with margins."""
        plot_item = plot_widget.getPlotItem()
        groups = self.prepared_data['groups']

        # For histogram, let pyqtgraph auto-range since we create bars directly
        if self.config.graph_type == GraphType.HISTOGRAM:
            plot_item.enableAutoRange()
            return

        x_vals, y_vals = [], []
        for group_data in groups.values():
            if group_data.get('x_data'):
                x_vals.extend(group_data['x_data'])
            if group_data.get('y_data'):
                y_vals.extend(group_data['y_data'])

        if not x_vals or not y_vals:
            return

        # V4 FEATURE 4: Calculate range with fixed margin
        margin = self.config.axis_margin_percent / 100.0

        x_min, x_max = min(x_vals), max(x_vals)
        x_range = x_max - x_min
        x_margin = x_range * margin

        y_min, y_max = min(y_vals), max(y_vals)
        y_range = y_max - y_min
        y_margin = y_range * margin

        plot_item.setXRange(x_min - x_margin, x_max + x_margin, padding=0)
        plot_item.setYRange(y_min - y_margin, y_max + y_margin, padding=0)

    def setup_interactivity(self, plot_widget: pg.PlotWidget):
        """Setup v4 interactive features."""
        plot_item = plot_widget.getPlotItem()

        # Keep default pyqtgraph context menu but extend it
        # We'll add our options to the existing menu
        self._extend_default_context_menu(plot_widget)

        # V4: Crosshair
        if self.config.enable_crosshair:
            self._add_crosshair(plot_widget)

        # V4 FEATURE 2: Setup styled tooltip
        if self.config.enable_tooltips:
            self._setup_tooltip(plot_widget)

        # V4 FEATURE 1 & 7: Click for tooltip/menu, hover for highlight
        plot_widget.scene().sigMouseClicked.connect(
            lambda evt: self._on_plot_clicked(evt, plot_widget)
        )

        if self.config.enable_hover_highlight:
            plot_widget.scene().sigMouseMoved.connect(
                lambda pos: self._on_mouse_moved(pos, plot_widget)
            )

        plot_widget.graph_generator = self

    def _extend_default_context_menu(self, plot_widget: pg.PlotWidget):
        """Extend the default pyqtgraph context menu with grid density options."""
        from functools import partial

        plot_item = plot_widget.getPlotItem()
        vb = plot_item.vb

        # Store reference to generator for point detection
        vb._graph_generator = self
        vb._plot_widget = plot_widget

        # Override the raiseContextMenu to check for point clicks first
        original_raise_context_menu = vb.raiseContextMenu

        def custom_raise_context_menu(event):
            # Check if we clicked on a point
            pos = event.scenePos()
            nearest_item, nearest_idx, distance = self._find_nearest_point(pos, plot_widget, threshold=20)
            if nearest_item is not None:
                # Don't show default menu - our point menu will handle it
                return
            # Show default menu for non-point clicks
            original_raise_context_menu(event)

        vb.raiseContextMenu = custom_raise_context_menu

        # Get the default ViewBox menu
        default_menu = vb.menu

        # Add separator before our additions
        default_menu.addSeparator()

        # Create Grid Density submenu
        grid_density_menu = default_menu.addMenu("Grid Density")

        # X-Axis density submenu
        x_density_menu = grid_density_menu.addMenu("X-Axis")
        x_density_group = QActionGroup(x_density_menu)
        x_density_group.setExclusive(True)

        for density_name in ['Sparse', 'Normal', 'Dense']:
            action = QAction(density_name, x_density_menu)
            action.setCheckable(True)
            action.setChecked(density_name.lower() == 'normal')
            # Use partial for reliable closure
            action.triggered.connect(partial(self._set_grid_density_axis, plot_widget, 'x', density_name.lower()))
            x_density_group.addAction(action)
            x_density_menu.addAction(action)

        # Y-Axis density submenu
        y_density_menu = grid_density_menu.addMenu("Y-Axis")
        y_density_group = QActionGroup(y_density_menu)
        y_density_group.setExclusive(True)

        for density_name in ['Sparse', 'Normal', 'Dense']:
            action = QAction(density_name, y_density_menu)
            action.setCheckable(True)
            action.setChecked(density_name.lower() == 'normal')
            # Use partial for reliable closure
            action.triggered.connect(partial(self._set_grid_density_axis, plot_widget, 'y', density_name.lower()))
            y_density_group.addAction(action)
            y_density_menu.addAction(action)

        # Both axes option
        grid_density_menu.addSeparator()
        both_menu = grid_density_menu.addMenu("Both Axes")
        both_density_group = QActionGroup(both_menu)
        both_density_group.setExclusive(True)

        for density_name in ['Sparse', 'Normal', 'Dense']:
            action = QAction(density_name, both_menu)
            action.setCheckable(True)
            action.setChecked(density_name.lower() == 'normal')
            # Use partial for reliable closure
            action.triggered.connect(partial(self._set_grid_density, plot_widget, density_name.lower()))
            both_density_group.addAction(action)
            both_menu.addAction(action)

        # Store references for updating check states later
        plot_widget._x_density_group = x_density_group
        plot_widget._y_density_group = y_density_group
        plot_widget._both_density_group = both_density_group

    def _set_grid_density_axis(self, plot_widget: pg.PlotWidget, axis: str, density: str, checked=None):
        """Change grid density for a single axis."""
        print(f"!!! _set_grid_density_axis called: axis={axis}, density={density}")

        plot_item = plot_widget.getPlotItem()

        if axis == 'x':
            target_axis = plot_item.getAxis('bottom')
            print(f"!!! Setting X-axis (bottom) to {density}")
        else:
            target_axis = plot_item.getAxis('left')
            print(f"!!! Setting Y-axis (left) to {density}")

        # Get the current axis range to calculate appropriate tick spacing
        view_range = plot_item.viewRange()
        if axis == 'x':
            axis_range = abs(view_range[0][1] - view_range[0][0])
        else:
            axis_range = abs(view_range[1][1] - view_range[1][0])

        print(f"!!! Axis range: {axis_range}")

        if axis_range == 0:
            axis_range = 1  # Prevent division by zero

        if density == 'sparse':
            # Few ticks - divide range by ~3-4
            major = axis_range / 3
            minor = major / 2
            target_axis.setTickSpacing(major=major, minor=minor)
            print(f"!!! Set sparse: major={major:.4f}, minor={minor:.4f}")
        elif density == 'dense':
            # Many ticks - divide range by ~15-20
            major = axis_range / 15
            minor = major / 5
            target_axis.setTickSpacing(major=major, minor=minor)
            print(f"!!! Set dense: major={major:.4f}, minor={minor:.4f}")
        else:  # normal
            # Reset to auto
            target_axis.setTickSpacing()
            print(f"!!! Set normal (auto)")

        plot_widget.update()
        print(f"!!! Grid density update complete")

    def _set_grid_density(self, plot_widget: pg.PlotWidget, density: str):
        """Change grid density for both axes."""
        self.config.grid_density = density

        plot_item = plot_widget.getPlotItem()
        x_axis = plot_item.getAxis('bottom')
        y_axis = plot_item.getAxis('left')

        # Get view ranges
        view_range = plot_item.viewRange()
        x_range = abs(view_range[0][1] - view_range[0][0]) or 1
        y_range = abs(view_range[1][1] - view_range[1][0]) or 1

        if density == 'sparse':
            x_axis.setTickSpacing(major=x_range/3, minor=x_range/6)
            y_axis.setTickSpacing(major=y_range/3, minor=y_range/6)
        elif density == 'dense':
            x_axis.setTickSpacing(major=x_range/15, minor=x_range/75)
            y_axis.setTickSpacing(major=y_range/15, minor=y_range/75)
        else:  # normal
            x_axis.setTickSpacing()
            y_axis.setTickSpacing()

        plot_widget.update()

    def _setup_tooltip(self, plot_widget: pg.PlotWidget):
        """V4 FEATURE 2: Styled tooltip."""
        plot_item = plot_widget.getPlotItem()
        self.tooltip_label = pg.TextItem(anchor=(0, 1))

        # V4 FEATURE 2: Solid themed background
        if is_dark_mode(self.config.color_scheme):
            self.tooltip_label.setColor('#e0e0e0')
            self.tooltip_label.fill = pg.mkBrush(30, 30, 30, 235)
            self.tooltip_label.border = pg.mkPen('#606060', width=2)
        else:
            self.tooltip_label.setColor('#000000')
            self.tooltip_label.fill = pg.mkBrush(255, 255, 255, 235)
            self.tooltip_label.border = pg.mkPen('#808080', width=2)

        self.tooltip_label.setVisible(False)
        plot_item.addItem(self.tooltip_label)

    def _add_crosshair(self, plot_widget: pg.PlotWidget):
        """Add crosshair cursor."""
        plot_item = plot_widget.getPlotItem()

        v_line = pg.InfiniteLine(angle=90, movable=False)
        h_line = pg.InfiniteLine(angle=0, movable=False)

        plot_item.addItem(v_line, ignoreBounds=True)
        plot_item.addItem(h_line, ignoreBounds=True)

        pen = pg.mkPen(color='#888888', width=1, style=pg.QtCore.Qt.PenStyle.DashLine)
        v_line.setPen(pen)
        h_line.setPen(pen)

        v_line.setVisible(False)
        h_line.setVisible(False)

        plot_widget.crosshair_v = v_line
        plot_widget.crosshair_h = h_line
        plot_widget.crosshairs_enabled = True  # Default to enabled

        def mouse_moved(evt):
            pos = evt[0] if isinstance(evt, tuple) else evt

            # Check if crosshairs are enabled (controlled by checkbox)
            if not getattr(plot_widget, 'crosshairs_enabled', True):
                v_line.setVisible(False)
                h_line.setVisible(False)
                return

            if plot_item.sceneBoundingRect().contains(pos):
                mouse_point = plot_item.vb.mapSceneToView(pos)
                v_line.setPos(mouse_point.x())
                h_line.setPos(mouse_point.y())
                v_line.setVisible(True)
                h_line.setVisible(True)
            else:
                v_line.setVisible(False)
                h_line.setVisible(False)

        proxy = pg.SignalProxy(plot_widget.scene().sigMouseMoved, rateLimit=60, slot=mouse_moved)
        plot_widget.mouse_proxy = proxy

    def _on_mouse_moved(self, pos: QPointF, plot_widget: pg.PlotWidget):
        """V4 FEATURE 1: Hover only highlights, no tooltip."""
        plot_item = plot_widget.getPlotItem()

        if not plot_item.sceneBoundingRect().contains(pos):
            self._clear_hover_highlight(plot_widget)
            return

        nearest_item, nearest_idx, min_distance = self._find_nearest_point(pos, plot_widget, threshold=20)

        if nearest_item is not None and nearest_idx is not None:
            self._apply_hover_highlight(nearest_item, nearest_idx, plot_widget)
        else:
            self._clear_hover_highlight(plot_widget)

    def _find_nearest_point(self, scene_pos: QPointF, plot_widget: pg.PlotWidget, threshold: float = 20) -> Tuple[Optional[Any], Optional[int], float]:
        """Find nearest point to cursor (supports scatter points and histogram bars)."""
        plot_item = plot_widget.getPlotItem()

        nearest_item, nearest_idx, min_distance = None, None, float('inf')

        # Convert scene position to view coordinates for histogram bar detection
        view_pos = plot_item.vb.mapSceneToView(scene_pos)

        for item in plot_item.items:
            if isinstance(item, pg.ScatterPlotItem):
                points = item.getData()
                if points is None or len(points) == 0:
                    continue

                x_data, y_data = points

                for idx in range(len(x_data)):
                    point_view_pos = QPointF(x_data[idx], y_data[idx])
                    scene_point = plot_item.vb.mapViewToScene(point_view_pos)

                    dx = scene_point.x() - scene_pos.x()
                    dy = scene_point.y() - scene_pos.y()
                    distance = np.sqrt(dx**2 + dy**2)

                    if distance < min_distance and distance < threshold:
                        min_distance = distance
                        nearest_item = item
                        nearest_idx = idx

            # Check for histogram bars
            elif isinstance(item, pg.BarGraphItem) and self.histogram_data:
                # Get bar positions and dimensions
                x_centers = self.histogram_data['x']
                heights = self.histogram_data['heights']
                width = self.histogram_data['width']

                # Check if click is within any bar
                for idx, (x_center, height) in enumerate(zip(x_centers, heights)):
                    if height == 0:
                        continue

                    # Check if view_pos is within bar bounds
                    half_width = width * 0.45  # Slightly less than half to account for display width

                    if (x_center - half_width <= view_pos.x() <= x_center + half_width and
                        0 <= view_pos.y() <= height):
                        # Found a bar - use distance of 0 to prioritize
                        nearest_item = item
                        nearest_idx = idx
                        min_distance = 0
                        break

        return nearest_item, nearest_idx, min_distance

    def _apply_hover_highlight(self, item: Any, point_idx: int, plot_widget: pg.PlotWidget):
        """V4: Highlight on hover (no tooltip)."""
        if self.hover_item != item or self.hover_index != point_idx:
            self._clear_hover_highlight(plot_widget)

        if isinstance(item, pg.ScatterPlotItem):
            if self.selected_item != item or self.selected_index != point_idx:
                if not hasattr(item, 'original_sizes'):
                    item.original_sizes = item.opts['size']

                if isinstance(item.original_sizes, (int, float)):
                    sizes = [item.original_sizes] * len(item.getData()[0])
                else:
                    sizes = list(item.original_sizes)

                sizes[point_idx] = (item.original_sizes * 1.5 if isinstance(item.original_sizes, (int, float))
                                    else item.original_sizes[point_idx] * 1.5)
                item.setSize(sizes)

                self.hover_item = item
                self.hover_index = point_idx

    def _clear_hover_highlight(self, plot_widget: pg.PlotWidget):
        """Clear hover highlight."""
        if self.hover_item is not None and isinstance(self.hover_item, pg.ScatterPlotItem):
            if hasattr(self.hover_item, 'original_sizes'):
                if self.selected_item != self.hover_item or self.selected_index != self.hover_index:
                    self.hover_item.setSize(self.hover_item.original_sizes)

        self.hover_item = None
        self.hover_index = None

    def _on_plot_clicked(self, event, plot_widget: pg.PlotWidget):
        """V4 FEATURE 1 & 7: Click shows tooltip, right-click shows unified menu."""
        pos = event.scenePos()
        plot_item = plot_widget.getPlotItem()

        if not plot_item.sceneBoundingRect().contains(pos):
            return

        button = event.button()
        nearest_item, nearest_idx, distance = self._find_nearest_point(pos, plot_widget, threshold=20)

        if nearest_item is None or nearest_idx is None:
            if button == Qt.MouseButton.LeftButton:
                self._clear_selection(plot_widget)
            # Right-click on empty area: let the default pyqtgraph menu handle it
            return

        if button == Qt.MouseButton.LeftButton:
            # V4 FEATURE 1: Left click shows tooltip
            if isinstance(nearest_item, pg.BarGraphItem):
                # Histogram bar clicked
                if self.tooltip_label and self.config.enable_tooltips:
                    mouse_point = plot_item.vb.mapSceneToView(pos)
                    self._show_histogram_tooltip(nearest_idx, mouse_point)
            else:
                # Scatter/line point clicked
                self._select_point(nearest_item, nearest_idx, plot_widget)

                if self.tooltip_label and self.config.enable_tooltips:
                    mouse_point = plot_item.vb.mapSceneToView(pos)
                    self._show_tooltip(nearest_item, nearest_idx, mouse_point)

        elif button == Qt.MouseButton.RightButton and self.config.enable_point_deletion:
            # V4 FEATURE 7: Unified context menu for points (not for histogram)
            if not isinstance(nearest_item, pg.BarGraphItem):
                self._show_unified_context_menu(nearest_item, nearest_idx, event.screenPos().toPoint(), plot_widget)

    def _select_point(self, item: Any, point_idx: int, plot_widget: pg.PlotWidget):
        """Select point on click."""
        self._clear_selection(plot_widget)

        if isinstance(item, pg.ScatterPlotItem):
            if not hasattr(item, 'original_sizes'):
                item.original_sizes = item.opts['size']

            if isinstance(item.original_sizes, (int, float)):
                sizes = [item.original_sizes] * len(item.getData()[0])
            else:
                sizes = list(item.original_sizes)

            sizes[point_idx] = (item.original_sizes * 1.8 if isinstance(item.original_sizes, (int, float))
                                else item.original_sizes[point_idx] * 1.8)
            item.setSize(sizes)

            self.selected_item = item
            self.selected_index = point_idx

    def _clear_selection(self, plot_widget: pg.PlotWidget):
        """Clear selection."""
        if self.selected_item is not None and isinstance(self.selected_item, pg.ScatterPlotItem):
            if hasattr(self.selected_item, 'original_sizes'):
                self.selected_item.setSize(self.selected_item.original_sizes)

        self.selected_item = None
        self.selected_index = None

        if self.tooltip_label:
            self.tooltip_label.setVisible(False)

    def _show_tooltip(self, item: Any, point_idx: int, mouse_point: QPointF):
        """V4 FEATURE 2: Show styled tooltip."""
        if not self.tooltip_label:
            return

        item_id = id(item)
        measurement = self.point_measurement_map.get((item_id, point_idx))

        if measurement is None:
            return

        if self.config.point_info_callback:
            try:
                info_dict = self.config.point_info_callback(measurement)
                tooltip_lines = [f"{key}: {value}" for key, value in info_dict.items()]
                tooltip_text = "\n".join(tooltip_lines)
            except Exception as e:
                tooltip_text = f"Error: {str(e)}"
        else:
            if isinstance(measurement, tuple):
                x_meas, y_meas = measurement
                tooltip_text = f"X: {x_meas.measurement:.3f}\n" \
                               f"Y: {y_meas.measurement:.3f}"
            else:
                value = measurement.measurement
                unit = measurement.unit if hasattr(measurement, 'unit') else ''
                tooltip_text = f"Value: {value:.3f} {unit}".strip()
                if hasattr(measurement, 'name'):
                    tooltip_text = f"{measurement.name} {tooltip_text}"

        self.tooltip_label.setText(tooltip_text)
        self.tooltip_label.setPos(mouse_point.x(), mouse_point.y())
        self.tooltip_label.setVisible(True)

    def _show_histogram_tooltip(self, bar_idx: int, mouse_point: QPointF):
        """Show tooltip for histogram bar."""
        if not self.tooltip_label or not self.histogram_data:
            return

        x_centers = self.histogram_data['x']
        heights = self.histogram_data['heights']
        bin_edges = self.histogram_data['bin_edges']
        total_count = self.histogram_data['total_count']

        if bar_idx >= len(x_centers):
            return

        # Get bar info
        count = heights[bar_idx]
        bin_start = bin_edges[bar_idx]
        bin_end = bin_edges[bar_idx + 1]
        percentage = (count / total_count * 100) if total_count > 0 else 0

        # Build tooltip text
        tooltip_text = f"Range: {bin_start:.4f} - {bin_end:.4f}\n"
        tooltip_text += f"Count: {count}\n"
        tooltip_text += f"Percentage: {percentage:.1f}%"

        self.tooltip_label.setText(tooltip_text)
        self.tooltip_label.setPos(mouse_point.x(), mouse_point.y())
        self.tooltip_label.setVisible(True)

    def _show_unified_context_menu(self, item: Any, point_idx: int, global_pos, plot_widget: pg.PlotWidget):
        """V4 FEATURE 7: Unified context menu for scatter points."""
        menu = QMenu()

        # Get the measurement for this point
        item_id = id(item)
        measurement = self.point_measurement_map.get((item_id, point_idx))

        # View Test Log action (only if measurement has test log)
        if measurement is not None:
            view_log_action = QAction("View Test Log", menu)
            view_log_action.triggered.connect(lambda: self._view_test_log(measurement, plot_widget))
            menu.addAction(view_log_action)
            menu.addSeparator()

        # Delete action
        delete_action = QAction("Delete Point", menu)
        delete_action.triggered.connect(lambda: self._delete_point(item, point_idx, plot_widget))
        menu.addAction(delete_action)

        # Undo action
        if len(self.deleted_items) > 0:
            menu.addSeparator()
            undo_action = QAction(f"Undo Deletions ({len(self.deleted_items)})", menu)
            undo_action.triggered.connect(lambda: self.reset_deletions(plot_widget))
            menu.addAction(undo_action)

        # View All action
        menu.addSeparator()
        view_all_action = QAction("View All", menu)
        view_all_action.triggered.connect(lambda: plot_widget.getPlotItem().autoRange())
        menu.addAction(view_all_action)

        # Export action
        export_action = QAction("Export Image...", menu)
        export_action.triggered.connect(lambda: self._export_plot_dialog(plot_widget))
        menu.addAction(export_action)

        menu.exec(global_pos)

    def _view_test_log(self, measurement, plot_widget: pg.PlotWidget):
        """Navigate to test log view for the given measurement."""
        try:
            # Get the test log from the measurement
            test_log = None
            html_content = None

            if hasattr(measurement, 'sub_test') and measurement.sub_test:
                if hasattr(measurement.sub_test, 'test_log') and measurement.sub_test.test_log:
                    test_log = measurement.sub_test.test_log
                    html_content = getattr(test_log, 'html_content', None)

            if not html_content:
                print("!!! No HTML content available for this test log")
                return

            # Get the main window through the graph_page reference
            if hasattr(plot_widget, 'graph_page') and plot_widget.graph_page:
                plot_widget.graph_page.view_test_log_html(html_content)
            else:
                print("!!! Cannot access graph_page from plot_widget")

        except Exception as e:
            print(f"!!! Error viewing test log: {e}")

    def _delete_point(self, item: Any, point_idx: int, plot_widget: pg.PlotWidget):
        """Delete a point."""
        if not isinstance(item, pg.ScatterPlotItem):
            return

        item_id = id(item)
        point_id = f"{item_id}_{point_idx}"
        self.deleted_items.add(point_id)

        x_data, y_data = item.getData()

        if x_data is None or y_data is None or len(x_data) == 0:
            return

        mask = np.ones(len(x_data), dtype=bool)
        mask[point_idx] = False

        new_x, new_y = x_data[mask], y_data[mask]

        if hasattr(item, 'original_sizes'):
            if isinstance(item.original_sizes, (int, float)):
                new_sizes = item.original_sizes
            else:
                new_sizes = np.array(item.original_sizes)[mask]
            item.setData(x=new_x, y=new_y)
            item.setSize(new_sizes)
            item.original_sizes = new_sizes
        else:
            item.setData(x=new_x, y=new_y)

        # Update point measurement map
        new_map = {}
        for (stored_id, stored_idx), measurement in self.point_measurement_map.items():
            if stored_id == item_id:
                if stored_idx < point_idx:
                    new_map[(stored_id, stored_idx)] = measurement
                elif stored_idx > point_idx:
                    new_map[(stored_id, stored_idx - 1)] = measurement
            else:
                new_map[(stored_id, stored_idx)] = measurement

        self.point_measurement_map = new_map

        if self.selected_item == item and self.selected_index == point_idx:
            self._clear_selection(plot_widget)

    def reset_deletions(self, plot_widget: pg.PlotWidget):
        """Reset all deleted points."""
        self.deleted_items.clear()

        if self.original_data:
            self.prepared_data = self._deep_copy_data(self.original_data)

        self._clear_selection(plot_widget)

        plot_widget.clear()
        self.plot_data(plot_widget)
        self.apply_styling(plot_widget)
        self.setup_interactivity(plot_widget)

    def _export_plot_dialog(self, plot_widget: pg.PlotWidget):
        """Export plot to image."""
        try:
            from PyQt6.QtWidgets import QFileDialog
            filepath, _ = QFileDialog.getSaveFileName(
                None, "Export Plot", "", "PNG Image (*.png);;All Files (*)"
            )
            if filepath:
                self.export_plot(plot_widget, filepath)
        except Exception as e:
            print(f"Export error: {e}")

    def export_plot(self, plot_widget: pg.PlotWidget, filepath: str, width: int = 1920, height: int = 1080):
        """Export plot to file."""
        try:
            exporter = pg.exporters.ImageExporter(plot_widget.plotItem)
            exporter.parameters()['width'] = width
            exporter.parameters()['height'] = height
            exporter.export(filepath)
        except Exception as e:
            raise IOError(f"Failed to export plot: {str(e)}")