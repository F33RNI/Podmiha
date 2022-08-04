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
import threading
import time

import pyvirtualcam
from pyvirtualcam import PixelFormat

import SettingsHandler


class VirtualCamera:
    def __init__(self, settings_handler: SettingsHandler):
        """
        Initializes VirtualCamera class
        :param settings_handler: SettingsHandler class
        """
        self.settings_handler = settings_handler
        self.virtual_camera = None
        self.virtual_camera_driver = ""
        self.camera_thread_running = False
        self.frame = None

    def get_virtual_camera_driver(self):
        return self.virtual_camera_driver

    def open_camera(self):
        """
        Opens pyvirtualcam.Camera object
        :return:
        """
        if self.virtual_camera is None:
            try:
                width = int(self.settings_handler.settings["output_size"][0])
                height = int(self.settings_handler.settings["output_size"][1])
                self.virtual_camera = pyvirtualcam.Camera(width=width, height=height, fps=30, fmt=PixelFormat.BGR)
                if self.virtual_camera.device is not None:
                    # Get driver name
                    self.virtual_camera_driver = str(self.virtual_camera.device)
                    logging.info("Using virtual camera: " + self.virtual_camera_driver)

                    # Start main loop
                    self.camera_thread_running = True
                    thread = threading.Thread(target=self.camera_thread)
                    thread.start()
                    logging.info("Virtual camera thread: " + thread.getName())
                else:
                    logging.error("Virtual camera driver is None!")
                    self.virtual_camera.close()
            except Exception as e:
                logging.exception(e)
                logging.error("Error opening virtual camera driver")

    def close_camera(self):
        """
        Closes pyvirtualcam.Camera object
        :return:
        """
        if self.virtual_camera is not None:
            try:
                self.virtual_camera.close()
                self.virtual_camera = None
                self.camera_thread_running = False
                self.virtual_camera_driver = ""
            except Exception as e:
                logging.exception(e)
                logging.error("Error closing virtual camera driver")

    def set_frame(self, frame):
        """
        Sets frame
        :param frame:
        :return:
        """
        if frame is not None:
            self.frame = frame

    def camera_thread(self):
        """
        Virtual camera loop
        :return:
        """
        while self.camera_thread_running:
            try:
                if self.virtual_camera is not None and self.frame is not None:
                    self.virtual_camera.send(self.frame)
                    self.virtual_camera.sleep_until_next_frame()
                else:
                    time.sleep(0.1)
            except Exception as e:
                logging.exception(e)
                logging.error("Error sending frame via virtual camera!")
                time.sleep(0.1)

        logging.warning("Virtual camera loop finished")
