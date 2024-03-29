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

from PyQt5 import QtCore


class Logger(logging.Handler):
    def set_qt_signal(self, qt_signal: QtCore.pyqtSignal):
        """
        Sets pyqtSignal for logs redirection
        :param qt_signal:
        :return:
        """
        self.qt_signal = qt_signal

        # Add log level
        formatter = logging.Formatter(fmt="[%(levelname)-8s] %(message)s", datefmt="%H:%M:%S")
        self.setFormatter(formatter)

    def emit(self, record):
        """
        Redirects logs to pyqtSignal
        :param record:
        :return:
        """
        try:
            self.qt_signal.emit(self.format(record))
        except Exception as e:
            print(e)