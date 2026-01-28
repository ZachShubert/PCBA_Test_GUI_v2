import os
import sys
import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QWidget

from src.gui.mainWindow import Main_Window
# from src.gui.splashWindow import SplashWindow

import tomli as tomllib

# from src.appPackage.helpers.logging_helper import setup_logging

# with open("bench_config.toml", "rb") as file:
#     bench_configuration = tomllib.load(file)
#
# __version__ = bench_configuration["metadata"]["version"]

# setup_logging()
logger = logging.getLogger(__name__)


def main():
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--enable-gpu-rasterization --enable-zero-copy --ignore-gpu-blacklist"

    # Must be set before QApplication instance
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    # Ensure gui's base font is clear
    myFont = QFont("63 12pt Titilliun Web SemiBold")
    myFont.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    QApplication.setFont(myFont)

    # create application
    app = QApplication(sys.argv)

    # 1. Create the splash window and main window but don't show yet
    main_window = Main_Window(__version__)
    splash_window = SplashWindow(__version__)

    # 2. When startup tasks are finished, close the splash window and show the main window
    def on_tasks_finished():
        main_window.show_and_fade_in()

    # 3. connect the splash finish to the main window start
    splash_window.start_up_animation_finished.connect(on_tasks_finished)

    # 4. show the splash window
    splash_window.open_splash_window()
    sys.exit(app.exec())


if __name__ == "__main__":
    """Main entry point."""

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Starting PCBA Database Application")

    # Create application
    app = QApplication(sys.argv)

    # Create database manager
    try:
        from src.database import DatabaseManager

        db_manager = DatabaseManager()
        logger.info("✓ Database manager created successfully")
    except Exception as e:
        logger.error(f"✗ Failed to create database manager: {e}")
        db_manager = None

    # Create main window with database manager
    window = Main_Window(db_manager)
    window.show()

    logger.info("✓ Application started")
    sys.exit(app.exec())