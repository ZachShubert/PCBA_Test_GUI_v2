"""
Measurement Graph Generation Module

This module provides comprehensive tools for generating interactive
visualizations of measurement data using PyQtGraph.

Main Components:
    - GraphConfig: Configuration dataclass for graph generation
    - GraphGenerationWorker: Background worker thread for async generation
    - MeasurementGraphGenerator: Main graph generation class
    - Utility functions: Color palettes, theme management, outlier detection

Examples:
    Basic usage::
    
        from graph_module import (
            GraphConfig, GraphType, ColorScheme,
            GraphGenerationWorker
        )
        
        config = GraphConfig(
            measurements=measurement_list,
            graph_type=GraphType.SCATTER,
            color_scheme=ColorScheme.DARK_NORMAL,
            show_spec_lines=True
        )
        
        worker = GraphGenerationWorker(config)
        worker.progress.connect(progress_bar.setValue)
        worker.finished.connect(display_plot)
        worker.start()

Author: Zach
Created: 2026
"""

from .graph_config import (
    GraphConfig,
    GraphType,
    ColorScheme,
    ComparisonMode
)

from .graph_worker import GraphGenerationWorker

from .graph_generator import MeasurementGraphGenerator

from .graph_utils import (
    get_color_palette,
    configure_plot_theme,
    detect_outliers,
    get_grouped_data,
    create_dashed_box_item,
    hex_to_rgb,
    is_dark_mode
)

__version__ = "3.0.0"

__all__ = [
    # Config
    'GraphConfig',
    'GraphType',
    'ColorScheme',
    'ComparisonMode',
    
    # Main classes
    'GraphGenerationWorker',
    'MeasurementGraphGenerator',
    
    # Utilities
    'get_color_palette',
    'configure_plot_theme',
    'detect_outliers',
    'get_grouped_data',
    'create_dashed_box_item',
    'hex_to_rgb',
    'is_dark_mode',
]
