"""
Device table models - PMT and PCBA Board.

These tables store device information that is tested.
Each device can have multiple test logs associated with it.
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

# Import unified Base from base.py
from src.database.base import Base


class PMT(Base):
    """
    PMT (PhotoMultiplier Tube) Device model.
    
    Stores information about PMT devices being tested.
    Each PMT can have multiple test logs.
    """
    __tablename__ = 'pmt_device'

    id = Column(Integer, primary_key=True, autoincrement=True)
    pmt_serial_number = Column(String, nullable=True)
    generation = Column(String)
    batch_number = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to test logs
    test_logs = relationship("TestLog", back_populates="pmt_device")


class PCBABoard(Base):
    """
    PCBA (Printed Circuit Board Assembly) Board model.
    
    Stores information about PCBA boards being tested.
    Each board can have multiple test logs.
    """
    __tablename__ = 'pia_board'

    id = Column(Integer, primary_key=True, autoincrement=True)
    serial_number = Column(String, unique=True, nullable=False)
    part_number = Column(String)
    generation_project = Column(String)
    version = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to test logs
    test_logs = relationship("TestLog", back_populates="pia_board")
