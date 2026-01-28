"""
Background worker thread for graph generation.

This module provides a QThread-based worker that generates graphs
in the background while emitting progress updates.
"""

from PyQt6.QtCore import QThread, pyqtSignal
import pyqtgraph as pg
from typing import Optional
import traceback

from .graph_config import GraphConfig
from .graph_generator import MeasurementGraphGenerator


class GraphGenerationWorker(QThread):
    """
    Worker thread for background graph generation.
    
    This QThread subclass generates measurement graphs in a background
    thread to prevent UI blocking. It emits progress updates and the
    final plot widget upon completion.
    
    Signals:
        progress: Emitted with progress percentage (0-100)
        finished: Emitted with completed PlotWidget when successful
        error: Emitted with error message string if generation fails
    """
    
    progress = pyqtSignal(int)
    finished = pyqtSignal(object)  # pg.PlotWidget
    error = pyqtSignal(str)
    
    def __init__(self, config: GraphConfig):
        """
        Initialize the graph generation worker.
        
        Args:
            config: GraphConfig object with all generation parameters
        """
        super().__init__()
        self.config = config
        self.generator: Optional[MeasurementGraphGenerator] = None
    
    def run(self):
        """
        Execute graph generation in background thread.
        
        This method is called automatically when start() is invoked.
        It handles all stages of graph generation and emits appropriate
        signals for progress, completion, or errors.
        """
        try:
            self.progress.emit(0)
            
            # Initialize generator
            self.generator = MeasurementGraphGenerator(self.config)
            self.progress.emit(10)
            
            # Prepare data
            self.generator.prepare_data()
            self.progress.emit(20)
            
            # Create plot widget
            plot_widget = self.generator.create_plot_widget()
            self.progress.emit(40)
            
            # Generate plot
            self.generator.plot_data(plot_widget)
            self.progress.emit(60)
            
            # Apply styling
            self.generator.apply_styling(plot_widget)
            self.progress.emit(80)
            
            # Setup interactivity
            self.generator.setup_interactivity(plot_widget)
            self.progress.emit(90)
            
            # Complete
            self.progress.emit(100)
            self.finished.emit(plot_widget)
            
        except Exception as e:
            error_msg = f"Graph generation failed: {str(e)}\n\n"
            error_msg += traceback.format_exc()
            self.error.emit(error_msg)
    
    def stop(self):
        """Request the worker to stop gracefully."""
        self.requestInterruption()
        self.quit()
