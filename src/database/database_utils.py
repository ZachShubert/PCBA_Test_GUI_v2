# ======================
# Standard Library
# ======================
import os
import sys
import logging
from collections import defaultdict
from datetime import datetime, timedelta

# ======================
# Third Party
# ======================
import pandas as pd
from sqlalchemy import (
    create_engine,
    inspect,
    text,
    and_,
    not_,
    exists,
    func,
)
from sqlalchemy.orm import sessionmaker, aliased

# ======================
# Project Imports - FIXED PATHS
# ======================
from src.database.base import get_default_db_path, get_engine, get_session_factory, init_database
from src.database.database_device_tables import PCBABoard, PMT
from src.database.database_test_log_tables import TestLog, SubTest, Spec

logger = logging.getLogger(__name__)


# ============================================================
# Database Paths
# ============================================================

# Use the centralized database path from base.py
DB_PATH = get_default_db_path()
DB_EXCEL_PATH = DB_PATH.replace('.db', '.xlsx')

DATABASE_URL = DB_PATH
DB_EXCEL_URL = DB_EXCEL_PATH


# ============================================================
# Engine / Session Helpers
# ============================================================

def setup_database(db_url: str = DATABASE_URL):
    """
    Set up database and return a session.
    
    Args:
        db_url: Database path
        
    Returns:
        SQLAlchemy Session
    """
    logger.info(f"Setting up database: {db_url}")
    init_database(db_url)
    Session = get_session_factory(db_url)
    return Session()


def start_new_session(db_url: str = DATABASE_URL):
    """
    Start a new database session.
    
    Args:
        db_url: Database path
        
    Returns:
        SQLAlchemy Session
    """
    Session = get_session_factory(db_url)
    return Session()


# ============================================================
# Simple Insert Helpers
# ============================================================

def add_pmt_to_database(session, pmt: PMT):
    session.add(pmt)
    session.commit()


def add_pcba_to_database(session, pcba: PCBABoard):
    session.add(pcba)
    session.commit()


# ============================================================
# Basic Find Helpers
# ============================================================

def find_board_by_serial(session, serial_number):
    return (
        session.query(PCBABoard)
        .filter(PCBABoard.serial_number == serial_number)
        .first()
    )


def find_boards_by_part_number(session, part_number):
    return (
        session.query(PCBABoard)
        .filter(PCBABoard.part_number == part_number)
        .all()
    )


def find_boards_with_passing_specs(session):
    return (
        session.query(PCBABoard)
        .join(TestLog)
        .join(SubTest)
        .join(Spec)
        .filter(Spec.result.is_(True))
        .all()
    )


def find_boards_with_all_specs_passing(session):
    failing_spec = aliased(Spec)

    return (
        session.query(PCBABoard)
        .filter(
            not_(
                exists().where(
                    and_(
                        failing_spec.test_log_id == TestLog.id,
                        TestLog.pia_board_id == PCBABoard.id,
                        failing_spec.result.is_(False),
                    )
                )
            )
        )
        .all()
    )


# ============================================================
# Database Introspection
# ============================================================

def count_tables_in_database(db_url: str = DATABASE_URL):
    engine = create_engine(f"sqlite:///{db_url}")
    inspector = inspect(engine)

    tables = inspector.get_table_names()
    print(f"Total tables in database: {len(tables)}")
    print("Tables:", tables)
    return len(tables)


def count_rows_in_table(table_name, db_url: str = DATABASE_URL):
    engine = create_engine(f"sqlite:///{db_url}")

    with engine.connect() as connection:
        result = connection.execute(
            text(f"SELECT COUNT(*) FROM {table_name}")
        )
        count = result.scalar()

    print(f"Table '{table_name}' has {count} rows")
    return count


def count_rows_in_all_tables(db_url: str = DATABASE_URL):
    engine = create_engine(f"sqlite:///{db_url}")
    inspector = inspect(engine)

    total_count = 0

    with engine.connect() as connection:
        for table in inspector.get_table_names():
            try:
                result = connection.execute(
                    text(f"SELECT COUNT(*) FROM {table}")
                )
                count = result.scalar()
                total_count += count
                print(f"{table}: {count} rows")
            except Exception as e:
                logger.error(f"Failed counting table '{table}': {e}")

    return total_count


# ============================================================
# Export Utilities
# ============================================================

