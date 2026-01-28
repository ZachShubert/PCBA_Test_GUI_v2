# ======================
# Python / SQLAlchemy
# ======================
from sqlalchemy import asc, desc, func, and_, or_, select
from sqlalchemy.orm import joinedload
import logging
import hashlib

# ======================
# Project Imports - FIXED PATHS
# ======================
from src.database.database_device_tables import PCBABoard, PMT
from src.database.database_test_log_tables import TestLog, SubTest, Spec

logger = logging.getLogger(__name__)


def compute_file_sha256(filepath: str) -> bytes:
    """
    Compute SHA256 hash of file.

    Args:
        filepath: Path to file to hash

    Returns:
        SHA256 digest as bytes
    """
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.digest()


# ============================================================
# Top-Level Query Container
# ============================================================

class Queries:
    def __init__(self, session=None):
        self.session = session
        self.pmts = PMT_Queries(session)
        self.pias = PIA_Board_Queries(session)
        self.test_logs = Test_Log_PIA_Board_Queries(session)
        self.sub_tests = Sub_Test_Queries(session)
        self.specs = Spec_Queries(session)

    def find_matching_string(self, search_term: str):
        """
        Case-insensitive substring search across PCBA + PMT identifiers
        """
        term = f"%{search_term.lower()}%"

        return (
            self.session.query(TestLog)
            .join(TestLog.pia_board)
            .outerjoin(TestLog.pmt_device)
            .options(
                joinedload(TestLog.pia_board),
                joinedload(TestLog.pmt_device),
            )
            .filter(
                or_(
                    func.lower(PCBABoard.serial_number).like(term),
                    func.lower(PCBABoard.part_number).like(term),
                    func.lower(PMT.pmt_serial_number).like(term),
                )
            )
            .order_by(desc(TestLog.created_at))
            .all()
        )


# ============================================================
# PMT Queries
# ============================================================

class PMT_Queries:
    def __init__(self, session):
        self.session = session

    def get_all_serial_numbers(self):
        rows = self.session.query(PMT.pmt_serial_number).distinct().all()
        return [r[0] for r in rows]


# ============================================================
# PCBA Board Queries
# ============================================================

class PIA_Board_Queries:
    def __init__(self, session):
        self.session = session

    def get_all_serial_numbers(self):
        rows = self.session.query(PCBABoard.serial_number).distinct().all()
        return [r[0] for r in rows]

    def get_all_part_numbers(self):
        rows = self.session.query(PCBABoard.part_number).distinct().all()
        return [r[0] for r in rows]

    def find_by_serial(self, serial_number):
        return (
            self.session.query(PCBABoard)
            .filter(PCBABoard.serial_number == serial_number)
            .first()
        )

    def find_by_part_number(self, part_number):
        return (
            self.session.query(PCBABoard)
            .filter(PCBABoard.part_number == part_number)
            .all()
        )

    def count_by_full_test_log(self):
        return (
            self.session.query(PCBABoard)
            .join(TestLog)
            .filter(TestLog.full_test_completed.is_(True))
            .distinct()
            .count()
        )


# ============================================================
# Test Log Queries
# ============================================================

class Test_Log_PIA_Board_Queries:
    def __init__(self, session):
        self.session = session

    def count_by_location(self, location="PLexus"):
        count = (
            self.session.query(func.count(TestLog.id))
            .filter(TestLog.test_fixture == location)
            .scalar()
        )
        return location, count

    def get_html_content_from_id(self, test_log_id):
        tl = (
            self.session.query(TestLog)
            .filter(TestLog.id == test_log_id)
            .first()
        )
        return tl.html_content if tl else None

    def test_log_exists(self, test_log_path):
        html_hash = compute_file_sha256(test_log_path)

        exists = (
            self.session.query(TestLog.id)
            .filter(TestLog.html_hash == html_hash)
            .first()
        )

        return html_hash, exists is not None

    def get_recent(self, limit=100):
        return (
            self.session.query(TestLog)
            .order_by(desc(TestLog.created_at))
            .limit(limit)
            .all()
        )


# ============================================================
# SubTest Queries
# ============================================================

class Sub_Test_Queries:
    def __init__(self, session):
        self.session = session


