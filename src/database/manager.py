"""
Database Manager - Single point of database access.

This module provides the DatabaseManager class which handles:
- Thread-safe session management
- High-level query interface
- Transaction management
- Database initialization

Usage:
    # Create manager instance
    db_manager = DatabaseManager()

    # Option 1: Use the queries interface (automatic session management)
    boards = db_manager.queries.pias.get_all_serial_numbers()
    
    # Option 2: Use context manager for transactions
    with db_manager.session_scope() as session:
        board = PCBABoard(serial_number="TEST001")
        session.add(board)
    # Automatically commits when exiting 'with' block
    
    # Option 3: Get new session for workers
    session = db_manager.get_new_session()
    try:
        # Do work...
        session.commit()
    finally:
        session.close()
"""
import logging
from contextlib import contextmanager
from typing import Optional, List, Any
from sqlalchemy.orm import Session, scoped_session
from sqlalchemy import func

from src.database.base import get_session_factory, init_database, get_default_db_path
from src.database.database_queries import Queries
from src.database.database_device_tables import PMT, PCBABoard
from src.database.database_test_log_tables import TestLog, SubTest, Spec

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections and provides high-level query interface.
    
    Thread-safe using scoped_session. Can be injected into GUI components.
    
    Features:
    - Option A: Context manager for safe transactions
    - Option B: High-level query interface with automatic session management
    - Option C: Manual session creation for workers
    
    Attributes:
        db_url: Database file path
        queries: High-level query interface (Queries object)
    """
    
    def __init__(self, db_url: Optional[str] = None):
        """
        Initialize database manager.
        
        Args:
            db_url: Optional database URL. If None, uses default path in data/ folder.
        """
        self.db_url = db_url or f"sqlite:///{get_default_db_path()}"
        
        # Create session factory
        self._session_factory = get_session_factory(self.db_url)
        
        # Scoped session for thread safety
        # Each thread gets its own session automatically
        self._scoped_session = scoped_session(self._session_factory)
        
        # High-level query interface (lazy initialized)
        self._queries = None
        
        # Initialize database tables
        init_database(self.db_url)
        
        logger.info(f"DatabaseManager initialized: {self.db_url}")
    
    @property
    def queries(self) -> Queries:
        """
        Access to high-level query interface.
        
        Creates session automatically and manages it internally.
        Use this for simple read operations.
        
        Example:
            serial_numbers = db_manager.queries.pias.get_all_serial_numbers()
            test_logs = db_manager.queries.test_logs.get_recent(limit=50)
        
        Returns:
            Queries object with access to all query methods
        """
        if self._queries is None:
            session = self._scoped_session()
            self._queries = Queries(session)
        return self._queries
    
    @contextmanager
    def session_scope(self):
        """
        Provide a transactional scope for database operations.
        
        Automatically commits on success and rolls back on error.
        Use this when you need to perform multiple operations in a transaction.
        
        Example:
            with db_manager.session_scope() as session:
                board = PCBABoard(serial_number="TEST001")
                session.add(board)
                
                pmt = PMT(pmt_serial_number="PMT123")
                session.add(pmt)
            # Automatically commits here
        
        Yields:
            SQLAlchemy Session object
        """
        session: Session = self._scoped_session()
        try:
            yield session
            session.commit()
            logger.debug("Transaction committed")
        except Exception as e:
            session.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")
            raise
        finally:
            session.close()
    
    def get_new_session(self) -> Session:
        """
        Get a new session for manual management.
        
        Use this in workers or when you need fine-grained control.
        Caller is responsible for closing the session.
        
        Example:
            session = db_manager.get_new_session()
            try:
                results = session.query(PCBABoard).all()
                session.commit()
            finally:
                session.close()
        
        Returns:
            New SQLAlchemy Session object
        """
        return self._session_factory()
    
    # ============================================================
    # Convenience Methods (Commonly used operations)
    # ============================================================
    
    def add_and_commit(self, obj: Any):
        """
        Add single object and commit immediately.
        
        Args:
            obj: SQLAlchemy model instance to add
        
        Example:
            board = PCBABoard(serial_number="TEST001")
            db_manager.add_and_commit(board)
        """
        with self.session_scope() as session:
            session.add(obj)
    
    def bulk_add(self, objects: List[Any]):
        """
        Add multiple objects in single transaction.
        
        Args:
            objects: List of SQLAlchemy model instances
        
        Example:
            boards = [PCBABoard(serial_number=f"TEST{i}") for i in range(10)]
            db_manager.bulk_add(boards)
        """
        with self.session_scope() as session:
            session.bulk_save_objects(objects)
    
    def delete_and_commit(self, obj: Any):
        """
        Delete object and commit immediately.
        
        Args:
            obj: SQLAlchemy model instance to delete
        """
        with self.session_scope() as session:
            session.delete(obj)
    
    # ============================================================
    # Common Query Shortcuts
    # ============================================================
    
    def find_board_by_serial(self, serial_number: str) -> Optional[PCBABoard]:
        """
        Find PCBA board by serial number.
        
        Args:
            serial_number: Board serial number
            
        Returns:
            PCBABoard instance or None if not found
        """
        session = self.get_new_session()
        try:
            board = session.query(PCBABoard).filter(
                PCBABoard.serial_number == serial_number
            ).first()
            if board:
                # Make instance independent of session
                session.expunge(board)
            return board
        finally:
            session.close()

    def find_pmt_by_serial(self, serial_number: str) -> Optional[PMT]:
        """
        Find PMT by serial number.

        Args:
            serial_number: PMT serial number

        Returns:
            PMT instance or None if not found
        """
        session = self.get_new_session()
        try:
            pmt = session.query(PMT).filter(
                PMT.pmt_serial_number == serial_number
            ).first()
            if pmt:
                # Make instance independent of session
                session.expunge(pmt)
            return pmt
        finally:
            session.close()

    def get_recent_test_logs(self, limit: int = 100) -> List[TestLog]:
        """
        Get most recent test logs.

        Args:
            limit: Maximum number of logs to return

        Returns:
            List of TestLog instances
        """
        return self.queries.test_logs.get_recent(limit)

    def get_test_log_html(self, test_log_id: int) -> Optional[str]:
        """
        Get HTML content for a test log.

        Args:
            test_log_id: Test log ID

        Returns:
            HTML content string or None
        """
        return self.queries.test_logs.get_html_content_from_id(test_log_id)

    def search(self, search_term: str) -> List[TestLog]:
        """
        Search across PCBA and PMT identifiers.

        Args:
            search_term: String to search for

        Returns:
            List of matching TestLog instances
        """
        return self.queries.find_matching_string(search_term)

    # ============================================================
    # Statistics / Dashboard Methods
    # ============================================================

    def get_database_stats(self) -> dict:
        """
        Get overview statistics for dashboard.

        Returns:
            Dictionary with counts:
            - total_boards: Number of PCBA boards
            - total_pmts: Number of PMTs
            - total_test_logs: Total test logs
            - completed_tests: Number of completed tests
            - passed_tests: Number of passed tests
        """
        with self.session_scope() as session:
            return {
                'total_boards': session.query(func.count(PCBABoard.id)).scalar() or 0,
                'total_pmts': session.query(func.count(PMT.id)).scalar() or 0,
                'total_test_logs': session.query(func.count(TestLog.id)).scalar() or 0,
                'completed_tests': session.query(func.count(TestLog.id)).filter(
                    TestLog.full_test_completed == True
                ).scalar() or 0,
                'passed_tests': session.query(func.count(TestLog.id)).filter(
                    TestLog.full_test_passed == True
                ).scalar() or 0,
            }

    def get_all_board_serial_numbers(self) -> List[str]:
        """Get all PCBA board serial numbers."""
        return self.queries.pias.get_all_serial_numbers()

    def get_all_pmt_serial_numbers(self) -> List[str]:
        """Get all PMT serial numbers."""
        return self.queries.pmts.get_all_serial_numbers()

    def get_all_spec_names(self) -> List[str]:
        """Get all unique spec names."""
        return self.queries.specs.get_all_spec_names()

    # ============================================================
    # Lifecycle Management
    # ============================================================

    def close(self):
        """
        Clean up database connections.

        Call this when shutting down the application.
        """
        self._scoped_session.remove()
        logger.info("DatabaseManager closed - all sessions removed")

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support - cleanup on exit."""
        self.close()