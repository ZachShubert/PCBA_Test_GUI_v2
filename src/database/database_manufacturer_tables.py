"""
Manufacturer table models and Excel import utilities.

This module provides:
- Manufacturer model for storing manufacturer/vendor specifications
- ManufacturerSpec model for individual spec values from manufacturers
- Excel import functionality for bulk loading manufacturer data
"""
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from src.database.base import Base


class Manufacturer(Base):
    """
    Manufacturer/Vendor model.

    Stores information about device manufacturers whose specs
    we want to compare against our test results.
    """
    __tablename__ = 'manufacturer'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    contact_info = Column(String, nullable=True)
    website = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    specs = relationship("ManufacturerSpec", back_populates="manufacturer", cascade="all, delete-orphan")
    device_batches = relationship("ManufacturerDeviceBatch", back_populates="manufacturer",
                                  cascade="all, delete-orphan")


class ManufacturerDeviceBatch(Base):
    """
    Manufacturer device batch model.

    Groups manufacturer specs by device batch/lot for comparison.
    """
    __tablename__ = 'manufacturer_device_batch'

    id = Column(Integer, primary_key=True, autoincrement=True)
    manufacturer_id = Column(Integer, ForeignKey('manufacturer.id'), nullable=False)
    batch_number = Column(String, nullable=False)
    device_type = Column(String, nullable=True)  # 'PMT', 'PIA', etc.
    device_serial = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    manufacturer = relationship("Manufacturer", back_populates="device_batches")
    specs = relationship("ManufacturerSpec", back_populates="device_batch", cascade="all, delete-orphan")


class ManufacturerSpec(Base):
    """
    Manufacturer specification model.

    Stores individual measurement specs from manufacturers
    for comparison with our test results.
    """
    __tablename__ = 'manufacturer_spec'

    id = Column(Integer, primary_key=True, autoincrement=True)
    manufacturer_id = Column(Integer, ForeignKey('manufacturer.id'), nullable=False)
    device_batch_id = Column(Integer, ForeignKey('manufacturer_device_batch.id'), nullable=True)

    # Spec identification
    spec_name = Column(String, nullable=False)  # Should match our Spec.name for comparison
    device_serial = Column(String, nullable=True)  # Individual device if available

    # Values
    measurement = Column(Float, nullable=True)
    unit = Column(String, nullable=True)
    lower_limit = Column(Float, nullable=True)
    nominal = Column(Float, nullable=True)
    upper_limit = Column(Float, nullable=True)

    # Metadata
    test_date = Column(DateTime, nullable=True)
    test_conditions = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    manufacturer = relationship("Manufacturer", back_populates="specs")
    device_batch = relationship("ManufacturerDeviceBatch", back_populates="specs")


