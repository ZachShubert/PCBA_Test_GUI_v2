#!/usr/bin/env python3
"""
Test script to verify database layer is working correctly.

This version handles existing data and provides options to:
1. Test with existing database
2. Create fresh test database
"""
import sys
import os
import argparse
from datetime import datetime
import random

# Add src to path so we can import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.database import DatabaseManager, PCBABoard, PMT, TestLog, SubTest, Spec, MeasurementType


def clear_test_data(db):
    """Delete all test data (TEST_* and BULK_* entries)."""
    print("\n" + "=" * 60)
    print("CLEARING TEST DATA")
    print("=" * 60)

    with db.session_scope() as session:
        # Delete test boards
        test_boards = session.query(PCBABoard).filter(
            PCBABoard.serial_number.like('TEST_%') |
            PCBABoard.serial_number.like('BULK_%')
        ).all()

        for board in test_boards:
            session.delete(board)

        # Delete test PMTs
        test_pmts = session.query(PMT).filter(
            PMT.pmt_serial_number.like('PMT_TEST_%')
        ).all()

        for pmt in test_pmts:
            session.delete(pmt)

        print(f"✓ Deleted {len(test_boards)} test boards")
        print(f"✓ Deleted {len(test_pmts)} test PMTs")


def test_database_initialization():
    """Test 1: Database initialization."""
    print("\n" + "=" * 60)
    print("TEST 1: Database Initialization")
    print("=" * 60)

    db = DatabaseManager()
    print(f"✓ DatabaseManager created")
    print(f"  Database location: {db.db_url}")

    stats = db.get_database_stats()
    print(f"✓ Initial stats retrieved:")
    for key, value in stats.items():
        print(f"  - {key}: {value}")

    return db


def test_adding_data(db):
    """Test 2: Adding data using context manager."""
    print("\n" + "=" * 60)
    print("TEST 2: Adding Data (Context Manager)")
    print("=" * 60)

    # Generate unique serial numbers using timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    board_serial = f"TEST_BOARD_{timestamp}"
    pmt_serial = f"PMT_TEST_{timestamp}"

    # Add PCBA board
    with db.session_scope() as session:
        board = PCBABoard(
            serial_number=board_serial,
            part_number="PN-12345",
            generation_project="Gen3",
            version="v1.0"
        )
        session.add(board)
        print(f"✓ Added PCBA Board: {board.serial_number}")

    # Add PMT
    with db.session_scope() as session:
        pmt = PMT(
            pmt_serial_number=pmt_serial,
            generation="Gen2",
            batch_number="BATCH_A"
        )
        session.add(pmt)
        print(f"✓ Added PMT: {pmt.pmt_serial_number}")

    # Verify they were added
    stats = db.get_database_stats()
    print(f"✓ Updated stats:")
    print(f"  - Total boards: {stats['total_boards']}")
    print(f"  - Total PMTs: {stats['total_pmts']}")

    return board_serial, pmt_serial


def test_add_test_log(db, board_serial, pmt_serial):
    """Test 3: Adding a complete test log with hierarchy."""
    print("\n" + "=" * 60)
    print("TEST 3: Adding Test Log Hierarchy")
    print("=" * 60)

    with db.session_scope() as session:
        # Query board and PMT within the same session to avoid detached instance issues
        board = session.query(PCBABoard).filter(
            PCBABoard.serial_number == board_serial
        ).first()
        pmt = session.query(PMT).filter(
            PMT.pmt_serial_number == pmt_serial
        ).first()

        if not board or not pmt:
            print("✗ Could not find board or PMT!")
            return

        # Create test log
        test_log = TestLog(
            pia_board_id=board.id,
            pmt_id=pmt.id,
            name="Full System Test",
            description="Complete test of board and PMT",
            generation_project="Gen3",
            script_version="v1.0",
            test_fixture="Test Fixture A",
            full_test_completed=True,
            full_test_passed=True,
            html_path=f"/logs/test_{board_serial}.html",
            html_content="<html>Test Results</html>",
            html_hash=f"hash_{board_serial}_{datetime.now().timestamp()}".encode()[:32]
        )
        session.add(test_log)
        session.flush()  # Get the ID
        print(f"✓ Added TestLog: {test_log.name}")

        # Create subtest
        subtest = SubTest(
            test_log_id=test_log.id,
            name="Voltage Test",
            description="Test output voltages",
            generation_project="Gen3",
            script_version="v1.0"
        )
        session.add(subtest)
        session.flush()
        print(f"✓ Added SubTest: {subtest.name}")

        # Create specs (measurements)
        specs = [
            Spec(
                sub_test_id=subtest.id,
                name="Output Voltage 5V",
                unit="V",
                measurement_type=MeasurementType.RANGE,
                measurement=5.02,
                lower_limit=4.95,
                nominal=5.0,
                upper_limit=5.05,
                result=True
            ),
            Spec(
                sub_test_id=subtest.id,
                name="Output Voltage 3.3V",
                unit="V",
                measurement_type=MeasurementType.RANGE,
                measurement=3.28,
                lower_limit=3.25,
                nominal=3.3,
                upper_limit=3.35,
                result=True
            ),
        ]
        session.add_all(specs)
        print(f"✓ Added {len(specs)} Specs (measurements)")

    stats = db.get_database_stats()
    print(f"✓ Updated stats:")
    print(f"  - Total test logs: {stats['total_test_logs']}")
    print(f"  - Completed tests: {stats['completed_tests']}")
    print(f"  - Passed tests: {stats['passed_tests']}")


