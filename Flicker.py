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
import logging
import sys

import PyQt5
from PyQt5 import QtCore
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import QApplication
import cv2

import SettingsHandler
from qt_thread_updater import get_updater


class Flicker(PyQt5.QtWidgets.QLabel):
    update_geometry = QtCore.pyqtSignal(PyQt5.QtCore.QRect)  # QtCore.Signal(PyQt5.QtCore.QRect)
    signal_show = QtCore.pyqtSignal()  # QtCore.Signal()
    signal_raise = QtCore.pyqtSignal()  # QtCore.Signal()

    def __init__(self, settings_handler: SettingsHandler):
        """
        Initializes Flicker class
        """
        super(Flicker, self).__init__()

        self.settings_handler = settings_handler

        self.geometry_ = PyQt5.QtCore.QRect(0, 0, 1, 1)
        self.geometry_zero = PyQt5.QtCore.QRect(0, 0, 1, 1)
        self.frame = None
        self.width_ = 0
        self.height_ = 0
        self.force_fullscreen_enabled = False

        # Display markers always on top
        self.setWindowFlags(QtCore.Qt.Tool
                            | QtCore.Qt.CustomizeWindowHint
                            | QtCore.Qt.FramelessWindowHint
                            | QtCore.Qt.WindowStaysOnTopHint
                            | QtCore.Qt.BypassWindowManagerHint
                            | QtCore.Qt.X11BypassWindowManagerHint)

        self.update_geometry.connect(self.setGeometry)
        self.signal_show.connect(self.show)
        self.signal_raise.connect(self.raise_)

        self.mouseDoubleClickEvent = self.close_double_click

        # Create first QApplication if no created
        if PyQt5.QtWidgets.QApplication.instance() is None:
            PyQt5.QtWidgets.QApplication(sys.argv)

    def update_position(self, margins):
        # Get margins
        margin_left = int(margins[0])
        margin_top = int(margins[1])
        margin_right = int(margins[2])
        margin_bottom = int(margins[3])

        # Get screen coordinates
        screen_top_left = QApplication.desktop().availableGeometry().topLeft()
        screen_bottom_right = QApplication.desktop().availableGeometry().bottomRight()

        width = screen_bottom_right.x() - margin_right - (screen_top_left.x() + margin_left)
        height = screen_bottom_right.y() - margin_bottom - (screen_top_left.y() + margin_top)

        self.geometry_.setX(screen_top_left.x() + margin_left)
        self.geometry_.setY(screen_top_left.y() + margin_top)
        self.geometry_.setWidth(width)
        self.geometry_.setHeight(height)

        self.setGeometry(self.geometry_zero)

    def set_frame(self, frame):
        """
        Sets current frame
        :param frame: OpenCV frame
        :return:
        """
        self.frame = frame

        if self.frame is not None:
            try:
                # Resize
                self.width_ = self.geometry_.width()
                self.height_ = self.geometry_.height()
                frame_resized = cv2.resize(self.frame, (self.width_, self.height_))

                # Convert to pixmap
                pixmap = QPixmap.fromImage(
                    QImage(frame_resized.data, self.width_, self.height_, 3 * self.width_, QImage.Format_BGR888))

                # Update frame
                get_updater().call_latest(self.setPixmap, pixmap)
            except Exception as e:
                logging.exception(e)
                logging.error("Error setting new frame to the Flicker class")

    def set_force_fullscreen_enabled(self, force_fullscreen_enabled):
        """
        Sets force_fullscreen_enabled flag
        :param force_fullscreen_enabled:
        :return:
        """
        self.force_fullscreen_enabled = force_fullscreen_enabled

    def is_force_fullscreen_enabled(self):
        """
        :return: force_fullscreen_enabled flag
        """
        return self.force_fullscreen_enabled

    def open_(self):
        """
        Opens window fullscreen
        :return:
        """
        self.update_geometry.emit(self.geometry_)
        self.signal_show.emit()
        self.signal_raise.emit()

    def close_(self):
        """
        Hides window if no force_fullscreen_enabled flag
        :return:
        """
        if not self.force_fullscreen_enabled:
            self.update_geometry.emit(self.geometry_zero)

    def close_double_click(self, event):
        """
        Clears force_fullscreen_enabled flag and hides window
        :param event:
        :return:
        """
        self.force_fullscreen_enabled = False
        self.close_()
