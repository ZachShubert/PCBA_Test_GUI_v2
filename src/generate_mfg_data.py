"""
Generate Sample Manufacturer Data
=================================
This script creates sample manufacturer specs based on your existing test data.

It will:
1. Find all unique spec names in your database
2. Find all devices (by serial number) that have measurements
3. Create manufacturer specs with slight variations from your actual measurements

This allows you to test the Comparison Mode plots.

Usage:
    python generate_manufacturer_data.py
"""
import sys
import os
import random
from datetime import datetime, timedelta

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def generate_manufacturer_data():
    print("=" * 60)
    print("GENERATE SAMPLE MANUFACTURER DATA")
    print("=" * 60)

    try:
        from src.database import DatabaseManager
        from src.database.database_manufacturer_tables import (
            Manufacturer, ManufacturerSpec, ManufacturerDeviceBatch
        )
        from src.database.database_test_log_tables import Spec, SubTest, TestLog
        from src.database.database_device_tables import PCBABoard, PMT

        db = DatabaseManager()
        print("✓ Connected to database")

    except Exception as e:
        print(f"✗ Error connecting to database: {e}")
        return False

    with db.session_scope() as session:
        # Step 1: Create or get manufacturer
        print("\n--- Creating Manufacturer ---")

        manufacturer = session.query(Manufacturer).filter_by(name="Sample Manufacturer").first()
        if not manufacturer:
            manufacturer = Manufacturer(
                name="Sample Manufacturer",
                description="Auto-generated sample manufacturer for testing comparison plots",
                website="https://example.com"
            )
            session.add(manufacturer)
            session.flush()
            print("✓ Created 'Sample Manufacturer'")
        else:
            print("✓ Using existing 'Sample Manufacturer'")

        # Step 2: Get all unique spec names from our database
        print("\n--- Finding Specs ---")

        spec_names = session.query(Spec.name).distinct().all()
        spec_names = [s[0] for s in spec_names if s[0]]
        print(f"✓ Found {len(spec_names)} unique spec names")

        # Step 3: Get device serial numbers and their measurements
        print("\n--- Finding Devices and Measurements ---")

        # Query to get device serials with their measurements
        device_specs = {}

        # Get PIA boards with their specs
        results = session.query(
            PCBABoard.serial_number,
            Spec.name,
            Spec.measurement,
            Spec.unit,
            Spec.lower_limit,
            Spec.upper_limit
        ).join(
            TestLog, TestLog.pia_board_id == PCBABoard.id
        ).join(
            SubTest, SubTest.test_log_id == TestLog.id
        ).join(
            Spec, Spec.sub_test_id == SubTest.id
        ).filter(
            Spec.measurement.isnot(None)
        ).all()

        for serial, spec_name, measurement, unit, lower, upper in results:
            if serial not in device_specs:
                device_specs[serial] = {}
            if spec_name not in device_specs[serial]:
                device_specs[serial][spec_name] = {
                    'measurements': [],
                    'unit': unit,
                    'lower_limit': lower,
                    'upper_limit': upper
                }
            device_specs[serial][spec_name]['measurements'].append(measurement)

        print(f"✓ Found {len(device_specs)} devices with measurements")

        # Step 4: Create manufacturer specs
        print("\n--- Creating Manufacturer Specs ---")

        # Check how many already exist
        existing_count = session.query(ManufacturerSpec).filter_by(
            manufacturer_id=manufacturer.id
        ).count()

        if existing_count > 0:
            print(f"  Found {existing_count} existing manufacturer specs")
            response = input("  Delete existing and regenerate? (y/n): ").strip().lower()
            if response == 'y':
                session.query(ManufacturerSpec).filter_by(
                    manufacturer_id=manufacturer.id
                ).delete()
                session.flush()
                print(f"  ✓ Deleted {existing_count} existing specs")
            else:
                print("  Keeping existing specs, adding new ones only")

        specs_created = 0

        for device_serial, specs in device_specs.items():
            for spec_name, spec_data in specs.items():
                # Check if already exists
                existing = session.query(ManufacturerSpec).filter_by(
                    manufacturer_id=manufacturer.id,
                    device_serial=device_serial,
                    spec_name=spec_name
                ).first()

                if existing:
                    continue

                # Calculate manufacturer value based on our measurements
                our_measurements = spec_data['measurements']
                our_avg = sum(our_measurements) / len(our_measurements)

                # Add slight variation (±2% random offset to simulate manufacturer tolerance)
                variation = our_avg * random.uniform(-0.02, 0.02)
                mfr_value = our_avg + variation

                # Create manufacturer spec
                mfr_spec = ManufacturerSpec(
                    manufacturer_id=manufacturer.id,
                    spec_name=spec_name,
                    device_serial=device_serial,
                    measurement=round(mfr_value, 6),
                    unit=spec_data['unit'],
                    lower_limit=spec_data['lower_limit'],
                    upper_limit=spec_data['upper_limit'],
                    test_date=datetime.now() - timedelta(days=random.randint(30, 365)),
                    notes="Auto-generated sample data for testing"
                )
                session.add(mfr_spec)
                specs_created += 1

        session.commit()
        print(f"✓ Created {specs_created} manufacturer specs")

        # Step 5: Show summary
        print("\n--- Summary ---")

        total_mfr_specs = session.query(ManufacturerSpec).filter_by(
            manufacturer_id=manufacturer.id
        ).count()

        # Show breakdown by spec name
        spec_counts = session.query(
            ManufacturerSpec.spec_name,
            session.query(ManufacturerSpec).filter(
                ManufacturerSpec.manufacturer_id == manufacturer.id,
                ManufacturerSpec.spec_name == ManufacturerSpec.spec_name
            ).count()
        ).filter_by(
            manufacturer_id=manufacturer.id
        ).group_by(ManufacturerSpec.spec_name).all()

        print(f"\nTotal manufacturer specs: {total_mfr_specs}")
        print("\nSpecs by name (first 10):")

        # Get count per spec name
        from sqlalchemy import func
        spec_breakdown = session.query(
            ManufacturerSpec.spec_name,
            func.count(ManufacturerSpec.id)
        ).filter_by(
            manufacturer_id=manufacturer.id
        ).group_by(ManufacturerSpec.spec_name).limit(10).all()

        for spec_name, count in spec_breakdown:
            print(f"  - {spec_name}: {count} devices")

        print("\n" + "=" * 60)
        print("DONE!")
        print("=" * 60)
        print("\nYou can now use Comparison Mode in the graph page.")
        print("The manufacturer data will be paired with your measurements by device serial number.")

        return True