def test_query_interface(db):
    """Test 4: Using the query interface."""
    print("\n" + "=" * 60)
    print("TEST 4: Query Interface")
    print("=" * 60)

    # Test queries.pias
    board_serials = db.queries.pias.get_all_serial_numbers()
    print(f"✓ Board serial numbers: {len(board_serials)} found")
    if board_serials:
        print(f"  Sample: {board_serials[:3]}")

    # Test queries.pmts
    pmt_serials = db.queries.pmts.get_all_serial_numbers()
    print(f"✓ PMT serial numbers: {len(pmt_serials)} found")
    if pmt_serials:
        print(f"  Sample: {pmt_serials[:3]}")

    # Test queries.specs
    spec_names = db.queries.specs.get_all_spec_names()
    print(f"✓ Spec names: {len(spec_names)} found")
    if spec_names:
        print(f"  Sample: {spec_names[:3]}")

    # Test queries.test_logs
    recent_logs = db.queries.test_logs.get_recent(limit=10)
    print(f"✓ Recent test logs: {len(recent_logs)} found")
    for log in recent_logs[:3]:  # Show first 3
        print(f"  - {log.name} ({log.test_fixture})")


def test_convenience_methods(db, board_serial, pmt_serial):
    """Test 5: Convenience methods."""
    print("\n" + "=" * 60)
    print("TEST 5: Convenience Methods")
    print("=" * 60)

    # Test within session to avoid detached instances
    with db.session_scope() as session:
        # Find board by serial
        board = session.query(PCBABoard).filter(
            PCBABoard.serial_number == board_serial
        ).first()

        if board:
            print(f"✓ Found board: {board.serial_number}")
            print(f"  - Part number: {board.part_number}")
            print(f"  - Generation: {board.generation_project}")
        else:
            print(f"✗ Could not find board: {board_serial}")

        # Find PMT by serial
        pmt = session.query(PMT).filter(
            PMT.pmt_serial_number == pmt_serial
        ).first()

        if pmt:
            print(f"✓ Found PMT: {pmt.pmt_serial_number}")
            print(f"  - Generation: {pmt.generation}")
            print(f"  - Batch: {pmt.batch_number}")
        else:
            print(f"✗ Could not find PMT: {pmt_serial}")

    # Test convenience method (it handles its own session)
    board_check = db.find_board_by_serial(board_serial)
    if board_check:
        print(f"✓ Convenience method find_board_by_serial() works")

    # Search
    results = db.search("TEST")
    print(f"✓ Search for 'TEST': {len(results)} results")


def test_bulk_operations(db):
    """Test 6: Bulk operations."""
    print("\n" + "=" * 60)
    print("TEST 6: Bulk Operations")
    print("=" * 60)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create multiple boards
    boards = [
        PCBABoard(
            serial_number=f"BULK_BOARD_{timestamp}_{i:03d}",
            part_number="PN-BULK",
            generation_project="Gen3",
            version="v1.0"
        )
        for i in range(5)
    ]

    db.bulk_add(boards)
    print(f"✓ Added {len(boards)} boards in bulk")

    stats = db.get_database_stats()
    print(f"✓ Total boards now: {stats['total_boards']}")


def test_worker_session(db):
    """Test 7: Manual session for workers."""
    print("\n" + "=" * 60)
    print("TEST 7: Manual Session (for Workers)")
    print("=" * 60)

    session = db.get_new_session()
    try:
        boards = session.query(PCBABoard).limit(3).all()
        print(f"✓ Queried {len(boards)} boards using manual session:")
        for board in boards:
            print(f"  - {board.serial_number}")
    finally:
        session.close()
        print(f"✓ Session closed manually")


def test_context_manager(db):
    """Test 8: DatabaseManager as context manager."""
    print("\n" + "=" * 60)
    print("TEST 8: Context Manager Pattern")
    print("=" * 60)

    # Test using DatabaseManager with 'with' statement
    with db as db_context:
        stats = db_context.get_database_stats()
        print(f"✓ Used DatabaseManager as context manager")
        print(f"  - Total boards: {stats['total_boards']}")

    print(f"✓ DatabaseManager auto-closed")


def main():
    """Run all tests."""
    parser = argparse.ArgumentParser(description='Test database layer')
    parser.add_argument('--clear', action='store_true',
                        help='Clear test data before running tests')
    parser.add_argument('--existing', action='store_true',
                        help='Test with existing database data')
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("DATABASE LAYER TEST SUITE")
    print("=" * 60)

    try:
        # Test 1: Initialize
        db = test_database_initialization()

        # Optionally clear test data
        if args.clear:
            clear_test_data(db)

        if not args.existing:
            # Test 2: Add new data
            board_serial, pmt_serial = test_adding_data(db)

            # Test 3: Add complex hierarchy
            test_add_test_log(db, board_serial, pmt_serial)

            # Test 5: Convenience methods (with known serials)
            test_convenience_methods(db, board_serial, pmt_serial)

            # Test 6: Bulk operations
            test_bulk_operations(db)
        else:
            print("\n✓ Skipping data creation (--existing flag set)")

        # Test 4: Query interface (works with any data)
        test_query_interface(db)

        # Test 7: Worker sessions
        test_worker_session(db)

        # Test 8: Context manager
        test_context_manager(db)

        # Final stats
        print("\n" + "=" * 60)
        print("FINAL DATABASE STATISTICS")
        print("=" * 60)
        stats = db.get_database_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")

        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)

        # Clean up
        db.close()
        print("\n✓ Database manager closed")

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())