"""
Utility functions for graph generation and styling.

This module provides helper functions for color palette generation,
theme configuration, outlier detection, and data processing.
"""

from typing import List, Tuple, Dict, Any
import numpy as np
from PyQt6.QtGui import QColor
import pyqtgraph as pg

from .graph_config import ColorScheme


# Color palettes for different schemes
TABLEAU_10 = [
    '#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F',
    '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#BAB0AC'
]

COLORBLIND_SAFE = [
    '#0173B2', '#DE8F05', '#029E73', '#CC78BC', '#CA9161',
    '#949494', '#ECE133', '#56B4E9', '#FBAFE4', '#FFFF00'
]

TABLEAU_10_DARK = [
    '#5DA5DA', '#FAA43A', '#F17CB0', '#B2912F', '#B276B2',
    '#DECF3F', '#F15854', '#60BD68', '#FAA43A', '#B2912F'
]

COLORBLIND_SAFE_DARK = [
    '#56B4E9', '#F0E442', '#009E73', '#E69F00', '#CC79A7',
    '#D55E00', '#0072B2', '#999999', '#FFD700', '#00CED1'
]


def get_color_palette(scheme: ColorScheme) -> List[str]:
    """Get color palette for the specified color scheme."""
    palette_map = {
        ColorScheme.LIGHT_NORMAL: TABLEAU_10,
        ColorScheme.LIGHT_HIGH: COLORBLIND_SAFE,
        ColorScheme.DARK_NORMAL: TABLEAU_10_DARK,
        ColorScheme.DARK_HIGH: COLORBLIND_SAFE_DARK,
    }
    return palette_map[scheme]


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def is_dark_mode(scheme: ColorScheme) -> bool:
    """Check if the color scheme is dark mode."""
    return scheme in (ColorScheme.DARK_NORMAL, ColorScheme.DARK_HIGH)


def configure_plot_theme(plot_widget: pg.PlotWidget, scheme: ColorScheme):
    """Configure PyQtGraph plot widget theme based on color scheme."""
    dark = is_dark_mode(scheme)
    
    if dark:
        bg_color = '#1e1e1e'
        text_color = '#e0e0e0'
        axis_color = '#808080'
        grid_color = '#404040'
    else:
        bg_color = '#ffffff'
        text_color = '#000000'
        axis_color = '#000000'
        grid_color = '#d0d0d0'
    
    plot_widget.setBackground(bg_color)
    
    plot_item = plot_widget.getPlotItem()
    
    axis_pen = pg.mkPen(color=axis_color, width=1)
    for axis in ['left', 'bottom', 'right', 'top']:
        plot_item.getAxis(axis).setPen(axis_pen)
        plot_item.getAxis(axis).setTextPen(text_color)
    
    plot_item.showGrid(x=True, y=True, alpha=0.3)
    grid_pen = pg.mkPen(color=grid_color, width=1, style=pg.QtCore.Qt.PenStyle.DotLine)
    plot_item.getAxis('left').setGrid(128)
    plot_item.getAxis('bottom').setGrid(128)


def detect_outliers(values: List[float], n_std: float = 3.0) -> List[bool]:
    """Detect outliers using standard deviation method."""
    if len(values) < 3:
        return [False] * len(values)
    
    arr = np.array(values, dtype=float)
    
    valid_mask = ~np.isnan(arr)
    if valid_mask.sum() < 3:
        return [False] * len(values)
    
    mean = np.mean(arr[valid_mask])
    std = np.std(arr[valid_mask])
    
    if std == 0:
        return [False] * len(values)
    
    z_scores = np.abs((arr - mean) / std)
    outliers = z_scores > n_std
    
    outliers[~valid_mask] = False
    
    return outliers.tolist()


def get_grouped_data(
    measurements: List[Any],
    group_by_field: str
) -> Dict[str, List[Any]]:
    """
    Group measurements by a specified field.

    Supports nested fields like:
    - pia_serial -> sub_test.test_log.pia_board.serial_number
    - pia_part -> sub_test.test_log.pia_board.part_number
    - pmt_serial -> sub_test.test_log.pmt_device.pmt_serial_number
    - pmt_batch -> sub_test.test_log.pmt_device.batch_number
    - test_fixture -> sub_test.test_log.test_fixture
    """
    groups: Dict[str, List[Any]] = {}

    # Map friendly field names to actual attribute paths
    field_mapping = {
        'pia_serial': 'sub_test.test_log.pia_board.serial_number',
        'pia_part': 'sub_test.test_log.pia_board.part_number',
        'pmt_serial': 'sub_test.test_log.pmt_device.pmt_serial_number',
        'pmt_batch': 'sub_test.test_log.pmt_device.batch_number',
        'pmt_generation': 'sub_test.test_log.pmt_device.generation',
        'test_fixture': 'sub_test.test_log.test_fixture',
        'test_date': 'sub_test.test_log.created_at',
    }

    # Get the actual path
    actual_path = field_mapping.get(group_by_field, group_by_field)
    print(f"!!! get_grouped_data: field={group_by_field}, path={actual_path}")

    for measurement in measurements:
        value = measurement
        for attr in actual_path.split('.'):
            value = getattr(value, attr, None)
            if value is None:
                break

        group_key = str(value) if value is not None else "Unknown"

        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append(measurement)

    print(f"!!! get_grouped_data: created {len(groups)} groups: {list(groups.keys())}")
    return groups


def calculate_group_spacing(
    num_groups: int,
    total_range: float,
    spacing_fraction: float = 0.05
) -> float:
    """Calculate spacing between groups for visual separation."""
    if num_groups <= 1:
        return 0.0
    return total_range * spacing_fraction


def create_dashed_box_item(
    x_range: Tuple[float, float],
    y_range: Tuple[float, float],
    color: str = '#808080'
) -> pg.PlotDataItem:
    """Create a dashed box outline for grouping visualization."""
    x_min, x_max = x_range
    y_min, y_max = y_range

    x_coords = [x_min, x_max, x_max, x_min, x_min]
    y_coords = [y_min, y_min, y_max, y_max, y_min]

    pen = pg.mkPen(
        color=color,
        width=2,
        style=pg.QtCore.Qt.PenStyle.DashLine
    )

    return pg.PlotDataItem(
        x=x_coords,
        y=y_coords,
        pen=pen,
        connect='all'
    )


def calculate_point_size(num_points: int) -> float:
    """Calculate optimal point size based on number of data points."""
    if num_points <= 0:
        return 8.0

    if num_points <= 20:
        return 15.0
    elif num_points <= 50:
        return 12.0
    elif num_points <= 100:
        return 10.0
    elif num_points <= 200:
        return 8.0
    elif num_points <= 500:
        return 7.0
    elif num_points <= 1000:
        return 6.0
    else:
        return 5.0


def calculate_line_width(num_points: int) -> float:
    """Calculate optimal line width based on number of data points."""
    if num_points <= 0:
        return 2.0

    if num_points <= 20:
        return 3.5
    elif num_points <= 50:
        return 3.0
    elif num_points <= 100:
        return 2.5
    elif num_points <= 200:
        return 2.0
    elif num_points <= 500:
        return 1.8
    else:
        return 1.5


def calculate_bar_width(num_bins: int) -> float:
    """Calculate bar width scale factor for histograms."""
    if num_bins <= 0:
        return 0.8

    if num_bins <= 10:
        return 0.95
    elif num_bins <= 20:
        return 0.90
    elif num_bins <= 50:
        return 0.85
    elif num_bins <= 100:
        return 0.80
    elif num_bins <= 200:
        return 0.75
    else:
        return 0.70