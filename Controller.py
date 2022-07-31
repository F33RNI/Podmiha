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

import PyQt5
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QFrame, QDesktopWidget

import TelegramHandler

CAMERA_STATE_ERROR_ACTIVE = 0
CAMERA_STATE_ERROR_PAUSED = 1
CAMERA_STATE_ACTIVE = 2
CAMERA_STATE_PAUSED = 3

MICROPHONE_STATE_ERROR_ACTIVE = 0
MICROPHONE_STATE_ERROR_PAUSED = 1
MICROPHONE_STATE_ACTIVE = 2
MICROPHONE_STATE_PAUSED = 3


class VLine(QFrame):
    """
    Creates vertical line
    """

    def __init__(self):
        """
        Simple Vertical line
        """
        super(VLine, self).__init__()
        self.setFrameShape(self.VLine | self.Sunken)


class Controller(QWidget):
    update_camera_icon = QtCore.pyqtSignal(QIcon)  # QtCore.Signal(QIcon)
    update_microphone_icon = QtCore.pyqtSignal(QIcon)  # QtCore.Signal(QIcon)

    def __init__(self, telegram_handler: TelegramHandler, update_show_main_gui: QtCore.pyqtSignal,
                 update_show_fullscreen: QtCore.pyqtSignal):
        """
        Initializes Controller class
        """
        super(Controller, self).__init__()

        # TelegramHandler class for sending +, - and screenshot
        self.telegram_handler = telegram_handler

        # Signal for showing main gui
        self.update_show_main_gui = update_show_main_gui

        # Signal for showing screenshot of fullscreen
        self.update_show_fullscreen = update_show_fullscreen

        # Internal variables
        self.camera_current_state = CAMERA_STATE_ERROR_PAUSED
        self.microphone_current_state = MICROPHONE_STATE_ERROR_PAUSED
        self.old_pos = QPoint(0, 0)
        self.timer = QTimer()
        self.request_camera_pause = True
        self.request_microphone_pause = True
        self.request_camera_resume = False
        self.request_microphone_resume = False

        # Icons
        # Camera
        self.icon_camera_error_active = QIcon("./icons/camera_error_active.png")
        self.icon_camera_error_paused = QIcon("./icons/camera_error_paused.png")
        self.icon_camera_active = QIcon("./icons/camera_active.png")
        self.icon_camera_paused = QIcon("./icons/camera_paused.png")
        # Microphone
        self.icon_microphone_error_active = QIcon("./icons/microphone_error_active.png")
        self.icon_microphone_error_paused = QIcon("./icons/microphone_error_paused.png")
        self.icon_microphone_active = QIcon("./icons/microphone_active.png")
        self.icon_microphone_paused = QIcon("./icons/microphone_paused.png")
        # Show screenshot
        self.icon_screenshot_show = QIcon("./icons/screenshot_show.png")
        # Send plus/minus/screenshot
        self.icon_send_plus = QIcon("./icons/send_plus.png")
        self.icon_send_minus = QIcon("./icons/send_minus.png")
        self.icon_send_screenshot = QIcon("./icons/screenshot_send.png")
        # Show gui
        self.icon_show_gui = QIcon("./icons/show_gui.png")

        # Display controller always on top
        self.setWindowFlags(QtCore.Qt.Tool
                            | QtCore.Qt.CustomizeWindowHint
                            | QtCore.Qt.FramelessWindowHint
                            | QtCore.Qt.WindowStaysOnTopHint
                            | QtCore.Qt.BypassWindowManagerHint
                            | QtCore.Qt.X11BypassWindowManagerHint)

        # Make window transparent
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.center()

        # Create button objects
        self.btn_camera_control = QPushButton()
        self.btn_microphone_control = QPushButton()
        self.btn_show_screenshot = QPushButton()
        self.btn_send_plus = QPushButton()
        self.btn_send_minus = QPushButton()
        self.btn_send_screenshot = QPushButton()
        self.btn_show_gui = QPushButton()

        # Make buttons transparent
        buttons_stylesheet = "QPushButton { background-color: rgba(255, 255, 255, 0); border :1px solid gray; }"
        self.btn_camera_control.setStyleSheet(buttons_stylesheet)
        self.btn_microphone_control.setStyleSheet(buttons_stylesheet)
        self.btn_show_screenshot.setStyleSheet(buttons_stylesheet)
        self.btn_send_plus.setStyleSheet(buttons_stylesheet)
        self.btn_send_minus.setStyleSheet(buttons_stylesheet)
        self.btn_send_screenshot.setStyleSheet(buttons_stylesheet)
        self.btn_show_gui.setStyleSheet(buttons_stylesheet)

        # Set initial icons
        self.btn_camera_control.setIcon(self.icon_camera_error_paused)
        self.btn_microphone_control.setIcon(self.icon_microphone_error_paused)
        self.btn_show_screenshot.setIcon(self.icon_screenshot_show)
        self.btn_send_plus.setIcon(self.icon_send_plus)
        self.btn_send_minus.setIcon(self.icon_send_minus)
        self.btn_send_screenshot.setIcon(self.icon_send_screenshot)
        self.btn_show_gui.setIcon(self.icon_show_gui)

        # Connect signals
        self.update_camera_icon.connect(self.btn_camera_control.setIcon)
        self.update_microphone_icon.connect(self.btn_microphone_control.setIcon)

        # Connect buttons
        self.btn_camera_control.clicked.connect(self.camera_control)
        self.btn_microphone_control.clicked.connect(self.microphone_control)
        self.btn_show_screenshot.clicked.connect(self.update_show_fullscreen)
        self.btn_send_plus.clicked.connect(self.telegram_handler.send_plus)
        self.btn_send_minus.clicked.connect(self.telegram_handler.send_minus)
        self.btn_send_screenshot.clicked.connect(self.telegram_handler.send_screenshot)
        self.btn_show_gui.clicked.connect(self.update_show_main_gui)

        # Create HBoxLayout and add buttons to it
        layout = QHBoxLayout()
        layout.addWidget(self.btn_camera_control)
        layout.addWidget(self.btn_microphone_control)
        layout.addWidget(self.btn_show_screenshot)
        layout.addWidget(VLine())
        layout.addWidget(self.btn_send_plus)
        layout.addWidget(self.btn_send_minus)
        layout.addWidget(self.btn_send_screenshot)
        layout.addWidget(VLine())
        layout.addWidget(self.btn_show_gui)
        self.setLayout(layout)
        self.setFixedSize(layout.sizeHint())

    def open_controller(self):
        """
        Opens controller window and starts timer
        :return:
        """
        # Show window
        self.old_pos = self.pos()
        self.show()

        # Raise controller every second
        self.timer.timeout.connect(self.raise_controller)
        self.timer.start(1000)

    def raise_controller(self):
        """
        Raises controller window
        :return:
        """
        # noinspection PyBroadException
        try:
            # self.setFocus(True)
            # self.activateWindow()
            self.raise_()
            # self.show()
        except:
            pass

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def mousePressEvent(self, event):
        self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPos() - self.old_pos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.old_pos = event.globalPos()

    def get_request_camera_pause(self):
        return self.request_camera_pause

    def get_request_microphone_pause(self):
        return self.request_microphone_pause

    def get_request_camera_resume(self):
        return self.request_camera_resume

    def get_request_microphone_resume(self):
        return self.request_microphone_resume

    def clear_request_camera_pause(self):
        self.request_camera_pause = False

    def clear_request_microphone_pause(self):
        self.request_microphone_pause = False

    def clear_request_camera_resume(self):
        self.request_camera_resume = False

    def clear_request_microphone_resume(self):
        self.request_microphone_resume = False

    def camera_control(self):
        """
        Toggles camera state
        :return:
        """
        # Paused -> Resume
        if self.camera_current_state == CAMERA_STATE_PAUSED\
                or self.camera_current_state == CAMERA_STATE_ERROR_PAUSED:
            self.request_camera_resume = True

        # Not paused -> Pause
        else:
            self.request_camera_pause = True

    def microphone_control(self):
        """
        Toggles microphone state
        :return:
        """
        # Paused -> Resume
        if self.microphone_current_state == MICROPHONE_STATE_PAUSED\
                or self.microphone_current_state == MICROPHONE_STATE_ERROR_PAUSED:
            self.request_microphone_resume = True

        # Not paused -> Pause
        else:
            self.request_microphone_pause = True

    def update_state_camera(self, new_state: int):
        """
        Updates camera icon
        :param new_state:
        :return:
        """
        self.camera_current_state = new_state
        if self.camera_current_state == CAMERA_STATE_ACTIVE:
            self.update_camera_icon.emit(self.icon_camera_active)
        elif self.camera_current_state == CAMERA_STATE_PAUSED:
            self.update_camera_icon.emit(self.icon_camera_paused)
        elif self.camera_current_state == CAMERA_STATE_ERROR_ACTIVE:
            self.update_camera_icon.emit(self.icon_camera_error_active)
        else:
            self.update_camera_icon.emit(self.icon_camera_error_paused)

    def update_state_microphone(self, new_state: int):
        """
        Updates microphone icon
        :param new_state:
        :return:
        """
        self.microphone_current_state = new_state
        if self.microphone_current_state == MICROPHONE_STATE_ACTIVE:
            self.update_microphone_icon.emit(self.icon_microphone_active)
        elif self.microphone_current_state == MICROPHONE_STATE_PAUSED:
            self.update_microphone_icon.emit(self.icon_microphone_paused)
        elif self.microphone_current_state == MICROPHONE_STATE_ERROR_ACTIVE:
            self.update_microphone_icon.emit(self.icon_microphone_error_active)
        else:
            self.update_microphone_icon.emit(self.icon_microphone_error_paused)

    def paintEvent(self, event):
        """
        Draws semi-transparent background
        :param event:
        :return:
        """
        q_painter = PyQt5.QtGui.QPainter(self)
        brush = PyQt5.QtGui.QBrush(PyQt5.QtGui.QColor(255, 255, 255, 10))
        q_painter.setBrush(brush)
        q_painter.drawRect(QtCore.QRect(QtCore.QPoint(-1, -1), QtCore.QPoint(self.size().width(),
                                                                             self.size().height())))
