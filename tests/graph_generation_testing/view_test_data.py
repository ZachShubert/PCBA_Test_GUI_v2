#!/usr/bin/env python3
"""
Database Data Viewer

View and verify test data in the database.
Useful for checking what data exists before graphing.
"""
import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.database import DatabaseManager


def show_summary(db: DatabaseManager):
    """Show database summary statistics."""
    print("\n" + "="*60)
    print("DATABASE SUMMARY")
    print("="*60)
    
    stats = db.get_database_stats()
    print(f"\nOverall Statistics:")
    print(f"  Total PCBA Boards: {stats['total_boards']}")
    print(f"  Total PMT Devices: {stats['total_pmts']}")
    print(f"  Total Test Logs: {stats['total_test_logs']}")
    print(f"  Completed Tests: {stats['completed_tests']}")
    print(f"  Passed Tests: {stats['passed_tests']}")
    
    if stats['completed_tests'] > 0:
        pass_rate = (stats['passed_tests'] / stats['completed_tests']) * 100
        print(f"  Pass Rate: {pass_rate:.1f}%")


def show_boards(db: DatabaseManager, limit: int = 20):
    """Show PCBA boards."""
    print("\n" + "="*60)
    print("PCBA BOARDS")
    print("="*60)
    
    with db.session_scope() as session:
        boards = session.query(PCBABoard).limit(limit).all()
        
        if not boards:
            print("  No boards found.")
            return
        
        print(f"\nShowing {len(boards)} boards:")
        print(f"{'Serial Number':<20} {'Part Number':<12} {'Generation':<10} {'Version':<8}")
        print("-" * 60)
        
        for board in boards:
            print(f"{board.serial_number:<20} {board.part_number:<12} "
                  f"{board.generation_project:<10} {board.version:<8}")


def show_pmts(db: DatabaseManager, limit: int = 20):
    """Show PMT devices."""
    print("\n" + "="*60)
    print("PMT DEVICES")
    print("="*60)
    
    with db.session_scope() as session:
        pmts = session.query(PMT).limit(limit).all()
        
        if not pmts:
            print("  No PMTs found.")
            return
        
        print(f"\nShowing {len(pmts)} PMTs:")
        print(f"{'Serial Number':<20} {'Generation':<12} {'Batch':<12}")
        print("-" * 50)
        
        for pmt in pmts:
            print(f"{pmt.pmt_serial_number:<20} {pmt.generation:<12} {pmt.batch_number:<12}")


def show_test_logs(db: DatabaseManager, limit: int = 20):
    """Show recent test logs."""
    print("\n" + "="*60)
    print("RECENT TEST LOGS")
    print("="*60)
    
    test_logs = db.queries.test_logs.get_recent(limit=limit)
    
    if not test_logs:
        print("  No test logs found.")
        return
    
    print(f"\nShowing {len(test_logs)} most recent test logs:")
    print(f"{'ID':<6} {'PCBA Serial':<18} {'PMT Serial':<18} {'Fixture':<18} {'Pass':<6} {'Date':<20}")
    print("-" * 90)
    
    for log in test_logs:
        # Get related objects
        with db.session_scope() as session:
            log = session.merge(log)
            pcba_serial = log.pia_board.serial_number if log.pia_board else "N/A"
            pmt_serial = log.pmt_device.pmt_serial_number if log.pmt_device else "N/A"
            passed = "PASS" if log.full_test_passed else "FAIL"
            date_str = log.created_at.strftime("%Y-%m-%d %H:%M") if log.created_at else "N/A"
            
            print(f"{log.id:<6} {pcba_serial:<18} {pmt_serial:<18} "
                  f"{log.test_fixture:<18} {passed:<6} {date_str:<20}")


def show_measurements(db: DatabaseManager):
    """Show available measurements and their statistics."""
    print("\n" + "="*60)
    print("AVAILABLE MEASUREMENTS")
    print("="*60)
    
    spec_names = db.queries.specs.get_all_spec_names()
    
    if not spec_names:
        print("  No measurements found.")
        return
    
    print(f"\nFound {len(spec_names)} unique measurements:")
    
    with db.session_scope() as session:
        for spec_name in sorted(spec_names):
            # Get count and pass rate for this measurement
            specs = session.query(Spec).filter(Spec.name == spec_name).all()
            
            if specs:
                total = len(specs)
                passed = sum(1 for s in specs if s.result)
                pass_rate = (passed / total * 100) if total > 0 else 0
                
                # Get unit from first spec
                unit = specs[0].unit if specs else ""
                
                # Get min/max values
                values = [s.measurement for s in specs if s.measurement is not None]
                if values:
                    min_val = min(values)
                    max_val = max(values)
                    avg_val = sum(values) / len(values)
                    
                    print(f"\n  {spec_name}")
                    print(f"    Total: {total} measurements")
                    print(f"    Pass Rate: {pass_rate:.1f}%")
                    print(f"    Range: {min_val:.3f} - {max_val:.3f} {unit}")
                    print(f"    Average: {avg_val:.3f} {unit}")


