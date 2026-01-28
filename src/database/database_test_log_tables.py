"""
Test log table models - TestLog, SubTest, and Spec.

These tables store the hierarchy of test results:
TestLog -> SubTest -> Spec (measurement)
"""
import enum
import json
from datetime import datetime

from sqlalchemy import Column, Integer, ForeignKey, String, Enum, Float, Boolean, LargeBinary, DateTime, Text
from sqlalchemy.orm import relationship

# Import unified Base from base.py
from src.database.base import Base


class MeasurementType(enum.Enum):
    """Enum for different types of measurements."""
    RANGE = "range"
    BOOLEAN = "boolean"
    PLOT = "plot"
    INT = "int"
    FLOAT = "float"


class Spec(Base):
    """
    Spec (Specification/Measurement) model.

    Stores individual measurements and their pass/fail results.
    Each spec belongs to a SubTest.
    """
    __tablename__ = 'spec'

    id = Column(Integer, primary_key=True, autoincrement=True)
    sub_test_id = Column(Integer, ForeignKey('sub_test.id'), nullable=False)
    name = Column(String)
    unit = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    measurement_type = Column(Enum(MeasurementType), nullable=False)
    measurement = Column(Float)
    has_plot = Column(Boolean)
    plot_image = Column(LargeBinary, nullable=True)

    # Plot line data stored as JSON string
    # Format: {"x": [x1, x2, ...], "y": [y1, y2, ...], "label": "Series Name"}
    # Or for multiple series: [{"x": [...], "y": [...], "label": "..."}, ...]
    plot_data = Column(Text, nullable=True)

    lower_limit = Column(Float)
    nominal = Column(Float)
    upper_limit = Column(Float)
    result = Column(Boolean)

    # Relationship to parent SubTest
    sub_test = relationship("SubTest", back_populates="specs")

    def get_plot_data(self):
        """
        Get plot data as Python object.

        Returns:
            dict or list of dicts with x, y, label keys, or None
        """
        if self.plot_data:
            try:
                return json.loads(self.plot_data)
            except json.JSONDecodeError:
                return None
        return None

    def set_plot_data(self, data):
        """
        Set plot data from Python object.

        Args:
            data: dict or list of dicts with x, y data
        """
        if data is not None:
            self.plot_data = json.dumps(data)
        else:
            self.plot_data = None


class subtestType(enum.Enum):
    """Enum for different types of subtests."""
    i2c_test_name = 'PIA I2C Test Results'
    eeprom_test_name = 'EEPROM Test Results'
    voltage_test_name = 'PIA Read Voltage Test Results'
    temperature_test_name = 'PIA Read Temperature Test Results'
    logAmp_test_name = 'PIA Log Ampere Calibration Test Results'
    senseAmp_test_name = 'PIA Sense Ampere Calibration Test Results'
    cathodeCurrent_test_name = 'PIA Cathode Current Test Results'


class SubTest(Base):
    """
    SubTest model.

    Groups related measurements (specs) together.
    Each SubTest belongs to a TestLog and contains multiple Specs.
    """
    __tablename__ = 'sub_test'

    id = Column(Integer, primary_key=True, autoincrement=True)
    test_log_id = Column(Integer, ForeignKey('test_log.id'), nullable=False)
    name = Column(String)
    description = Column(String)
    generation_project = Column(String)
    script_version = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    test_log = relationship("TestLog", back_populates="sub_tests")
    specs = relationship("Spec", back_populates="sub_test")


class TestLog(Base):
    """
    TestLog model.

    Top-level test record. Each TestLog represents one complete test run
    of a PCBA board (and optionally a PMT device).
    """
    __tablename__ = 'test_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    pia_board_id = Column(Integer, ForeignKey('pia_board.id'), nullable=False)
    pmt_id = Column(Integer, ForeignKey('pmt_device.id'), nullable=True)
    name = Column(String)
    description = Column(String)
    generation_project = Column(String)
    script_version = Column(String)
    test_fixture = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    full_test_completed = Column(Boolean, default=False)
    full_test_passed = Column(Boolean, default=False)
    html_path = Column(String, unique=True)
    html_content = Column(String, unique=True)
    html_hash = Column(LargeBinary(32), unique=True)  # sha256 digest

    # Relationships
    pia_board = relationship("PCBABoard", back_populates="test_logs")
    pmt_device = relationship("PMT", back_populates="test_logs")
    sub_tests = relationship("SubTest", back_populates="test_log")