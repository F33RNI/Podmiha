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

# Default app settings
import json
import logging
import os

SETTINGS_DEFAULT = {
    "input_camera": 0,
    "use_dshow": True,
    "input_camera_exposure": -6,
    "input_camera_exposure_auto": False,
    "input_camera_focus": 5,
    "input_camera_focus_auto": False,
    "fake_screen": False,
    "window_title": "",
    "window_capture_method": 0,
    "window_crop": [5, 8, 0, 4],
    "fake_mode": 0,
    "flicker_duration": 2,
    "flicker_interval": 10,
    "frame_blending": False,
    "stretch_scale": [1., 1.],
    "brightness_gradient": True,
    "aruco_size": 200,
    "aruco_invert": True,
    "aruco_margins": [0, 0, 0, 0],
    "aruco_ids": [0, 1, 2, 3],
    "virtual_camera_enabled": False,
    "http_stream_enabled": False,
    "output_size": [960, 540],
    "output_blur_radius": 1,
    "output_noise_amount": 0.,
    "http_server_ip": "localhost",
    "http_server_port": 8080,
    "jpeg_quality": 50,
    "audio_input_device_name": "",
    "audio_output_device_name": "",
    "audio_sample_rate": 32000,
    "audio_noise_amount": 0,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_bot_enabled": False,
    "telegram_message_plus": "+",
    "telegram_message_minus": "-"
    }


class SettingsHandler:
    def __init__(self, filename: str):
        """
        Initializes SettingsHandler class
        :param filename:
        """
        self.filename = filename
        self.settings = {}

    def read_from_file(self):
        """
        Parses and checks settings from file
        :return:
        """
        try:
            # Create new if file not exists
            if not os.path.exists(self.filename):
                logging.warning("Settings file not exists. Creating new one")
                self.settings = SETTINGS_DEFAULT
                self.write_to_file()

            # Open file
            settings_file = open(self.filename, "r")

            # Parse JSON
            try:
                self.settings = json.load(settings_file)
            except:
                logging.warning("Settings corrupted! Using default settings")
                self.settings = SETTINGS_DEFAULT
                self.write_to_file()

            # Check settings
            if not self.check_settings():
                logging.warning("Settings corrupted! Using default settings")
                self.settings = SETTINGS_DEFAULT
                self.write_to_file()

            # Print final message
            logging.info("Settings loaded")

        except Exception as e:
            logging.exception(e)

    def check_settings(self):
        """
        Checks settings
        :return:
        """
        try:
            default_keys = SETTINGS_DEFAULT.keys()
            for key in default_keys:
                if key not in self.settings:
                    return False
            return True
        except Exception as e:
            logging.exception(e)
            return False

    def write_to_file(self):
        """
        Writes settings to JSON file
        :return:
        """
        try:
            # Open file for writing
            settings_file = open(self.filename, "w")

            # Check if file is writable
            if settings_file.writable():
                # Write json to file
                json.dump(self.settings, settings_file, indent=4)
                logging.info("Settings written to file")
            else:
                logging.error("Settings file is not writable!")
                settings_file.close()
        except Exception as e:
            logging.exception(e)
