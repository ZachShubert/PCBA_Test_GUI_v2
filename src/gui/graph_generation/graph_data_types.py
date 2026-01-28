"""
Data structures for graph module integration.

This module defines the dataclass used to pass measurement data
to the graph module, avoiding SQLAlchemy lazy loading issues.
"""

from dataclasses import dataclass
from typing import Optional, Any
from datetime import datetime


@dataclass
class Database_Full_Measurement_Result_Object:
    """
    Complete measurement data with all related objects.
    
    This dataclass contains a spec (measurement) and all its related
    database objects, loaded eagerly to avoid SQLAlchemy lazy loading issues.
    
    Attributes:
        spec: Spec object with measurement data
        sub_test: SubTest object (parent of spec)
        test_log: TestLog object (parent of sub_test)
        pia: PCBABoard object (parent of test_log)
        pmt: PMT object (parent of test_log, may be None)
    
    Examples:
        Creating from database query::
        
            for spec in session.query(Spec).all():
                result = Database_Full_Measurement_Result_Object(
                    spec=spec,
                    sub_test=spec.sub_test,
                    test_log=spec.sub_test.test_log,
                    pia=spec.sub_test.test_log.pia_board,
                    pmt=spec.sub_test.test_log.pmt_device
                )
    
    Notes:
        - All relationships are pre-loaded, no lazy loading occurs
        - PMT may be None for tests that don't use PMT devices
        - This structure matches your database query pattern
    """
    
    spec: Any  # Spec SQLAlchemy object
    sub_test: Any  # SubTest SQLAlchemy object
    test_log: Any  # TestLog SQLAlchemy object
    pia: Any  # PCBABoard SQLAlchemy object
    pmt: Optional[Any] = None  # PMT SQLAlchemy object (may be None)
    
    # Convenience properties for backward compatibility
    @property
    def id(self) -> int:
        """Spec ID."""
        return self.spec.id
    
    @property
    def name(self) -> str:
        """Spec name."""
        return self.spec.name
    
    @property
    def unit(self) -> str:
        """Measurement unit."""
        return self.spec.unit
    
    @property
    def measurement(self) -> float:
        """Measurement value."""
        return self.spec.measurement
    
    @property
    def measurement_type(self):
        """Measurement type enum."""
        return self.spec.measurement_type
    
    @property
    def has_plot(self) -> bool:
        """Whether this spec has plot data."""
        return self.spec.has_plot
    
    @property
    def plot_data(self) -> Optional[list]:
        """Plot data if available."""
        return getattr(self.spec, 'plot_data', None)
    
    @property
    def plot_image(self) -> Optional[bytes]:
        """Plot image binary data."""
        return self.spec.plot_image
    
    @property
    def lower_limit(self) -> Optional[float]:
        """Lower specification limit."""
        return self.spec.lower_limit
    
    @property
    def nominal(self) -> Optional[float]:
        """Nominal specification value."""
        return self.spec.nominal
    
    @property
    def upper_limit(self) -> Optional[float]:
        """Upper specification limit."""
        return self.spec.upper_limit
    
    @property
    def result(self) -> bool:
        """Pass/fail result."""
        return self.spec.result
    
    @property
    def created_at(self) -> datetime:
        """Timestamp of measurement."""
        return self.spec.created_at
    
    @property
    def sub_test_id(self) -> int:
        """SubTest ID."""
        return self.spec.sub_test_id


# Type alias for clarity
from typing import Any
MeasurementData = Database_Full_Measurement_Result_Object
