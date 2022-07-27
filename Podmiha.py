"""
 Copyright (C) 2022 Fern Lane, Podmiha project

 Licensed under the GNU Affero General Public License, Version 3.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

       https://www.gnu.org/licenses/agpl-3.0.en.html

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.

 IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES OR
 OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
 ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
 OTHER DEALINGS IN THE SOFTWARE.
"""
import ctypes
import logging
import math
import os
import sys
import threading
import time

import PyQt5
import cv2
import imutils
import psutil as psutil
import pyvirtualcam
import qimage2ndarray
import win32com
from PyQt5 import uic
from PyQt5.QtCore import QUrl, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidgetItem, QHeaderView, QVBoxLayout, QWidget, QMessageBox
import numpy as np
from PyQt5 import uic, QtGui, Qt, QtCore
from PyQt5.QtGui import QPen, QColor
from PyQt5 import uic, QtGui, Qt, QtCore
import csv
import json
from PIL import ImageGrab
import win32api
from cv2 import aruco

import Bar
import Flicker
import winguiauto
import win32gui
import win32con

import Marker
import SettingsHandler
import Logger
import OpenCVHandler
import HTTPStreamer

# https://github.com/aler9/rtsp-simple-server/releases/tag/v0.19.3
# https://gstreamer.freedesktop.org/data/pkg/windows/1.20.3/msvc/gstreamer-1.0-msvc-x86_64-1.20.3.msi
# - TODO: Записать шум отдельным файлом FULLHD и брать из него
# - TODO: Добавить рескейлинг + JPEG артифакты (кодировать в JPEG)
# TODO: сделать решулировки яркости и контрастности
# TODO: сделать вывод в RTSP стрим (для виртуалки)
# - TODO: добавить размытие
# - TODO: сделать глобальный выход при закрытии + спрашивать подтверждение на выход
# ? TODO: сделать размыливание границ
# - TODO: попробовать сделать просто поиск черной рамки экрана (добавить белую рамку)
# - TODO: пофиксить кадр при отключении камеры
# - TODO: определять яркость не через warp а рисуя всё что не маркер черным и беря max
# TODO: добавить фильтрацию кординат маркеров
# - TODO: шум не ресайзить а просто кропить
# - TODO: добавить контроль времени кадра
# - TODO: попробовать ИНВЕРТИРОВАТЬ маркеры
# ? TODO: сделать переключение между градиентом и просто срежней яркостью
# - TODO: фейк миганием экрана
# - TODO: сделать быстрое переключение между режимами фейка
# TODO: добавить возможность просто отобразить нужное окно на весь экран и при нажатии на эту картинку (или ещё что-то) включется ARUCO


APP_VERSION = "1.0.0"

SETTINGS_FILE = "settings.json"

UPDATE_SETTINGS_AFTER_MS = 500