def show_manufacturer_data():
    """Show existing manufacturer data."""
    print("\n--- Existing Manufacturer Data ---")

    try:
        from src.database import DatabaseManager
        from src.database.database_manufacturer_tables import Manufacturer, ManufacturerSpec
        from sqlalchemy import func

        db = DatabaseManager()

        with db.session_scope() as session:
            manufacturers = session.query(Manufacturer).all()

            if not manufacturers:
                print("No manufacturers found in database.")
                return

            for mfr in manufacturers:
                print(f"\nManufacturer: {mfr.name}")
                print(f"  Description: {mfr.description or 'N/A'}")

                # Count specs
                spec_count = session.query(ManufacturerSpec).filter_by(
                    manufacturer_id=mfr.id
                ).count()
                print(f"  Total specs: {spec_count}")

                # Breakdown by spec name
                breakdown = session.query(
                    ManufacturerSpec.spec_name,
                    func.count(ManufacturerSpec.id)
                ).filter_by(
                    manufacturer_id=mfr.id
                ).group_by(ManufacturerSpec.spec_name).all()

                if breakdown:
                    print("  Specs breakdown:")
                    for spec_name, count in breakdown[:10]:
                        print(f"    - {spec_name}: {count} devices")
                    if len(breakdown) > 10:
                        print(f"    ... and {len(breakdown) - 10} more spec types")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--show':
        show_manufacturer_data()
    else:
        success = generate_manufacturer_data()
        sys.exit(0 if success else 1)