def export_database_to_excel(
    db_url: str = DATABASE_URL,
    excel_path: str = DB_EXCEL_URL,
):
    engine = create_engine(f"sqlite:///{db_url}")
    inspector = inspect(engine)

    table_names = inspector.get_table_names()
    num_tables = len(table_names)
    sheets_written = 0

    with engine.connect() as connection:
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            for table in table_names:
                try:
                    df = pd.read_sql_query(
                        text(f"SELECT * FROM {table}"),
                        con=connection,
                    )

                    if df.empty:
                        logger.info(f"Table '{table}' empty — skipping")
                        continue

                    sheet_name = table[:31]
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    sheets_written += 1

                    percent = round((sheets_written / num_tables) * 100, 1)
                    bar = "#" * int(percent // 2) + "-" * (50 - int(percent // 2))
                    sys.stdout.write(f"\rExporting: [{bar}] {percent}%")
                    sys.stdout.flush()

                except Exception as e:
                    logger.error(f"Failed exporting '{table}': {e}")

    print("\nExport complete:", excel_path)
    return excel_path


# ============================================================
# Search Utilities
# ============================================================

def search_database_for_string(search_string, db_url: str = DATABASE_URL):
    engine = create_engine(f"sqlite:///{db_url}")
    inspector = inspect(engine)

    matches = []

    with engine.connect() as connection:
        for table in inspector.get_table_names():
            try:
                df = pd.read_sql_query(
                    text(f"SELECT * FROM {table}"),
                    con=connection,
                )

                for row_idx, row in df.iterrows():
                    for col in df.columns:
                        val = row[col]
                        if isinstance(val, str) and search_string.lower() in val.lower():
                            matches.append({
                                "table": table,
                                "column": col,
                                "row_index": row_idx,
                                "value": val,
                            })
            except Exception as e:
                logger.error(f"Search failed in '{table}': {e}")

    return matches


def find_matching_pia_boards(search_string, db_url: str = DATABASE_URL):
    engine = create_engine(f"sqlite:///{db_url}")
    inspector = inspect(engine)

    if "pia_board" not in inspector.get_table_names():
        logger.warning("No pia_board table found")
        return []

    with engine.connect() as connection:
        df = pd.read_sql_query(
            text("SELECT * FROM pia_board"),
            con=connection,
        )

    matches = []
    for _, row in df.iterrows():
        for col in df.columns:
            val = row[col]
            if isinstance(val, str) and search_string.lower() in val.lower():
                matches.append(row.to_dict())
                break

    return matches


# ============================================================
# Spec & Test Log Helpers
# ============================================================

def get_all_specs_of_full_test_by_name(session, spec_name):
    return (
        session.query(Spec)
        .join(SubTest, Spec.sub_test_id == SubTest.id)
        .join(TestLog, SubTest.test_log_id == TestLog.id)
        .filter(Spec.name == spec_name)
        .filter(TestLog.full_test_completed.is_(True))
        .all()
    )


def get_all_specs_of_subtest_from_completed_tests_only(
    session,
    subtest_name,
    exclude_outliers=False,
    tolerance=0.4,
    days_from_today=365,
):
    query = (
        session.query(Spec)
        .join(SubTest, Spec.sub_test_id == SubTest.id)
        .join(TestLog, SubTest.test_log_id == TestLog.id)
        .filter(SubTest.name == subtest_name)
        .filter(TestLog.full_test_completed.is_(True))
    )

    if days_from_today:
        cutoff = datetime.now() - timedelta(days=days_from_today)
        query = query.filter(TestLog.created_at > cutoff)

    if exclude_outliers:
        query = query.filter(
            and_(
                Spec.measurement > Spec.nominal - func.abs(Spec.nominal) * tolerance,
                Spec.measurement < Spec.nominal + func.abs(Spec.nominal) * tolerance,
            )
        )

    specs = query.all()
    grouped = defaultdict(list)

    for spec in specs:
        grouped[spec.name].append(spec)

    return grouped


def get_test_logs_for_pia_board(pia_board, db_url: str = DATABASE_URL):
    engine = create_engine(f"sqlite:///{db_url}")
    board_id = pia_board.id

    with engine.connect() as connection:
        df = pd.read_sql_query(
            text("SELECT * FROM test_log WHERE pia_board_id = :id"),
            con=connection,
            params={"id": board_id},
        )

    return df.to_dict(orient="records")


def get_test_log_html(test_log_id, db_url: str = DATABASE_URL):
    engine = create_engine(f"sqlite:///{db_url}")

    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT html_content FROM test_log WHERE id = :id"),
            {"id": test_log_id},
        ).fetchone()

    return result[0] if result else None


def get_test_log_html_path(test_log_id, db_url: str = DATABASE_URL):
    engine = create_engine(f"sqlite:///{db_url}")

    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT html_path FROM test_log WHERE id = :id"),
            {"id": test_log_id},
        ).fetchone()

    return result[0] if result else None
