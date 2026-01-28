"""
Database package - Unified database access layer.

This package provides:
- DatabaseManager: Main interface for database operations
- Model classes: PMT, PCBABoard, TestLog, SubTest, Spec, Manufacturer
- Query classes: High-level query interface
- Utility functions: Helper functions for common operations

Usage:
    from src.database import DatabaseManager

    db = DatabaseManager()
    boards = db.queries.pias.get_all_serial_numbers()
"""

# Import main components for easy access
from src.database.manager import DatabaseManager
from src.database.database_device_tables import PMT, PCBABoard
from src.database.database_test_log_tables import TestLog, SubTest, Spec, MeasurementType
from src.database.database_manufacturer_tables import (
    Manufacturer, ManufacturerSpec, ManufacturerDeviceBatch, ManufacturerExcelImporter
)
from src.database.base import Base, init_database

# Define what's exported when doing "from src.database import *"
__all__ = [
    'DatabaseManager',
    'PMT',
    'PCBABoard',
    'TestLog',
    'SubTest',
    'Spec',
    'MeasurementType',
    'Manufacturer',
    'ManufacturerSpec',
    'ManufacturerDeviceBatch',
    'ManufacturerExcelImporter',
    'Base',
    'init_database',
]