import logging
from PyQt6.QtCore import QObject, pyqtSignal
from sqlalchemy import select, func

from src.database.base import get_session_factory
from src.database.database_test_log_tables import Spec

logger = logging.getLogger(__name__)


class DatabaseQueryWorker(QObject):
    # Signals
    init_progress = pyqtSignal(int)     # total number of rows
    increment_progress = pyqtSignal()   # increment by 1
    finished = pyqtSignal(list)         # results list
    error = pyqtSignal(str)

    def __init__(self, stmt):
        super().__init__()
        self._session_factory = get_session_factory()
        self._stmt = stmt
        self._cancel = False
        self.results = []

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            with self._session_factory() as session:
                # -----------------------------
                # Count query for progress bar
                # -----------------------------
                count_stmt = (
                    select(func.count())
                    .select_from(
                        self._stmt.with_only_columns(Spec.id)
                        .distinct()
                        .order_by(None)
                        .subquery()
                    )
                )

                total = session.execute(count_stmt).scalar_one()
                self.init_progress.emit(total)

                if total == 0:
                    self.finished.emit(self.results)
                    return

                # -----------------------------
                # Main query loop
                # -----------------------------
                result_iter = (
                    session.execute(self._stmt)
                    .scalars()
                    .yield_per(100)
                )

                for measurement in result_iter:
                    if self._cancel:
                        break

                    # Force-load relationships (avoid lazy loading on gui thread)
                    sub_test = measurement.sub_test
                    test_log = sub_test.test_log if sub_test else None

                    measurement.sub_test = sub_test
                    measurement.test_log = test_log
                    measurement.pia = test_log.pia_board if test_log else None
                    measurement.pmt = test_log.pmt_device if test_log else None

                    self.results.append(measurement)
                    self.increment_progress.emit()

        except Exception as e:
            logger.exception("Database query failed")
            self.error.emit(str(e))

        finally:
            logger.info("Database query complete.")
            self.finished.emit(self.results)
