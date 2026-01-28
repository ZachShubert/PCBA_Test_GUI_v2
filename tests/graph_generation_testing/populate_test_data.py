#!/usr/bin/env python3
"""
Populate Database with Test Data

This script creates realistic test data for testing graph features:
- Multiple PCBAs and PMTs
- Various test fixtures
- Multiple test runs per device
- Different measurement types (pass/fail/edge cases)
- Measurements with plots
- Date ranges
- Different batches/generations

Run this to populate your database with test data for graph testing.
"""
import sys
import os
import random
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.database import DatabaseManager, PCBABoard, PMT, TestLog, SubTest, Spec, MeasurementType


class TestDataGenerator:
    """Generate realistic test data for database."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

        # Test fixture names
        self.fixtures = ["Test Fixture A", "Test Fixture B", "Test Fixture C"]

        # Measurement specs with realistic ranges
        self.measurements = {
            "Output Voltage 5V": {
                "unit": "V",
                "nominal": 5.0,
                "lower": 4.95,
                "upper": 5.05,
                "typical_range": (4.97, 5.03),
            },
            "Output Voltage 3.3V": {
                "unit": "V",
                "nominal": 3.3,
                "lower": 3.25,
                "upper": 3.35,
                "typical_range": (3.28, 3.32),
            },
            "Output Voltage 12V": {
                "unit": "V",
                "nominal": 12.0,
                "lower": 11.8,
                "upper": 12.2,
                "typical_range": (11.9, 12.1),
            },
            "Current Draw 5V": {
                "unit": "A",
                "nominal": 2.0,
                "lower": 1.9,
                "upper": 2.1,
                "typical_range": (1.95, 2.05),
            },
            "Current Draw 3.3V": {
                "unit": "A",
                "nominal": 1.5,
                "lower": 1.4,
                "upper": 1.6,
                "typical_range": (1.45, 1.55),
            },
            "Temperature": {
                "unit": "°C",
                "nominal": 45.0,
                "lower": 20.0,
                "upper": 70.0,
                "typical_range": (40.0, 50.0),
            },
            "Ripple Voltage": {
                "unit": "mV",
                "nominal": 50.0,
                "lower": 0.0,
                "upper": 100.0,
                "typical_range": (30.0, 70.0),
            },
            "Efficiency": {
                "unit": "%",
                "nominal": 90.0,
                "lower": 85.0,
                "upper": 95.0,
                "typical_range": (88.0, 92.0),
            },
            "Response Time": {
                "unit": "ms",
                "nominal": 10.0,
                "lower": 5.0,
                "upper": 15.0,
                "typical_range": (8.0, 12.0),
            },
            "Noise Level": {
                "unit": "dB",
                "nominal": 60.0,
                "lower": 55.0,
                "upper": 65.0,
                "typical_range": (58.0, 62.0),
            },
        }

        # PMT generations and batches
        self.pmt_generations = ["Gen1", "Gen2", "Gen3"]
        self.pmt_batches = ["BATCH_A", "BATCH_B", "BATCH_C", "BATCH_D"]

        # PCBA part numbers
        self.part_numbers = ["PN-001", "PN-002", "PN-003"]
        self.pcba_generations = ["Gen1", "Gen2", "Gen3"]
        self.pcba_versions = ["v1.0", "v1.1", "v2.0"]

    def generate_measurement(self, spec_info: dict, pass_rate: float = 0.9) -> float:
        """
        Generate a measurement value.

        Args:
            spec_info: Measurement specification
            pass_rate: Probability of passing (0.0 to 1.0)

        Returns:
            Measurement value
        """
        if random.random() < pass_rate:
            # Passing measurement - within typical range
            return random.uniform(*spec_info["typical_range"])
        else:
            # Failing measurement - choose between low or high failure
            if random.random() < 0.5:
                # Below lower limit
                return random.uniform(
                    spec_info["lower"] - 0.2 * (spec_info["nominal"] - spec_info["lower"]),
                    spec_info["lower"] - 0.01
                )
            else:
                # Above upper limit
                return random.uniform(
                    spec_info["upper"] + 0.01,
                    spec_info["upper"] + 0.2 * (spec_info["upper"] - spec_info["nominal"])
                )

    def create_pcba_boards(self, count: int = 20) -> list:
        """Create PCBA boards."""
        print(f"\nCreating {count} PCBA boards...")
        boards = []

        for i in range(count):
            board = PCBABoard(
                serial_number=f"PCBA_TEST_{i:04d}",
                part_number=random.choice(self.part_numbers),
                generation_project=random.choice(self.pcba_generations),
                version=random.choice(self.pcba_versions)
            )
            boards.append(board)

        self.db.bulk_add(boards)
        print(f"✓ Created {count} PCBA boards")
        return boards

    def create_pmts(self, count: int = 15) -> list:
        """Create PMT devices."""
        print(f"\nCreating {count} PMT devices...")
        pmts = []

        for i in range(count):
            pmt = PMT(
                pmt_serial_number=f"PMT_TEST_{i:04d}",
                generation=random.choice(self.pmt_generations),
                batch_number=random.choice(self.pmt_batches)
            )
            pmts.append(pmt)

        self.db.bulk_add(pmts)
        print(f"✓ Created {count} PMT devices")
        return pmts

    def create_test_log(
            self,
            board_serial: str,
            pmt_serial: str,
            fixture: str,
            test_date: datetime,
            pass_rate: float = 0.9
    ):
        """
        Create a complete test log with subtests and measurements.

        Args:
            board_serial: PCBABoard serial number
            pmt_serial: PMT serial number
            fixture: Test fixture name
            test_date: When test was run
            pass_rate: Probability of measurements passing
        """
        import hashlib
        import uuid

        with self.db.session_scope() as session:
            # Query the board and PMT in this session
            board = session.query(PCBABoard).filter(
                PCBABoard.serial_number == board_serial
            ).first()

            pmt = session.query(PMT).filter(
                PMT.pmt_serial_number == pmt_serial
            ).first()

            if not board or not pmt:
                raise ValueError(f"Board or PMT not found: {board_serial}, {pmt_serial}")

            # Create unique identifiers
            unique_str = f"{board_serial}_{pmt_serial}_{fixture}_{test_date.timestamp()}_{uuid.uuid4()}"
            html_hash = hashlib.sha256(unique_str.encode()).digest()

            # Create test log
            test_log = TestLog(
                pia_board_id=board.id,
                pmt_id=pmt.id,
                name="System Integration Test",
                description=f"Full system test on {fixture}",
                generation_project=board.generation_project,
                script_version="v2.1.0",
                test_fixture=fixture,
                created_at=test_date,
                full_test_completed=True,
                full_test_passed=True,  # Will update based on specs
                html_path=f"/logs/{board_serial}_{test_date.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.html",
                html_content=f"<html>Test Results for {board_serial} at {test_date} - {uuid.uuid4()}</html>",
                html_hash=html_hash
            )
            session.add(test_log)
            session.flush()

            # Create subtests
            subtests = [
                ("Power Supply Test", "Test all voltage outputs"),
                ("Current Draw Test", "Test current consumption"),
                ("Thermal Test", "Test temperature under load"),
                ("Signal Quality Test", "Test noise and response time"),
            ]

            all_passed = True

            for subtest_name, subtest_desc in subtests:
                subtest = SubTest(
                    test_log_id=test_log.id,
                    name=subtest_name,
                    description=subtest_desc,
                    generation_project=board.generation_project,
                    script_version="v2.1.0",
                    created_at=test_date
                )
                session.add(subtest)
                session.flush()

                # Create measurements for this subtest
                # Assign relevant measurements to each subtest
                if "Power Supply" in subtest_name:
                    measurement_names = ["Output Voltage 5V", "Output Voltage 3.3V", "Output Voltage 12V"]
                elif "Current" in subtest_name:
                    measurement_names = ["Current Draw 5V", "Current Draw 3.3V"]
                elif "Thermal" in subtest_name:
                    measurement_names = ["Temperature"]
                else:
                    measurement_names = ["Ripple Voltage", "Efficiency", "Response Time", "Noise Level"]

                for meas_name in measurement_names:
                    spec_info = self.measurements[meas_name]
                    measured_value = self.generate_measurement(spec_info, pass_rate)

                    result = (measured_value >= spec_info["lower"] and
                              measured_value <= spec_info["upper"])

                    if not result:
                        all_passed = False

                    spec = Spec(
                        sub_test_id=subtest.id,
                        name=meas_name,
                        unit=spec_info["unit"],
                        created_at=test_date,
                        measurement_type=MeasurementType.RANGE,
                        measurement=measured_value,
                        has_plot=False,
                        lower_limit=spec_info["lower"],
                        nominal=spec_info["nominal"],
                        upper_limit=spec_info["upper"],
                        result=result
                    )
                    session.add(spec)

            # Update test log pass/fail
            test_log.full_test_passed = all_passed

    def populate_realistic_data(
            self,
            num_boards: int = 20,
            num_pmts: int = 15,
            tests_per_board: int = 3,
            days_back: int = 90
    ):
        """
        Populate database with realistic test data.

        Args:
            num_boards: Number of PCBA boards to create
            num_pmts: Number of PMT devices to create
            tests_per_board: Number of test runs per board
            days_back: Date range (tests spread over last N days)
        """
        print("\n" + "=" * 60)
        print("POPULATING DATABASE WITH TEST DATA")
        print("=" * 60)

        # Create devices
        boards = self.create_pcba_boards(num_boards)
        pmts = self.create_pmts(num_pmts)

        # Create test logs
        print(f"\nCreating test logs ({tests_per_board} per board)...")

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        test_count = 0

        for board in boards:
            # Select a random PMT for this board
            pmt = random.choice(pmts)

            # Create multiple tests for this board over time
            for test_num in range(tests_per_board):
                # Random date within range
                days_offset = random.uniform(0, days_back)
                test_date = start_date + timedelta(days=days_offset)

                # Random fixture
                fixture = random.choice(self.fixtures)

                # Pass rate varies by test number (early tests more likely to fail)
                if test_num == 0:
                    pass_rate = 0.7  # First test - more failures
                elif test_num == 1:
                    pass_rate = 0.85  # Second test - some fixes
                else:
                    pass_rate = 0.95  # Later tests - mostly passing

                # Pass serial numbers instead of objects
                self.create_test_log(
                    board.serial_number,
                    pmt.pmt_serial_number,
                    fixture,
                    test_date,
                    pass_rate
                )
                test_count += 1

                if test_count % 10 == 0:
                    print(f"  Created {test_count} test logs...")

        print(f"✓ Created {test_count} test logs")

        # Summary
        print("\n" + "=" * 60)
        print("DATA POPULATION COMPLETE")
        print("=" * 60)

        stats = self.db.get_database_stats()
        print(f"\nDatabase Statistics:")
        print(f"  - PCBA Boards: {stats['total_boards']}")
        print(f"  - PMT Devices: {stats['total_pmts']}")
        print(f"  - Test Logs: {stats['total_test_logs']}")
        print(f"  - Completed Tests: {stats['completed_tests']}")
        print(f"  - Passed Tests: {stats['passed_tests']}")

        # Show what specs are available
        spec_names = self.db.queries.specs.get_all_spec_names()
        print(f"\nAvailable Measurements ({len(spec_names)}):")
        for spec in sorted(spec_names):
            print(f"  - {spec}")

        print("\n✓ Ready for graph testing!")
        print("  Run: python src/main.py")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Populate database with test data')
    parser.add_argument('--boards', type=int, default=20,
                        help='Number of PCBA boards (default: 20)')
    parser.add_argument('--pmts', type=int, default=15,
                        help='Number of PMT devices (default: 15)')
    parser.add_argument('--tests', type=int, default=3,
                        help='Tests per board (default: 3)')
    parser.add_argument('--days', type=int, default=90,
                        help='Spread tests over N days (default: 90)')
    parser.add_argument('--clear', action='store_true',
                        help='Clear existing test data first')

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("DATABASE TEST DATA POPULATION")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  PCBA Boards: {args.boards}")
    print(f"  PMT Devices: {args.pmts}")
    print(f"  Tests per board: {args.tests}")
    print(f"  Date range: Last {args.days} days")
    print(f"  Clear existing: {args.clear}")

    # Confirm
    response = input("\nProceed? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return 0

    try:
        # Create database manager
        db = DatabaseManager()

        # Clear old test data if requested
        if args.clear:
            print("\nClearing existing test data...")
            with db.session_scope() as session:
                # Delete test data
                deleted_boards = session.query(PCBABoard).filter(
                    PCBABoard.serial_number.like('PCBA_TEST_%')
                ).delete()
                deleted_pmts = session.query(PMT).filter(
                    PMT.pmt_serial_number.like('PMT_TEST_%')
                ).delete()

                print(f"✓ Deleted {deleted_boards} test boards")
                print(f"✓ Deleted {deleted_pmts} test PMTs")

        # Generate data
        generator = TestDataGenerator(db)
        generator.populate_realistic_data(
            num_boards=args.boards,
            num_pmts=args.pmts,
            tests_per_board=args.tests,
            days_back=args.days
        )

        # Close database
        db.close()

        return 0

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())