class ManufacturerExcelImporter:
    """
    Utility class for importing manufacturer specs from Excel files.

    Expected Excel format:
    - Sheet 1: Manufacturer info (name, description, contact, website)
    - Sheet 2: Device batches (batch_number, device_type, device_serial, notes)
    - Sheet 3: Specs (batch_number, device_serial, spec_name, measurement, unit,
                      lower_limit, nominal, upper_limit, test_date, notes)

    Or simplified single-sheet format:
    - Columns: manufacturer_name, batch_number, device_serial, spec_name,
               measurement, unit, lower_limit, nominal, upper_limit, test_date, notes
    """

    def __init__(self, db_manager):
        """
        Initialize importer with database manager.

        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager

    def import_from_excel(self, file_path: str, format_type: str = 'simple') -> Dict[str, Any]:
        """
        Import manufacturer specs from Excel file.

        Args:
            file_path: Path to Excel file
            format_type: 'simple' (single sheet) or 'detailed' (multi-sheet)

        Returns:
            Dict with import results (counts, errors, etc.)
        """
        try:
            import pandas as pd
        except ImportError:
            return {'success': False, 'error': 'pandas not installed. Run: pip install pandas openpyxl'}

        results = {
            'success': True,
            'manufacturers_added': 0,
            'batches_added': 0,
            'specs_added': 0,
            'errors': [],
            'warnings': []
        }

        try:
            if format_type == 'simple':
                results = self._import_simple_format(file_path, results)
            else:
                results = self._import_detailed_format(file_path, results)
        except Exception as e:
            results['success'] = False
            results['errors'].append(f"Import failed: {str(e)}")

        return results

    def _import_simple_format(self, file_path: str, results: Dict) -> Dict:
        """Import from single-sheet simple format."""
        import pandas as pd

        df = pd.read_excel(file_path)

        # Required columns
        required_cols = ['manufacturer_name', 'spec_name', 'measurement']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            results['success'] = False
            results['errors'].append(f"Missing required columns: {missing_cols}")
            return results

        with self.db.session_scope() as session:
            manufacturers_cache = {}
            batches_cache = {}

            for idx, row in df.iterrows():
                try:
                    # Get or create manufacturer
                    mfr_name = str(row['manufacturer_name']).strip()
                    if mfr_name not in manufacturers_cache:
                        mfr = session.query(Manufacturer).filter_by(name=mfr_name).first()
                        if not mfr:
                            mfr = Manufacturer(name=mfr_name)
                            session.add(mfr)
                            session.flush()
                            results['manufacturers_added'] += 1
                        manufacturers_cache[mfr_name] = mfr

                    manufacturer = manufacturers_cache[mfr_name]

                    # Get or create batch if specified
                    device_batch = None
                    batch_number = row.get('batch_number')
                    if pd.notna(batch_number):
                        batch_key = (mfr_name, str(batch_number))
                        if batch_key not in batches_cache:
                            batch = session.query(ManufacturerDeviceBatch).filter_by(
                                manufacturer_id=manufacturer.id,
                                batch_number=str(batch_number)
                            ).first()
                            if not batch:
                                batch = ManufacturerDeviceBatch(
                                    manufacturer_id=manufacturer.id,
                                    batch_number=str(batch_number),
                                    device_type=row.get('device_type') if pd.notna(row.get('device_type')) else None
                                )
                                session.add(batch)
                                session.flush()
                                results['batches_added'] += 1
                            batches_cache[batch_key] = batch
                        device_batch = batches_cache[batch_key]

                    # Create spec
                    spec = ManufacturerSpec(
                        manufacturer_id=manufacturer.id,
                        device_batch_id=device_batch.id if device_batch else None,
                        spec_name=str(row['spec_name']).strip(),
                        device_serial=str(row['device_serial']).strip() if pd.notna(row.get('device_serial')) else None,
                        measurement=float(row['measurement']) if pd.notna(row.get('measurement')) else None,
                        unit=str(row['unit']).strip() if pd.notna(row.get('unit')) else None,
                        lower_limit=float(row['lower_limit']) if pd.notna(row.get('lower_limit')) else None,
                        nominal=float(row['nominal']) if pd.notna(row.get('nominal')) else None,
                        upper_limit=float(row['upper_limit']) if pd.notna(row.get('upper_limit')) else None,
                        notes=str(row['notes']).strip() if pd.notna(row.get('notes')) else None
                    )

                    # Parse test_date if present
                    if pd.notna(row.get('test_date')):
                        try:
                            spec.test_date = pd.to_datetime(row['test_date'])
                        except:
                            results['warnings'].append(f"Row {idx + 2}: Could not parse test_date")

                    session.add(spec)
                    results['specs_added'] += 1

                except Exception as e:
                    results['warnings'].append(f"Row {idx + 2}: {str(e)}")

            session.commit()

        return results

    def _import_detailed_format(self, file_path: str, results: Dict) -> Dict:
        """Import from multi-sheet detailed format."""
        import pandas as pd

        xlsx = pd.ExcelFile(file_path)

        with self.db.session_scope() as session:
            # Sheet 1: Manufacturers
            if 'Manufacturers' in xlsx.sheet_names:
                mfr_df = pd.read_excel(xlsx, 'Manufacturers')
                for _, row in mfr_df.iterrows():
                    if pd.notna(row.get('name')):
                        mfr = Manufacturer(
                            name=str(row['name']).strip(),
                            description=str(row.get('description', '')).strip() or None,
                            contact_info=str(row.get('contact_info', '')).strip() or None,
                            website=str(row.get('website', '')).strip() or None
                        )
                        session.add(mfr)
                        results['manufacturers_added'] += 1
                session.flush()

            # Sheet 2: Batches
            if 'Batches' in xlsx.sheet_names:
                batch_df = pd.read_excel(xlsx, 'Batches')
                for _, row in batch_df.iterrows():
                    mfr = session.query(Manufacturer).filter_by(name=str(row['manufacturer_name']).strip()).first()
                    if mfr:
                        batch = ManufacturerDeviceBatch(
                            manufacturer_id=mfr.id,
                            batch_number=str(row['batch_number']).strip(),
                            device_type=str(row.get('device_type', '')).strip() or None,
                            notes=str(row.get('notes', '')).strip() or None
                        )
                        session.add(batch)
                        results['batches_added'] += 1
                session.flush()

            # Sheet 3: Specs
            if 'Specs' in xlsx.sheet_names:
                spec_df = pd.read_excel(xlsx, 'Specs')
                for idx, row in spec_df.iterrows():
                    try:
                        mfr = session.query(Manufacturer).filter_by(name=str(row['manufacturer_name']).strip()).first()
                        if not mfr:
                            results['warnings'].append(f"Specs row {idx + 2}: Manufacturer not found")
                            continue

                        batch = None
                        if pd.notna(row.get('batch_number')):
                            batch = session.query(ManufacturerDeviceBatch).filter_by(
                                manufacturer_id=mfr.id,
                                batch_number=str(row['batch_number']).strip()
                            ).first()

                        spec = ManufacturerSpec(
                            manufacturer_id=mfr.id,
                            device_batch_id=batch.id if batch else None,
                            spec_name=str(row['spec_name']).strip(),
                            device_serial=str(row.get('device_serial', '')).strip() or None,
                            measurement=float(row['measurement']) if pd.notna(row.get('measurement')) else None,
                            unit=str(row.get('unit', '')).strip() or None,
                            lower_limit=float(row['lower_limit']) if pd.notna(row.get('lower_limit')) else None,
                            nominal=float(row['nominal']) if pd.notna(row.get('nominal')) else None,
                            upper_limit=float(row['upper_limit']) if pd.notna(row.get('upper_limit')) else None,
                            notes=str(row.get('notes', '')).strip() or None
                        )
                        session.add(spec)
                        results['specs_added'] += 1
                    except Exception as e:
                        results['warnings'].append(f"Specs row {idx + 2}: {str(e)}")

            session.commit()

        return results

    def export_template(self, file_path: str, format_type: str = 'simple'):
        """
        Export an Excel template for data entry.

        Args:
            file_path: Output file path
            format_type: 'simple' or 'detailed'
        """
        import pandas as pd

        if format_type == 'simple':
            # Single sheet with all columns
            df = pd.DataFrame(columns=[
                'manufacturer_name', 'batch_number', 'device_type', 'device_serial',
                'spec_name', 'measurement', 'unit', 'lower_limit', 'nominal',
                'upper_limit', 'test_date', 'notes'
            ])
            df.to_excel(file_path, index=False)
        else:
            # Multi-sheet detailed format
            with pd.ExcelWriter(file_path) as writer:
                pd.DataFrame(columns=['name', 'description', 'contact_info', 'website']).to_excel(
                    writer, sheet_name='Manufacturers', index=False)
                pd.DataFrame(columns=['manufacturer_name', 'batch_number', 'device_type', 'notes']).to_excel(
                    writer, sheet_name='Batches', index=False)
                pd.DataFrame(columns=[
                    'manufacturer_name', 'batch_number', 'device_serial', 'spec_name',
                    'measurement', 'unit', 'lower_limit', 'nominal', 'upper_limit',
                    'test_date', 'notes'
                ]).to_excel(writer, sheet_name='Specs', index=False)