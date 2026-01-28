"""
Database base configuration and shared declarative base.

This module provides:
- Single unified declarative base for all models
- Engine and session factory creation
- Database initialization

All model files MUST import Base from this module to ensure
proper foreign key relationships and metadata management.
"""
import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# ==============================================
# Single Source of Truth for Declarative Base
# ==============================================
Base = declarative_base()


# ==============================================
# Database Path Configuration
# ==============================================
def get_project_root():
    """Get project root directory (two levels up from this file)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def get_default_db_path():
    """Get default database path in data/ folder."""
    project_root = get_project_root()
    data_dir = os.path.join(project_root, "data")
    
    # Ensure data directory exists
    os.makedirs(data_dir, exist_ok=True)
    
    return os.path.join(data_dir, "Combined_database.db")


# Default database URL
DATABASE_URL = f"sqlite:///{get_default_db_path()}"


# ==============================================
# Engine and Session Factory Creation
# ==============================================
def get_engine(db_url=None, echo=False):
    """
    Create SQLAlchemy engine.
    
    Args:
        db_url: Database URL. If None, uses default path in data/
        echo: If True, log all SQL statements (useful for debugging)
    
    Returns:
        SQLAlchemy Engine instance
    """
    url = db_url or DATABASE_URL
    engine = create_engine(url, echo=echo)
    logger.info(f"Created engine for: {url}")
    return engine


def get_session_factory(db_url=None):
    """
    Create session factory (sessionmaker).
    
    Args:
        db_url: Database URL. If None, uses default.
    
    Returns:
        sessionmaker instance
    """
    engine = get_engine(db_url)
    return sessionmaker(bind=engine)


def init_database(db_url=None):
    """
    Initialize database by creating all tables defined in models.
    
    This must be called after all models are imported to ensure
    Base.metadata contains all table definitions.
    
    Args:
        db_url: Database URL. If None, uses default.
    """
    engine = get_engine(db_url)
    Base.metadata.create_all(engine)
    logger.info("Database initialized - all tables created")


# ==============================================
# Helper Functions
# ==============================================
def get_table_names():
    """Get list of all table names registered with Base."""
    return list(Base.metadata.tables.keys())


def drop_all_tables(db_url=None):
    """
    Drop all tables. USE WITH CAUTION!
    
    Args:
        db_url: Database URL. If None, uses default.
    """
    engine = get_engine(db_url)
    Base.metadata.drop_all(engine)
    logger.warning("All tables dropped!")