# ============================================================
# Spec Queries (ORM + Core)
# ============================================================

class Spec_Queries:
    def __init__(self, session):
        self.session = session

    def get_all_spec_names(self):
        rows = self.session.query(Spec.name).distinct().all()
        return [r[0] for r in rows]

    def get_plot_spec_names(self):
        """Get spec names that have plot data (has_plot=True)."""
        rows = (
            self.session.query(Spec.name)
            .filter(Spec.has_plot == True)
            .distinct()
            .all()
        )
        return [r[0] for r in rows]

    def get_paired_spec_names(self, spec_name: str):
        """
        Get spec names that exist in the same test logs as the given spec.

        This is useful for relational plotting where we need measurements
        that can be paired together (same device, same test session).

        Args:
            spec_name: The reference spec name to find pairs for

        Returns:
            List of spec names that have paired data
        """
        # Get test_log_ids that have the reference spec
        test_log_ids_subquery = (
            self.session.query(TestLog.id)
            .join(SubTest, SubTest.test_log_id == TestLog.id)
            .join(Spec, Spec.sub_test_id == SubTest.id)
            .filter(Spec.name == spec_name)
            .distinct()
            .subquery()
        )

        # Get other spec names from those same test logs
        paired_specs = (
            self.session.query(Spec.name)
            .join(SubTest, SubTest.id == Spec.sub_test_id)
            .join(TestLog, TestLog.id == SubTest.test_log_id)
            .filter(TestLog.id.in_(select(test_log_ids_subquery)))
            .filter(Spec.name != spec_name)  # Exclude the reference spec itself
            .filter(Spec.measurement.isnot(None))  # Only specs with scalar values
            .distinct()
            .all()
        )

        return [r[0] for r in paired_specs]

    def get_statement(
            self,
            spec_name,
            filter_by_csv=None,
            filter_by_pia_serial_number=None,
            filter_by_pia_part_number=None,
            filter_by_pmt=None,
            filter_by_pmt_batch=None,
            filter_by_dates=None,
            include_only_full_tests=False,
            order_key=None,
    ):
        stmt = (
            select(Spec)
            .join(SubTest, SubTest.id == Spec.sub_test_id)
            .join(TestLog, TestLog.id == SubTest.test_log_id)
            .outerjoin(PCBABoard, PCBABoard.id == TestLog.pia_board_id)
            .outerjoin(PMT, PMT.id == TestLog.pmt_id)
            .where(Spec.name == spec_name)
        )

        if filter_by_csv:
            vals = [v.upper() for v in filter_by_csv]
            stmt = stmt.where(
                or_(
                    func.upper(PCBABoard.serial_number).in_(vals),
                    func.upper(PCBABoard.part_number).in_(vals),
                    func.upper(PMT.pmt_serial_number).in_(vals),
                )
            )

        if filter_by_pia_serial_number:
            stmt = stmt.where(PCBABoard.serial_number == filter_by_pia_serial_number)

        if filter_by_pia_part_number:
            stmt = stmt.where(PCBABoard.part_number == filter_by_pia_part_number)

        if filter_by_pmt:
            stmt = stmt.where(PMT.pmt_serial_number == filter_by_pmt)

        if filter_by_pmt_batch:
            stmt = stmt.where(PMT.batch_number == filter_by_pmt_batch)

        if filter_by_dates:
            start_dt, end_dt = filter_by_dates
            stmt = stmt.where(
                and_(
                    TestLog.created_at >= start_dt,
                    TestLog.created_at <= end_dt,
                )
            )

        if include_only_full_tests:
            stmt = stmt.where(TestLog.full_test_completed.is_(True))

        order_map = {
            "PIA Serial Number": PCBABoard.serial_number,
            "PIA Part Number": PCBABoard.part_number,
            "PMT Serial Number": PMT.pmt_serial_number,
            "Recent": desc(TestLog.created_at),
            "Test Name": TestLog.name,
            "Test Fixture": TestLog.test_fixture,
            "PMT Generation": PMT.generation,
            "PMT Batch": PMT.batch_number,
        }

        if order_key in order_map:
            stmt = stmt.order_by(order_map[order_key])

        return stmt