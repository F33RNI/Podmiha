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
import cv2
import numpy as np
import qimage2ndarray
from PyQt5 import QtCore
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication

POSITION_TOP_LEFT = 0
POSITION_TOP_RIGHT = 1
POSITION_BOTTOM_LEFT = 2
POSITION_BOTTOM_RIGHT = 3


class Marker(PyQt5.QtWidgets.QLabel):
    def __init__(self):
        """
        Initializes ARUco marker window
        """
        super(Marker, self).__init__()
        self.installEventFilter(self)

        self.size_ = 0
        self.one_block_pixels = 0

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

    def show_marker(self, marker_id: int, size_: int, position: int, margins: list, invert: bool):
        """
        Shows marker window on top
        :param marker_id: ID of marker (Integer)
        :param size_: size of marker (in px, without white border, Integer)
        :param position: Marker.POSITION_...
        :param margins: left, top, right, bottom as integers
        :param invert: invert colors of marker
        :return:
        """
        self.size_ = size_

        # Calculate one block size in px
        self.one_block_pixels = int(self.size_ / (4 + 2))

        # Calculate total marker size
        marker_size_total = self.size_ + self.one_block_pixels * 2

        # Create white background image
        final_image = np.ones((marker_size_total, marker_size_total), dtype="uint8") * 255

        # Draw ARUco marker
        marker_image = np.zeros((self.size_, self.size_, 1), dtype="uint8")
        cv2.aruco.drawMarker(cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50), marker_id, self.size_, marker_image, 1)

        # Copy ARUco image to the center
        final_image[self.one_block_pixels:self.size_ + self.one_block_pixels,
                    self.one_block_pixels:self.size_ + self.one_block_pixels] = marker_image[:, :, 0]

        # Set window title
        self.setWindowTitle("ARUco ID " + str(marker_id))

        # Get margins
        margin_left = int(margins[0])
        margin_top = int(margins[1])
        margin_right = int(margins[2])
        margin_bottom = int(margins[3])

        # Fix screen margins
        margin_bottom -= 1
        margin_right -= 1

        # Set marker position
        if position == POSITION_TOP_RIGHT:
            marker_position = QApplication.desktop().availableGeometry().topRight()
            marker_position.setX(marker_position.x() - (self.size_ + self.one_block_pixels * 2))
            marker_position.setX(marker_position.x() - margin_right)
            marker_position.setY(marker_position.y() + margin_top)

            final_image[self.one_block_pixels:, :1] = 0
            final_image[marker_size_total - 1:, :marker_size_total - self.one_block_pixels] = 0

        elif position == POSITION_BOTTOM_RIGHT:
            marker_position = QApplication.desktop().availableGeometry().bottomRight()
            marker_position.setX(marker_position.x() - (self.size_ + self.one_block_pixels * 2))
            marker_position.setY(marker_position.y() - (self.size_ + self.one_block_pixels * 2))
            marker_position.setX(marker_position.x() - margin_right)
            marker_position.setY(marker_position.y() - margin_bottom)

            final_image[:marker_size_total - self.one_block_pixels, :1] = 0
            final_image[:1, :marker_size_total - self.one_block_pixels] = 0

        elif position == POSITION_BOTTOM_LEFT:
            marker_position = QApplication.desktop().availableGeometry().bottomLeft()
            marker_position.setY(marker_position.y() - (self.size_ + self.one_block_pixels * 2))
            marker_position.setX(marker_position.x() + margin_left)
            marker_position.setY(marker_position.y() - margin_bottom)

            final_image[:1, self.one_block_pixels:] = 0
            final_image[:marker_size_total - self.one_block_pixels, marker_size_total - 1:] = 0

        else:
            marker_position = QApplication.desktop().availableGeometry().topLeft()
            marker_position.setX(marker_position.x() + margin_left)
            marker_position.setY(marker_position.y() + margin_top)

            final_image[self.one_block_pixels:, marker_size_total - 1:] = 0
            final_image[marker_size_total - 1:, self.one_block_pixels:] = 0

        # Invert marker if needed
        if invert:
            final_image = cv2.bitwise_not(final_image)

        # Draw marker on QLabel
        self.setPixmap(QPixmap.fromImage(qimage2ndarray.array2qimage(
            cv2.cvtColor(final_image, cv2.COLOR_GRAY2RGB))))

        # Show window
        self.move(marker_position)
        self.show()
