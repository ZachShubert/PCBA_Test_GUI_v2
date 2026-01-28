"""
Database Migration Script
=========================
Run this after updating the model files to:
1. Create new tables (Manufacturer, ManufacturerSpec, ManufacturerDeviceBatch)
2. Add new columns to existing tables (plot_data to spec)

Usage:
    python migrate_database.py

"""
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def migrate():
    print("=" * 60)
    print("DATABASE MIGRATION")
    print("=" * 60)

    # Import database components
    try:
        from src.database.base import Base, get_engine
        from src.database import (
            PMT, PCBABoard, TestLog, SubTest, Spec,
            Manufacturer, ManufacturerSpec, ManufacturerDeviceBatch
        )
        print("✓ Imports successful")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("\nMake sure you're running from the project root directory.")
        return False

    # Get engine instance
    engine = get_engine()
    print(f"✓ Connected to database")

    # Step 1: Create new tables
    print("\n--- Creating New Tables ---")
    try:
        Base.metadata.create_all(engine)
        print("✓ Tables created (or already exist):")
        print("  - manufacturer")
        print("  - manufacturer_spec")
        print("  - manufacturer_device_batch")
    except Exception as e:
        print(f"✗ Error creating tables: {e}")
        return False

    # Step 2: Add new columns to existing tables
    print("\n--- Adding New Columns ---")
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            # Check spec table for plot_data column
            result = conn.execute(text("PRAGMA table_info(spec)"))
            columns = [row[1] for row in result.fetchall()]

            if 'plot_data' not in columns:
                conn.execute(text("ALTER TABLE spec ADD COLUMN plot_data TEXT"))
                conn.commit()
                print("✓ Added 'plot_data' column to spec table")
            else:
                print("✓ 'plot_data' column already exists in spec table")

    except Exception as e:
        print(f"✗ Error adding columns: {e}")
        print("  This may be okay if the column already exists.")

    # Step 3: Verify migration
    print("\n--- Verification ---")
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)

        # Check tables exist
        tables = inspector.get_table_names()
        required_tables = ['manufacturer', 'manufacturer_spec', 'manufacturer_device_batch', 'spec']

        for table in required_tables:
            if table in tables:
                print(f"✓ Table '{table}' exists")
            else:
                print(f"✗ Table '{table}' NOT FOUND")

        # Check spec columns
        spec_columns = [col['name'] for col in inspector.get_columns('spec')]
        if 'plot_data' in spec_columns:
            print("✓ 'plot_data' column exists in spec table")
        else:
            print("✗ 'plot_data' column NOT FOUND in spec table")

    except Exception as e:
        print(f"✗ Verification error: {e}")

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)

    return True


def show_table_info():
    """Show current database structure."""
    print("\n--- Current Database Structure ---")

    try:
        from src.database.base import get_engine
        from sqlalchemy import inspect

        engine = get_engine()
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        for table in sorted(tables):
            columns = inspector.get_columns(table)
            print(f"\n{table}:")
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                print(f"  - {col['name']}: {col['type']} {nullable}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--info':
        show_table_info()
    else:
        success = migrate()

        if success:
            print("\nTo see current database structure, run:")
            print("  python migrate_database.py --info")

        sys.exit(0 if success else 1)