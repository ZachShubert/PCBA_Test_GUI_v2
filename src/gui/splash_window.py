import os
import sys
from pathlib import Path

from PyQt6 import uic, QtCore, QtWidgets
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
    QProgressBar,
    QFrame,
)


class SplashWindow(QMainWindow):
    startup_animation_finished = QtCore.pyqtSignal()

    def __init__(self, version: str):
        super().__init__()

        self.version = version

        # Load UI file
        ui_path = Path(__file__).parent / "user_interfaces" / "SplashScreen.ui"
        uic.loadUi(ui_path, self)

        # Window flags
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint)
        self.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True
        )

        # Init UI references
        self.init_gui_names()

        # Logo
        # logo_path = Path(__file__).parent / "user_interfaces" / "Voyager_Logo_circle.png"
        # self.logo_label.setPixmap(QPixmap(logo_path))


        # Animations
        self.init_fade_out_animation()

    def open_splash_window(self):
        self.show()
        self.logo_animation()
        self.description_animation()


# =========================================================
# Animations
# =========================================================
    def logo_animation(self):
        effect = QtWidgets.QGraphicsOpacityEffect(self.logo_label)
        self.logo_label.setGraphicsEffect(effect)

        self.logo_opacity_animation = QtCore.QPropertyAnimation(
            effect, b"opacity", self
        )
        self.logo_opacity_animation.setDuration(1500)
        self.logo_opacity_animation.setStartValue(0.0)
        self.logo_opacity_animation.setEndValue(1.0)
        self.logo_opacity_animation.setEasingCurve(
            QtCore.QEasingCurve.Type.InOutCubic
        )
        self.logo_opacity_animation.start()

    def description_animation(self):
        effect = QtWidgets.QGraphicsOpacityEffect(self.details_frame)
        self.details_frame.setGraphicsEffect(effect)

        geometry_anim = QtCore.QPropertyAnimation(
            self.details_frame, b"maximumHeight", self
        )
        geometry_anim.setDuration(1500)
        geometry_anim.setStartValue(0)
        geometry_anim.setEndValue(228)
        geometry_anim.setEasingCurve(
            QtCore.QEasingCurve.Type.InOutCubic
        )

        opacity_anim = QtCore.QPropertyAnimation(
            effect, b"opacity", self
        )
        opacity_anim.setDuration(500)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)

        self.description_animation_group = QtCore.QParallelAnimationGroup(self)
        self.description_animation_group.addAnimation(geometry_anim)
        self.description_animation_group.addAnimation(opacity_anim)

        self.description_animation_group.finished.connect(
            self.fade_out_animation.start
        )
        self.description_animation_group.start()

    def init_fade_out_animation(self):
        self.fade_out_animation = QtCore.QPropertyAnimation(
            self, b"windowOpacity", self
        )
        self.fade_out_animation.setDuration(500)
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.setEasingCurve(
            QtCore.QEasingCurve.Type.InOutCubic
        )
        self.fade_out_animation.finished.connect(self.loading_finished)

# =========================================================
# UI helpers
# =========================================================

    @QtCore.pyqtSlot(int, str)
    def update_progress(self, value: int, status: str):
        self.progressBar.setValue(value)
        self.progressBar_label.setText(f"{value}%")
        self.status_label.setText(status)


    def loading_finished(self):
        self.startup_animation_finished.emit()
        self.close()

    def init_gui_names(self):
        self.init_labels()
        self.init_progress_bars()
        self.init_frames()

    def init_labels(self):
        self.logo_label = self.findChild(QLabel, "logo_label")

        self.AppName_label = self.findChild(QLabel, "AppName_label")
        self.AppName_label.setText("Voyager 1088")

        self.AppDescription_label = self.findChild(
            QLabel, "AppDescription_label"
        )
        self.AppDescription_label.setText(
            "PIA / PMT Test Fixture Database"
        )

        self.version_label = self.findChild(QLabel, "version_label")
        self.version_label.setText(f"Version: {self.version}")

        self.status_label = self.findChild(QLabel, "status_label")
        self.progressBar_label = self.findChild(
            QLabel, "progress_Label"
        )

    def init_progress_bars(self):
        self.progressBar = self.findChild(QProgressBar, "progressBar")

    def init_frames(self):
        self.details_frame = self.findChild(QFrame, "details_frame")
        self.progressBar_frame = self.findChild(
            QFrame, "ProgressBar_frame"
        )
        self.logo_frame = self.findChild(QFrame, "logo_frame")
