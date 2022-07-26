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

import sys

import PyQt5
from PyQt5 import QtCore
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication

POSITION_LEFT = 0
POSITION_TOP = 1
POSITION_RIGHT = 2
POSITION_BOTTOM = 3


class Bar(PyQt5.QtWidgets.QWidget):
    def __init__(self):
        """
        Initializes Bar window
        """
        super(Bar, self).__init__()

        # Local variables
        self.bar_position = POSITION_LEFT
        self.invert = False

        # Display markers always on top
        self.setWindowFlags(QtCore.Qt.Tool
                            | QtCore.Qt.CustomizeWindowHint
                            | QtCore.Qt.FramelessWindowHint
                            | QtCore.Qt.WindowStaysOnTopHint
                            | QtCore.Qt.BypassWindowManagerHint
                            | QtCore.Qt.X11BypassWindowManagerHint)

        # Create first QApplication if no created
        if PyQt5.QtWidgets.QApplication.instance() is None:
            PyQt5.QtWidgets.QApplication(sys.argv)

    def paintEvent(self, event):
        q_painter = PyQt5.QtGui.QPainter(self)

        if self.invert:
            brush = PyQt5.QtGui.QBrush(PyQt5.QtGui.QColor(0, 0, 0, 255))
        else:
            brush = PyQt5.QtGui.QBrush(PyQt5.QtGui.QColor(255, 255, 255, 255))

        q_painter.setBrush(brush)
        q_painter.drawRect(QtCore.QRect(QtCore.QPoint(-1, -1), QtCore.QPoint(self.size().width() + 1,
                                                                             self.size().height() + 1)))

        # Set bar position and size
        if self.bar_position == POSITION_LEFT:
            q_painter.drawRect(QtCore.QRect(QtCore.QPoint(-1, -1), QtCore.QPoint(self.size().width() - 2,
                                                                                 self.size().height() + 1)))

        elif self.bar_position == POSITION_TOP:
            q_painter.drawRect(QtCore.QRect(QtCore.QPoint(-1, -1), QtCore.QPoint(self.size().width() + 1,
                                                                                 self.size().height() - 2)))

        elif self.bar_position == POSITION_RIGHT:
            q_painter.drawRect(QtCore.QRect(QtCore.QPoint(0, -1), QtCore.QPoint(self.size().width() + 1,
                                                                                self.size().height() + 1)))

        else:
            q_painter.drawRect(QtCore.QRect(QtCore.QPoint(-1, 0), QtCore.QPoint(self.size().width() + 1,
                                                                                self.size().height() + 1)))

    def show_bar(self, marker_size: int, bar_position: int, margins: list, invert: bool):
        # Get bar position
        self.bar_position = bar_position

        # Is bar black
        self.invert = invert

        # Get margins
        margin_left = int(margins[0])
        margin_top = int(margins[1])
        margin_right = int(margins[2])
        margin_bottom = int(margins[3])

        # Fix screen margins
        margin_bottom -= 1
        margin_right -= 1

        # Get screen coordinates
        screen_top_left = QApplication.desktop().availableGeometry().topLeft()
        screen_top_right = QApplication.desktop().availableGeometry().topRight()
        screen_bottom_right = QApplication.desktop().availableGeometry().bottomRight()
        screen_bottom_left = QApplication.desktop().availableGeometry().bottomLeft()

        # Calculate one block size in px
        marker_one_block_pixels = int(marker_size / (4 + 2))

        # Calculate total marker size
        marker_size_total = marker_size + marker_one_block_pixels * 2

        # Set bar position and size
        if self.bar_position == POSITION_LEFT:
            bar_left_start = QtCore.QPoint(screen_top_left.x() + margin_left,
                                           screen_top_left.y() + margin_top + marker_size_total)
            bar_left_height = screen_bottom_right.y() - margin_bottom - marker_size_total - bar_left_start.y()
            self.setGeometry(bar_left_start.x(), bar_left_start.y(), marker_one_block_pixels, bar_left_height)

        elif self.bar_position == POSITION_TOP:
            bar_top_start = QtCore.QPoint(screen_top_left.x() + margin_left + marker_size_total,
                                          screen_top_left.y() + margin_top)
            bar_top_width = screen_top_right.x() - margin_right - marker_size_total - bar_top_start.x()
            self.setGeometry(bar_top_start.x(), bar_top_start.y(), bar_top_width, marker_one_block_pixels)

        elif self.bar_position == POSITION_RIGHT:
            bar_right_start = QtCore.QPoint(screen_top_right.x() - margin_right - marker_one_block_pixels,
                                            screen_top_right.y() + margin_top + marker_size_total)
            bar_right_height = screen_bottom_left.y() - margin_bottom - marker_size_total - bar_right_start.y()
            self.setGeometry(bar_right_start.x(), bar_right_start.y(), marker_one_block_pixels, bar_right_height)

        else:
            bar_bottom_start = QtCore.QPoint(screen_bottom_left.x() + margin_left + marker_size_total,
                                             screen_bottom_left.y() - margin_bottom - marker_one_block_pixels)
            bar_bottom_width = screen_bottom_right.x() - margin_right - marker_size_total - bar_bottom_start.x()
            self.setGeometry(bar_bottom_start.x(), bar_bottom_start.y(), bar_bottom_width, marker_one_block_pixels)

        self.update()
        self.show()
