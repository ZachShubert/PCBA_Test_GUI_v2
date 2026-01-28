"""
Graph configuration module for measurement data visualization.

This module provides the configuration dataclass used to specify
all parameters for graph generation.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict, Callable
from enum import Enum


class GraphType(Enum):
    """
    Enumeration of supported graph types.
    
    Attributes:
        SCATTER: Scatter plot with individual points
        LINE: Line plot connecting sequential points
        HISTOGRAM: Distribution histogram of values
    """
    SCATTER = "scatter"
    LINE = "line"
    HISTOGRAM = "histogram"


class ColorScheme(Enum):
    """
    Enumeration of supported color schemes.
    
    Attributes:
        LIGHT_NORMAL: Light mode with normal contrast (Tableau)
        LIGHT_HIGH: Light mode with high contrast (colorblind-safe)
        DARK_NORMAL: Dark mode with normal contrast (Tableau)
        DARK_HIGH: Dark mode with high contrast (colorblind-safe)
    """
    LIGHT_NORMAL = "light_normal"
    LIGHT_HIGH = "light_high"
    DARK_NORMAL = "dark_normal"
    DARK_HIGH = "dark_high"


class ComparisonMode(Enum):
    """
    Enumeration of comparison modes for X/Y axis selection.
    
    Attributes:
        NONE: Standard time-series or distribution plot
        SAME_MEASUREMENT: Compare same measurement across different conditions
        DIFFERENT_MEASUREMENTS: Compare two different measurements
    """
    NONE = "none"
    SAME_MEASUREMENT = "same_measurement"
    DIFFERENT_MEASUREMENTS = "different_measurements"


@dataclass
class GraphConfig:
    """
    Configuration for measurement graph generation.
    
    This dataclass encapsulates all parameters needed to generate
    a graph from measurement data, including visual styling,
    filtering, and comparison options.
    
    V4 Features:
        - Click-to-show tooltips (not hover)
        - Styled tooltips with solid background
        - Integer X-axis for scatter plots
        - Fixed axis margins (10%)
        - Auto-overlay plot measurements
        - Full-height colored grouping boxes
        - Unified context menu
        - Device-based pairing for comparison
        - Diagonal comparison line
        - Styled legend
        - Fixed prepare_data for comparison mode
    
    Attributes:
        measurements: List of SQLAlchemy Measurement objects to plot
        graph_type: Type of graph to generate
        color_scheme: Color scheme for the graph
        show_spec_lines: Whether to draw upper/lower specification lines
        show_legend: Whether to display the legend
        legend_position: Position of legend ('top-left', 'top-right', 'bottom-left', 'bottom-right')
        legend_bg_opacity: Legend background opacity (0-255)
        legend_border_width: Legend border width in pixels
        enable_grouping_boxes: Whether to draw boxes around grouped data
        group_by_field: Field name to group data by (e.g., 'pia_serial', 'pmt_batch')
        comparison_mode: Type of comparison to perform
        x_axis_measurement: Measurement name for X-axis (comparison mode)
        y_axis_measurement: Measurement name for Y-axis (comparison mode)
        x_axis_field: Field to use for X-axis in standard mode or comparison grouping
        y_axis_field: Field to use for Y-axis in comparison grouping
        x_axis_use_indices: Use integer indices for X-axis (scatter plots only)
        axis_margin_percent: Percentage margin for axis ranges (default 10%)
        show_comparison_line: Show y=x diagonal line in comparison mode
        pairing_device: Device type for comparison pairing ('pia' or 'pmt')
        pairing_strategy: Strategy for device pairing ('first', 'last', 'best')
        auto_overlay_plots: Automatically overlay plot-type measurements
        remove_outliers: Whether to filter outliers (>3 std dev)
        title: Optional graph title
        x_label: Optional X-axis label
        y_label: Optional Y-axis label
        point_info_callback: Optional callback function to get custom point info dict
        enable_point_deletion: Whether to enable right-click point deletion
        enable_tooltips: Whether to show tooltips
        enable_hover_highlight: Whether to highlight points on hover
        enable_crosshair: Whether to show crosshair cursor
        enable_size_scaling: Whether to scale point/bar sizes based on data count
    """
    
    measurements: List[Any] = field(default_factory=list)
    graph_type: GraphType = GraphType.SCATTER
    color_scheme: ColorScheme = ColorScheme.LIGHT_NORMAL
    
    # Visual options
    show_spec_lines: bool = True
    show_legend: bool = True
    legend_position: str = 'top-right'  # V4: Legend positioning
    legend_bg_opacity: int = 235  # V4: Legend background opacity (0-255)
    legend_border_width: float = 2.0  # V4: Legend border width
    enable_grouping_boxes: bool = False
    group_by_field: Optional[str] = None
    
    # Comparison mode
    comparison_mode: ComparisonMode = ComparisonMode.NONE
    x_axis_measurement: Optional[str] = None
    y_axis_measurement: Optional[str] = None
    
    # Axis configuration
    x_axis_field: str = "created_at"  # Default to timestamp, or grouping field for comparison
    y_axis_field: Optional[str] = None  # For comparison mode grouping
    x_axis_use_indices: bool = True  # V4: Use integer X positions for scatter (prevents overlap)
    axis_margin_percent: float = 10.0  # V4: Fixed axis margin percentage
    
    # Comparison enhancements - V4
    show_comparison_line: bool = True  # V4: Show y=x diagonal line
    pairing_device: str = 'pia'  # V4: 'pia' or 'pmt' for device-based pairing
    pairing_strategy: str = 'last'  # V4: 'first', 'last', or 'best'
    
    # Plot overlay - V4
    auto_overlay_plots: bool = True  # V4: Automatically overlay plot-type measurements
    
    # Data filtering
    remove_outliers: bool = False
    
    # Labels
    title: Optional[str] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    
    # Interactive features
    point_info_callback: Optional[Callable[[Any], Dict[str, str]]] = None
    enable_point_deletion: bool = True
    enable_tooltips: bool = True  # V4: Tooltips on click (not hover)
    enable_hover_highlight: bool = True  # V4: Highlight on hover
    enable_crosshair: bool = True  # V4: Show crosshair cursor
    enable_size_scaling: bool = True
    
    # Grid options
    grid_alpha: float = 0.3  # Grid line opacity (0.0-1.0)
    grid_density: str = 'normal'  # 'sparse', 'normal', 'dense'

    def __post_init__(self):
        """
        Validate configuration after initialization.

        Raises:
            ValueError: If configuration is invalid
        """
        if self.comparison_mode != ComparisonMode.NONE:
            if not self.x_axis_measurement:
                raise ValueError(
                    "Comparison mode requires x_axis_measurement to be specified"
                )

            # For SAME_MEASUREMENT mode, y_axis_measurement should match x_axis_measurement
            if self.comparison_mode == ComparisonMode.SAME_MEASUREMENT:
                if self.y_axis_measurement and self.y_axis_measurement != self.x_axis_measurement:
                    raise ValueError(
                        "SAME_MEASUREMENT mode requires y_axis_measurement to match x_axis_measurement "
                        "(or be None, it will be set automatically)"
                    )
                # Auto-set y_axis_measurement to match x
                self.y_axis_measurement = self.x_axis_measurement

            # For DIFFERENT_MEASUREMENTS mode, both must be specified
            elif self.comparison_mode == ComparisonMode.DIFFERENT_MEASUREMENTS:
                if not self.y_axis_measurement:
                    raise ValueError(
                        "DIFFERENT_MEASUREMENTS mode requires both x_axis_measurement "
                        "and y_axis_measurement to be specified"
                    )

        if self.enable_grouping_boxes and not self.group_by_field:
            raise ValueError(
                "Grouping boxes enabled but no group_by_field specified"
            )

        # Validate pairing device
        if self.pairing_device not in ('pia', 'pmt'):
            raise ValueError(
                f"pairing_device must be 'pia' or 'pmt', got '{self.pairing_device}'"
            )

        # Validate pairing strategy
        if self.pairing_strategy not in ('first', 'last', 'best'):
            raise ValueError(
                f"pairing_strategy must be 'first', 'last', or 'best', got '{self.pairing_strategy}'"
            )

        # Validate legend position
        valid_positions = ['top-left', 'top-right', 'bottom-left', 'bottom-right']
        if self.legend_position not in valid_positions:
            raise ValueError(
                f"legend_position must be one of {valid_positions}, got '{self.legend_position}'"
            )

        # Validate opacity
        if not (0 <= self.legend_bg_opacity <= 255):
            raise ValueError(
                f"legend_bg_opacity must be between 0 and 255, got {self.legend_bg_opacity}"
            )