def show_measurement_details(db: DatabaseManager, spec_name: str, limit: int = 10):
    """Show details for a specific measurement."""
    print("\n" + "="*60)
    print(f"MEASUREMENT DETAILS: {spec_name}")
    print("="*60)
    
    with db.session_scope() as session:
        # Get specs with relationships loaded
        from sqlalchemy.orm import joinedload
        specs = (session.query(Spec)
                .filter(Spec.name == spec_name)
                .join(SubTest)
                .join(TestLog)
                .options(
                    joinedload(Spec.sub_test).joinedload(SubTest.test_log).joinedload(TestLog.pia_board),
                    joinedload(Spec.sub_test).joinedload(SubTest.test_log).joinedload(TestLog.pmt_device)
                )
                .order_by(Spec.created_at.desc())
                .limit(limit)
                .all())
        
        if not specs:
            print(f"  No measurements found for '{spec_name}'")
            return
        
        print(f"\nShowing {len(specs)} most recent measurements:")
        print(f"{'Value':<10} {'Unit':<6} {'Result':<8} {'PCBA Serial':<18} {'Fixture':<18} {'Date':<20}")
        print("-" * 90)
        
        for spec in specs:
            result = "PASS" if spec.result else "FAIL"
            date_str = spec.created_at.strftime("%Y-%m-%d %H:%M") if spec.created_at else "N/A"
            
            # Get related data
            test_log = spec.sub_test.test_log if spec.sub_test else None
            pcba_serial = test_log.pia_board.serial_number if test_log and test_log.pia_board else "N/A"
            fixture = test_log.test_fixture if test_log else "N/A"
            
            print(f"{spec.measurement:<10.3f} {spec.unit:<6} {result:<8} "
                  f"{pcba_serial:<18} {fixture:<18} {date_str:<20}")


def show_fixtures(db: DatabaseManager):
    """Show test fixtures and their statistics."""
    print("\n" + "="*60)
    print("TEST FIXTURES")
    print("="*60)
    
    with db.session_scope() as session:
        # Get unique fixtures
        from sqlalchemy import func, distinct
        fixtures = session.query(
            TestLog.test_fixture,
            func.count(TestLog.id).label('total'),
            func.sum(func.cast(TestLog.full_test_passed, Integer)).label('passed')
        ).group_by(TestLog.test_fixture).all()
        
        if not fixtures:
            print("  No fixtures found.")
            return
        
        print(f"\n{'Fixture':<25} {'Total Tests':<15} {'Passed':<10} {'Pass Rate':<10}")
        print("-" * 65)
        
        for fixture, total, passed in fixtures:
            passed = passed or 0
            pass_rate = (passed / total * 100) if total > 0 else 0
            print(f"{fixture:<25} {total:<15} {passed:<10} {pass_rate:>8.1f}%")


def interactive_menu(db: DatabaseManager):
    """Interactive menu for viewing data."""
    while True:
        print("\n" + "="*60)
        print("DATABASE VIEWER - MENU")
        print("="*60)
        print("\n1. Show Summary")
        print("2. Show PCBA Boards")
        print("3. Show PMT Devices")
        print("4. Show Recent Test Logs")
        print("5. Show Available Measurements")
        print("6. Show Measurement Details")
        print("7. Show Test Fixtures")
        print("8. Exit")
        
        choice = input("\nSelect option (1-8): ").strip()
        
        if choice == "1":
            show_summary(db)
        elif choice == "2":
            limit = input("How many boards to show? (default: 20): ").strip()
            limit = int(limit) if limit.isdigit() else 20
            show_boards(db, limit)
        elif choice == "3":
            limit = input("How many PMTs to show? (default: 20): ").strip()
            limit = int(limit) if limit.isdigit() else 20
            show_pmts(db, limit)
        elif choice == "4":
            limit = input("How many test logs to show? (default: 20): ").strip()
            limit = int(limit) if limit.isdigit() else 20
            show_test_logs(db, limit)
        elif choice == "5":
            show_measurements(db)
        elif choice == "6":
            spec_name = input("Enter measurement name: ").strip()
            if spec_name:
                limit = input("How many to show? (default: 10): ").strip()
                limit = int(limit) if limit.isdigit() else 10
                show_measurement_details(db, spec_name, limit)
        elif choice == "7":
            show_fixtures(db)
        elif choice == "8":
            print("\nGoodbye!")
            break
        else:
            print("\nInvalid option. Please try again.")
        
        input("\nPress Enter to continue...")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='View database contents')
    parser.add_argument('--summary', action='store_true',
                       help='Show summary and exit')
    parser.add_argument('--measurements', action='store_true',
                       help='Show measurements and exit')
    parser.add_argument('--detail', type=str,
                       help='Show details for specific measurement')
    
    args = parser.parse_args()
    
    try:
        # Create database manager
        db = DatabaseManager()
        
        if args.summary:
            show_summary(db)
            show_fixtures(db)
        elif args.measurements:
            show_measurements(db)
        elif args.detail:
            show_measurement_details(db, args.detail, limit=20)
        else:
            # Interactive mode
            interactive_menu(db)
        
        # Close database
        db.close()
        
        return 0
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    from src.database import PCBABoard, PMT, TestLog, SubTest, Spec
    from sqlalchemy import Integer
    sys.exit(main())