class Window(QMainWindow):
    update_logs = QtCore.pyqtSignal(str)  # QtCore.Signal(str)
    update_preview = QtCore.pyqtSignal(QPixmap)  # QtCore.Signal(QPixmap)

    def __init__(self):
        super(Window, self).__init__()

        # List of opened applications
        self.available_windows_titles = []

        # Timer for write new settings
        self.settings_timer = QTimer()

        # Load GUI from file
        uic.loadUi("gui.ui", self)

        # Set window title
        self.setWindowTitle("Podmiha " + APP_VERSION)

        # Set icon
        self.setWindowIcon(QtGui.QIcon("icon.png"))

        # Initialize settings class
        self.settings_handler = SettingsHandler.SettingsHandler(SETTINGS_FILE)

        # Connect signals
        self.update_logs.connect(self.log.appendPlainText)
        self.update_preview.connect(self.preview.setPixmap)

        # Connect buttons
        self.camera_btn_mode_open = True
        self.btn_open_camera.clicked.connect(self.open_camera)
        self.btn_refresh_windows.clicked.connect(self.refresh_windows)
        self.btn_show_fullscreen.clicked.connect(self.show_fullscreen)
        self.input_image_mode.clicked.connect(self.change_preview_mode)
        self.window_image_mode.clicked.connect(self.change_preview_mode)
        self.output_image_mode.clicked.connect(self.change_preview_mode)

        # Initialize logger
        self.setup_logger()
        logging.info("Podmiha version: " + APP_VERSION)

        # Initialize HTTP server
        self.http_streamer = HTTPStreamer.HTTPStreamer(self.settings_handler)

        # Initialize flicker
        self.flicker = Flicker.Flicker(self.settings_handler)
        self.flicker.update_position([0, 0, 0, 0])

        # Initialize opencv class
        self.opencv_handler = OpenCVHandler.OpenCVHandler(self.settings_handler, self.http_streamer, self.flicker,
                                                          self.update_preview, self.preview)

        # Show GUI
        self.show()

        # Parse settings
        self.settings_handler.read_from_file()

        # Initialize markers
        self.marker_top_left = Marker.Marker()
        self.marker_top_right = Marker.Marker()
        self.marker_bottom_right = Marker.Marker()
        self.marker_bottom_left = Marker.Marker()

        # Initialize bars
        self.bar_left = Bar.Bar()
        self.bar_top = Bar.Bar()
        self.bar_right = Bar.Bar()
        self.bar_bottom = Bar.Bar()

        # Update GUI
        self.show_settings()
        self.write_settings()

        # Connect settings updater
        self.camera_id.valueChanged.connect(self.update_settings)
        self.use_dshow.clicked.connect(self.write_settings)
        self.camera_exposure.valueChanged.connect(self.update_settings)
        self.camera_exposure_auto.clicked.connect(self.write_settings)
        self.camera_focus.valueChanged.connect(self.update_settings)
        self.camera_focus_auto.clicked.connect(self.write_settings)
        self.fake_screen_checkbox.clicked.connect(self.write_settings)
        self.windows_titles.currentTextChanged.connect(self.update_settings)
        self.window_capture_stable.clicked.connect(self.write_settings)
        self.window_capture_experimental.clicked.connect(self.write_settings)
        self.window_crop_left.valueChanged.connect(self.update_settings)
        self.window_crop_top.valueChanged.connect(self.update_settings)
        self.window_crop_right.valueChanged.connect(self.update_settings)
        self.window_crop_bottom.valueChanged.connect(self.update_settings)
        self.fake_type_aruco.clicked.connect(self.write_settings)
        self.fake_type_flicker.clicked.connect(self.write_settings)
        self.flicker_duration.valueChanged.connect(self.update_settings)
        self.flicker_interval.valueChanged.connect(self.update_settings)
        self.frame_blending.clicked.connect(self.write_settings)
        self.stretch_scale_x.valueChanged.connect(self.update_settings)
        self.stretch_scale_y.valueChanged.connect(self.update_settings)
        self.brightness_gradient.clicked.connect(self.write_settings)
        self.aruco_size.valueChanged.connect(self.update_settings)
        self.aruco_invert_checkbox.clicked.connect(self.write_settings)
        self.aruco_margin_left.valueChanged.connect(self.update_settings)
        self.aruco_margin_top.valueChanged.connect(self.update_settings)
        self.aruco_margin_right.valueChanged.connect(self.update_settings)
        self.aruco_margin_bottom.valueChanged.connect(self.update_settings)
        self.id_tl.valueChanged.connect(self.update_settings)
        self.id_tr.valueChanged.connect(self.update_settings)
        self.id_br.valueChanged.connect(self.update_settings)
        self.id_bl.valueChanged.connect(self.update_settings)
        self.virtual_camera_enabled.clicked.connect(self.write_settings)
        self.http_stream_enabled.clicked.connect(self.write_settings)
        self.output_blur_radius.valueChanged.connect(self.update_settings)
        self.noise_amount.valueChanged.connect(self.update_settings)
        self.http_server_ip.textChanged.connect(self.update_settings)
        self.http_server_port.valueChanged.connect(self.update_settings)
        self.jpeg_quality.valueChanged.connect(self.update_settings)
        self.output_width.valueChanged.connect(self.resize_output_width)
        self.output_height.valueChanged.connect(self.resize_output_height)

        # Connect timer
        self.settings_timer.timeout.connect(self.write_settings)

        # Open flicker
        self.flicker.show()

        # Start OpenCV thread
        self.opencv_handler.start_opencv_thread()

        # Update preview mode
        self.change_preview_mode()

    def show_settings(self):
        """
        Updates gui elements from settings
        :return:
        """
        try:
            # Camera
            self.camera_id.setValue(int(self.settings_handler.settings["input_camera"]))
            self.use_dshow.setChecked(self.settings_handler.settings["use_dshow"])
            self.camera_exposure.setValue(int(self.settings_handler.settings["input_camera_exposure"]))
            self.camera_exposure_auto.setChecked(self.settings_handler.settings["input_camera_exposure_auto"])
            self.camera_focus.setValue(int(self.settings_handler.settings["input_camera_focus"]))
            self.camera_focus_auto.setChecked(self.settings_handler.settings["input_camera_focus_auto"])

            # Window capture
            self.fake_screen_checkbox.setChecked(self.settings_handler.settings["fake_screen"])
            self.refresh_windows()
            self.window_capture_stable.setChecked(int(self.settings_handler.settings["window_capture_method"])
                                                  == OpenCVHandler.WINDOW_CAPTURE_STABLE)
            self.window_capture_experimental.setChecked(int(self.settings_handler.settings["window_capture_method"])
                                                        == OpenCVHandler.WINDOW_CAPTURE_EXPERIMENTAL)
            self.window_crop_left.setValue(int(self.settings_handler.settings["window_crop"][0]))
            self.window_crop_top.setValue(int(self.settings_handler.settings["window_crop"][1]))
            self.window_crop_right.setValue(int(self.settings_handler.settings["window_crop"][2]))
            self.window_crop_bottom.setValue(int(self.settings_handler.settings["window_crop"][3]))
            self.stretch_scale_x.setValue(float(self.settings_handler.settings["stretch_scale"][0]))
            self.stretch_scale_y.setValue(float(self.settings_handler.settings["stretch_scale"][1]))
            self.brightness_gradient.setChecked(self.settings_handler.settings["brightness_gradient"])
            self.fake_type_aruco.setChecked(int(self.settings_handler.settings["fake_mode"])
                                            == OpenCVHandler.FAKE_MODE_ARUCO)
            self.fake_type_flicker.setChecked(int(self.settings_handler.settings["fake_mode"])
                                              == OpenCVHandler.FAKE_MODE_FLICKER)

            # Flicker
            self.flicker_duration.setValue(int(self.settings_handler.settings["flicker_duration"]))
            self.flicker_interval.setValue(int(self.settings_handler.settings["flicker_interval"]))
            self.frame_blending.setChecked(self.settings_handler.settings["frame_blending"])

            # ARUco markers
            self.aruco_size.setValue(int(self.settings_handler.settings["aruco_size"]))
            self.aruco_invert_checkbox.setChecked(self.settings_handler.settings["aruco_invert"])
            self.aruco_margin_left.setValue(int(self.settings_handler.settings["aruco_margins"][0]))
            self.aruco_margin_top.setValue(int(self.settings_handler.settings["aruco_margins"][1]))
            self.aruco_margin_right.setValue(int(self.settings_handler.settings["aruco_margins"][2]))
            self.aruco_margin_bottom.setValue(int(self.settings_handler.settings["aruco_margins"][3]))
            self.id_tl.setValue(int(self.settings_handler.settings["aruco_ids"][0]))
            self.id_tr.setValue(int(self.settings_handler.settings["aruco_ids"][1]))
            self.id_br.setValue(int(self.settings_handler.settings["aruco_ids"][2]))
            self.id_bl.setValue(int(self.settings_handler.settings["aruco_ids"][3]))

            # Output
            self.virtual_camera_enabled.setChecked(self.settings_handler.settings["virtual_camera_enabled"])
            self.http_stream_enabled.setChecked(self.settings_handler.settings["http_stream_enabled"])
            self.output_width.setValue(int(self.settings_handler.settings["output_size"][0]))
            self.output_height.setValue(int(self.settings_handler.settings["output_size"][1]))
            self.output_blur_radius.setValue(int(self.settings_handler.settings["output_blur_radius"]))
            self.noise_amount.setValue(float(self.settings_handler.settings["output_noise_amount"]))
            self.http_server_ip.setText(self.settings_handler.settings["http_server_ip"])
            self.http_server_port.setValue(int(self.settings_handler.settings["http_server_port"]))
            self.jpeg_quality.setValue(int(self.settings_handler.settings["jpeg_quality"]))

        except Exception as e:
            logging.exception(e)

    def update_settings(self):
        """
        Starts timer to write new settings
        :return:
        """
        # Start timer
        self.settings_timer.start(UPDATE_SETTINGS_AFTER_MS)

    def write_settings(self):
        """
        Writes new settings to file
        :return:
        """
        # Stop timer
        self.settings_timer.stop()

        # Camera
        self.settings_handler.settings["input_camera"] = int(self.camera_id.value())
        self.settings_handler.settings["use_dshow"] = self.use_dshow.isChecked()
        self.settings_handler.settings["input_camera_exposure"] = int(self.camera_exposure.value())
        self.settings_handler.settings["input_camera_exposure_auto"] = self.camera_exposure_auto.isChecked()
        self.settings_handler.settings["input_camera_focus"] = int(self.camera_focus.value())
        self.settings_handler.settings["input_camera_focus_auto"] = self.camera_focus_auto.isChecked()

        # Window capture
        self.settings_handler.settings["fake_screen"] = self.fake_screen_checkbox.isChecked()
        self.settings_handler.settings["window_title"] = str(self.windows_titles.currentText())
        self.settings_handler.settings["window_capture_method"] = OpenCVHandler.WINDOW_CAPTURE_STABLE \
            if self.window_capture_stable.isChecked() else OpenCVHandler.WINDOW_CAPTURE_EXPERIMENTAL
        self.settings_handler.settings["window_crop"][0] = int(self.window_crop_left.value())
        self.settings_handler.settings["window_crop"][1] = int(self.window_crop_top.value())
        self.settings_handler.settings["window_crop"][2] = int(self.window_crop_right.value())
        self.settings_handler.settings["window_crop"][3] = int(self.window_crop_bottom.value())
        self.settings_handler.settings["stretch_scale"][0] = float(self.stretch_scale_x.value())
        self.settings_handler.settings["stretch_scale"][1] = float(self.stretch_scale_y.value())
        self.settings_handler.settings["brightness_gradient"] = self.brightness_gradient.isChecked()
        self.settings_handler.settings["fake_mode"] = OpenCVHandler.FAKE_MODE_FLICKER \
            if self.fake_type_flicker.isChecked() else OpenCVHandler.FAKE_MODE_ARUCO

        # Flicker
        self.settings_handler.settings["flicker_duration"] = int(self.flicker_duration.value())
        self.settings_handler.settings["flicker_interval"] = int(self.flicker_interval.value())
        self.settings_handler.settings["frame_blending"] = self.frame_blending.isChecked()

        # ARUco markers
        self.settings_handler.settings["aruco_size"] = int(self.aruco_size.value())
        self.settings_handler.settings["aruco_invert"] = self.aruco_invert_checkbox.isChecked()
        self.settings_handler.settings["aruco_margins"][0] = int(self.aruco_margin_left.value())
        self.settings_handler.settings["aruco_margins"][1] = int(self.aruco_margin_top.value())
        self.settings_handler.settings["aruco_margins"][2] = int(self.aruco_margin_right.value())
        self.settings_handler.settings["aruco_margins"][3] = int(self.aruco_margin_bottom.value())
        self.settings_handler.settings["aruco_ids"][0] = int(self.id_tl.value())
        self.settings_handler.settings["aruco_ids"][1] = int(self.id_tr.value())
        self.settings_handler.settings["aruco_ids"][2] = int(self.id_br.value())
        self.settings_handler.settings["aruco_ids"][3] = int(self.id_bl.value())

        # Output
        self.settings_handler.settings["virtual_camera_enabled"] = self.virtual_camera_enabled.isChecked()
        self.settings_handler.settings["http_stream_enabled"] = self.http_stream_enabled.isChecked()
        self.settings_handler.settings["output_size"][0] = int(self.output_width.value())
        self.settings_handler.settings["output_size"][1] = int(self.output_height.value())
        self.settings_handler.settings["output_blur_radius"] = int(self.output_blur_radius.value())
        self.settings_handler.settings["output_noise_amount"] = float(self.noise_amount.value())
        self.settings_handler.settings["http_server_ip"] = self.http_server_ip.text()
        self.settings_handler.settings["http_server_port"] = int(self.http_server_port.value())
        self.settings_handler.settings["jpeg_quality"] = int(self.jpeg_quality.value())

        # Write new settings to file
        self.settings_handler.write_to_file()

        # Apply settings
        self.update_everything()

    def update_everything(self):
        """
        Updates all modules based on setting
        :return:
        """

        # Flicker mode
        if self.settings_handler.settings["fake_mode"] == OpenCVHandler.FAKE_MODE_FLICKER:
            # Disable ARUco controls and hide markers in flicker mode
            self.marker_top_left.hide()
            self.marker_top_right.hide()
            self.marker_bottom_right.hide()
            self.marker_bottom_left.hide()
            self.bar_left.hide()
            self.bar_top.hide()
            self.bar_right.hide()
            self.bar_bottom.hide()
            self.aruco_size.setEnabled(False)
            self.aruco_invert_checkbox.setEnabled(False)
            self.aruco_margin_left.setEnabled(False)
            self.aruco_margin_top.setEnabled(False)
            self.aruco_margin_right.setEnabled(False)
            self.aruco_margin_bottom.setEnabled(False)
            self.id_tl.setEnabled(False)
            self.id_tr.setEnabled(False)
            self.id_br.setEnabled(False)
            self.id_bl.setEnabled(False)

        # ARUco mode
        elif self.settings_handler.settings["fake_mode"] == OpenCVHandler.FAKE_MODE_ARUCO:
            # Fake screen enabled
            if self.settings_handler.settings["fake_screen"]:
                aruco_size = int(self.settings_handler.settings["aruco_size"])
                aruco_margins = self.settings_handler.settings["aruco_margins"]
                invert = self.settings_handler.settings["aruco_invert"]

                self.marker_top_left.show_marker(int(self.settings_handler.settings["aruco_ids"][0]),
                                                 aruco_size, Marker.POSITION_TOP_LEFT, aruco_margins, invert)
                self.marker_top_right.show_marker(int(self.settings_handler.settings["aruco_ids"][1]),
                                                  aruco_size, Marker.POSITION_TOP_RIGHT, aruco_margins, invert)
                self.marker_bottom_right.show_marker(int(self.settings_handler.settings["aruco_ids"][2]),
                                                     aruco_size, Marker.POSITION_BOTTOM_RIGHT, aruco_margins, invert)
                self.marker_bottom_left.show_marker(int(self.settings_handler.settings["aruco_ids"][3]),
                                                    aruco_size, Marker.POSITION_BOTTOM_LEFT, aruco_margins, invert)

                self.bar_left.show_bar(aruco_size, Bar.POSITION_LEFT, aruco_margins, invert)
                self.bar_top.show_bar(aruco_size, Bar.POSITION_TOP, aruco_margins, invert)
                self.bar_right.show_bar(aruco_size, Bar.POSITION_RIGHT, aruco_margins, invert)
                self.bar_bottom.show_bar(aruco_size, Bar.POSITION_BOTTOM, aruco_margins, invert)

            # Fake screen disabled
            else:
                self.marker_top_left.hide()
                self.marker_top_right.hide()
                self.marker_bottom_right.hide()
                self.marker_bottom_left.hide()
                self.bar_left.hide()
                self.bar_top.hide()
                self.bar_right.hide()
                self.bar_bottom.hide()
                self.aruco_size.setEnabled(True)
                self.aruco_invert_checkbox.setEnabled(True)
                self.aruco_margin_left.setEnabled(True)
                self.aruco_margin_top.setEnabled(True)
                self.aruco_margin_right.setEnabled(True)
                self.aruco_margin_bottom.setEnabled(True)
                self.id_tl.setEnabled(True)
                self.id_tr.setEnabled(True)
                self.id_br.setEnabled(True)
                self.id_bl.setEnabled(True)

        # Stretch works only in ARUco fake mode
        if self.settings_handler.settings["fake_mode"] == OpenCVHandler.FAKE_MODE_ARUCO:
            self.stretch_scale_x.setEnabled(True)
            self.stretch_scale_y.setEnabled(True)
        else:
            self.stretch_scale_x.setEnabled(False)
            self.stretch_scale_y.setEnabled(False)

        # Enable fullscreen button only if fake screen enabled
        self.btn_show_fullscreen.setEnabled(self.settings_handler.settings["fake_screen"])

        # OpenCVHandler
        self.opencv_handler.update_from_settings()

        # HTTP stream
        if self.settings_handler.settings["http_stream_enabled"]:
            self.http_server_ip.setEnabled(False)
            self.http_server_port.setEnabled(False)
            self.http_streamer.start_server()
            self.http_streamer.set_frame(self.opencv_handler.get_final_output_frame())
        else:
            self.http_streamer.stop_server()
            self.http_server_ip.setEnabled(True)
            self.http_server_port.setEnabled(True)

    def refresh_windows(self):
        """
        Updates available windows
        :return:
        """
        self.get_windows_list()
        self.windows_titles.clear()
        for window_title in self.available_windows_titles:
            self.windows_titles.addItem(window_title)
        window_title = self.settings_handler.settings["window_title"]
        if len(window_title) > 0 and window_title in self.available_windows_titles:
            self.windows_titles.setCurrentText(window_title)
        elif len(self.available_windows_titles) > 0:
            self.windows_titles.setCurrentText(self.available_windows_titles[0])

    def get_windows_list(self):
        """
        Updates list of actual opened windows
        :return:
        """
        self.available_windows_titles = []
        try:
            windows = []
            win32gui.EnumWindows(winguiauto._windowEnumerationHandler, windows)
            for hwnd, windowText, windowClass in windows:
                # Check if window is visible and not null
                if str(windowText).lower() != ("Podmiha " + APP_VERSION).lower() \
                        and win32gui.IsWindowVisible(hwnd) \
                        and len(str(windowText)) > 0 and hwnd is not None:
                    try:
                        # Get test image
                        rect = win32gui.GetWindowPlacement(hwnd)[-1]
                        image = np.array(ImageGrab.grab(rect))

                        # Check if window is real
                        if image.shape[0] > 10 and image.shape[1] > 10:
                            # Add to list
                            self.available_windows_titles.append(str(windowText))
                    except:
                        pass

            # Count number of opened windows
            logging.info("Found " + str(len(self.available_windows_titles)) + " open windows")
        except Exception as e:
            logging.exception(e)

    def show_fullscreen(self):
        """
        Temporarily opens a screenshot of a window in full screen
        :return:
        """
        self.flicker.open_fullscreen(self.opencv_handler.get_window_image())

    def setup_logger(self):
        """
        Sets up logs redirection and formatting
        :return:
        """
        # Initialize custom logger class for redirecting log messages
        logger = Logger.Logger()

        # Set QPlainTextEdit signal
        logger.set_qt_signal(self.update_logs)

        # Connect handler (redirection)
        logging.getLogger().addHandler(logger)

        # Enable global logging
        logging.root.setLevel(logging.NOTSET)

        # Print first message
        logging.info("Logs initialized")

    def open_camera(self):
        """
        Opens or closes camera input
        :return:
        """
        if self.camera_btn_mode_open:
            self.camera_btn_mode_open = False
            self.camera_id.setEnabled(False)
            self.use_dshow.setEnabled(False)
            self.btn_open_camera.setText("Close camera")
            self.opencv_handler.open_camera()
            self.opencv_handler.set_camera_capture_allowed(True)
        else:
            self.camera_btn_mode_open = True
            self.opencv_handler.close_camera()
            self.camera_id.setEnabled(True)
            self.use_dshow.setEnabled(True)
            self.btn_open_camera.setText("Open camera")

    def resize_output_width(self):
        if self.lock_resize.isChecked():
            self.output_height.disconnect()
            self.output_height.setValue(int(int(self.output_width.value()) / (16 / 9)))
            self.output_height.valueChanged.connect(self.resize_output_height)
        self.update_settings()

    def resize_output_height(self):
        if self.lock_resize.isChecked():
            self.output_width.disconnect()
            self.output_width.setValue(int(int(self.output_height.value()) * (16 / 9)))
            self.output_width.valueChanged.connect(self.resize_output_width)
        self.update_settings()

    def change_preview_mode(self):
        """
        Selects preview mode
        :return:
        """
        if self.input_image_mode.isChecked():
            self.opencv_handler.set_preview_mode(OpenCVHandler.PREVIEW_SOURCE)
        elif self.window_image_mode.isChecked():
            self.opencv_handler.set_preview_mode(OpenCVHandler.PREVIEW_WINDOW)
        elif self.output_image_mode.isChecked():
            self.opencv_handler.set_preview_mode(OpenCVHandler.PREVIEW_OUTPUT)

    def closeEvent(self, event):
        """
        Asks for exit confirmation
        :param event:
        :return:
        """
        # Close confirmation
        quit_msg = "Are you sure you want to exit the Podmiha?"
        reply = QMessageBox.warning(self, "Exit confirmation", quit_msg, QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            # Kill all threads
            current_system_pid = os.getpid()
            psutil.Process(current_system_pid).terminate()
            event.accept()

        # Stay in app
        else:
            event.ignore()


if __name__ == '__main__':
    # Replace icon in taskbar
    podmiha_app_ip = "f3rni.podmiha.podmiha." + APP_VERSION
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(podmiha_app_ip)

    # Add ffmpeg to PATH
    # current_dir = os.path.dirname(os.path.abspath(__file__))
    # os.environ["PATH"] += current_dir + "\\ffmpeg-2022-07-21-git-f7d510b33f-essentials_build"
    # os.environ["PATH"] += current_dir + "\\ffmpeg-2022-07-21-git-f7d510b33f-essentials_build\\bin"
    # os.environ["PATH"] += current_dir + "\\ffmpeg-2022-07-21-git-f7d510b33f-essentials_build\\presets"

    # Start app
    app = QApplication(sys.argv)
    app.setStyle('fusion')
    win = Window()
    sys.exit(app.exec_())
