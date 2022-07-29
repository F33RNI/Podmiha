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
import audioop
import logging
import math
import threading
import time

import numpy as np
import pyaudio
from PyQt5 import QtCore

import SettingsHandler
import Controller

AUDIO_CHANNELS = 1
AUDIO_CHUNK_SIZE = 2048 * AUDIO_CHANNELS
AUDIO_FORMAT = pyaudio.paInt16
AUDIO_NP_FORMAT = np.int16
AUDIO_WIDTH = 2

DEVICE_TYPE_INPUT = 0
DEVICE_TYPE_OUTPUT = 1


class AudioHandler:
    def __init__(self, settings_handler: SettingsHandler, controller: Controller, update_audio_rms: QtCore.pyqtSignal):
        """
        Initializes AudioHandler class
        :param settings_handler: SettingsHandler class
        :param controller: Controller class
        :param update_audio_rms: qt signal for updating progress bar
        """
        self.settings_handler = settings_handler
        self.controller = controller
        self.update_audio_rms = update_audio_rms

        self.py_audio = pyaudio.PyAudio()
        self.input_stream = None
        self.output_stream = None
        self.input_output_sample_rate = 0
        self.audio_thread_running = False

    def get_device_list(self, device_type: int):
        """
        Gets list of device names
        :param device_type: DEVICE_TYPE_INPUT or DEVICE_TYPE_OUTPUT
        :return:
        """
        devices = []
        try:
            info = self.py_audio.get_host_api_info_by_index(0)
            device_count = info.get("deviceCount")

            for i in range(0, device_count):
                device = self.py_audio.get_device_info_by_host_api_device_index(0, i)
                if (device.get("maxInputChannels")) > 0 and device_type == DEVICE_TYPE_INPUT:
                    devices.append(device.get("name"))
                elif (device.get("maxOutputChannels")) > 0 and device_type == DEVICE_TYPE_OUTPUT:
                    devices.append(device.get("name"))
        except Exception as e:
            logging.exception(e)
            logging.error("Can't get list of audio devices")
        return devices

    def get_device_index_by_name(self, device_name: str):
        """
        Gets device index by it's name
        :param device_name: name of device from get_device_list()
        :return:
        """
        try:
            info = self.py_audio.get_host_api_info_by_index(0)
            device_count = info.get("deviceCount")
            for i in range(0, device_count):
                device = self.py_audio.get_device_info_by_host_api_device_index(0, i)
                if device_name.lower() in str(device.get("name")).lower():
                    return device.get("index")

        except Exception as e:
            logging.exception(e)
            logging.error("Can't get device index")

        return -1

    def open_input_device(self):
        """
        Opens input device
        :return:
        """
        if self.input_stream is None:
            try:
                device_name = str(self.settings_handler.settings["audio_input_device_name"])
                if len(device_name) > 0:
                    device_index = self.get_device_index_by_name(device_name)
                    self.input_output_sample_rate = int(self.settings_handler.settings["audio_sample_rate"])
                    if device_index >= 0:
                        self.input_stream = self.py_audio.open(
                            input_device_index=device_index,
                            format=AUDIO_FORMAT,
                            channels=AUDIO_CHANNELS,
                            rate=self.input_output_sample_rate,
                            input=True,
                            output=False,
                            frames_per_buffer=AUDIO_CHUNK_SIZE)
                        logging.info("Audio input opened: " + ("Yes" if self.input_stream.is_active() else "No"))
                        return self.input_stream.is_active()
                    else:
                        logging.error("No input device!")
                else:
                    logging.error("No input device!")
            except Exception as e:
                logging.exception(e)
                logging.error("Can't open input device")
        return False

    def close_input_device(self):
        """
        Closes input device
        :return:
        """
        if self.input_stream is not None:
            try:
                self.input_stream.stop_stream()
                self.input_stream.close()
                self.input_stream = None
            except Exception as e:
                logging.exception(e)
                logging.error("Can't close input device")

    def is_input_device_opened(self):
        """
        :return: true if input device is opened
        """
        if self.input_stream is not None:
            try:
                return self.input_stream.is_active()
            except:
                return False
        else:
            return False

    def open_output_device(self):
        """
        Opens output device
        :return:
        """
        if self.output_stream is None:
            try:
                device_name = str(self.settings_handler.settings["audio_output_device_name"])
                if len(device_name) > 0:
                    device_index = self.get_device_index_by_name(device_name)
                    self.input_output_sample_rate = int(self.settings_handler.settings["audio_sample_rate"])
                    if device_index >= 0:
                        self.output_stream = self.py_audio.open(
                            output_device_index=device_index,
                            format=AUDIO_FORMAT,
                            channels=AUDIO_CHANNELS,
                            rate=self.input_output_sample_rate,
                            input=False,
                            output=True,
                            frames_per_buffer=AUDIO_CHUNK_SIZE)
                        logging.info("Audio output opened: " + ("Yes" if self.output_stream.is_active() else "No"))
                        return self.output_stream.is_active()
                    else:
                        logging.error("No output device!")
                else:
                    logging.error("No output device!")
            except Exception as e:
                logging.exception(e)
                logging.error("Can't open output device")
        return False

    def close_output_device(self):
        """
        Closes output device
        :return:
        """
        if self.output_stream is not None:
            try:
                self.output_stream.stop_stream()
                self.output_stream.close()
                self.output_stream = None
            except Exception as e:
                logging.exception(e)
                logging.error("Can't close output device")

    def is_output_device_opened(self):
        """
        :return: true if output device is opened
        """
        if self.output_stream is not None:
            try:
                return self.output_stream.is_active()
            except:
                return False
        else:
            return False

    def start_main_thread(self):
        """
        Start main audio thread loop as background thread
        :return:
        """
        self.audio_thread_running = True
        thread = threading.Thread(target=self.audio_thread)
        thread.start()
        logging.info("Audio Thread: " + thread.getName())

    def audio_thread(self):
        """
        Main loop
        :return:
        """
        # Timer for updating volume
        update_audio_timer = time.time()

        while self.audio_thread_running:
            try:
                # Read input device chunk
                if self.is_input_device_opened() and self.input_output_sample_rate > 0:
                    # Retrieve data
                    input_data_raw = self.input_stream.read(AUDIO_CHUNK_SIZE)

                    # Convert to numpy array
                    input_data_np = np.fromstring(input_data_raw, dtype=AUDIO_NP_FORMAT)

                    # Add noise
                    noise_amount = self.settings_handler.settings["audio_noise_amount"]
                    if noise_amount > 0:
                        output_data_np = np.add(input_data_np,
                                                np.random.normal(0, noise_amount, AUDIO_CHUNK_SIZE)
                                                .astype(AUDIO_NP_FORMAT))
                    else:
                        output_data_np = input_data_np

                    # Convert back to bytes
                    output_data = output_data_np.tobytes()

                    # Send output buffer
                    if not self.controller.get_request_microphone_pause():
                        self.output_stream.write(output_data)
                        self.controller.update_state_microphone(Controller.MICROPHONE_STATE_ACTIVE)
                    else:
                        self.controller.update_state_microphone(Controller.MICROPHONE_STATE_PAUSED)

                    # Send volume at ~30FPS
                    try:
                        if time.time() - update_audio_timer >= 0.033:
                            if not self.controller.get_request_microphone_pause():
                                # Measure volume in dB
                                volume_rms = 20 * math.log10(audioop.rms(output_data, AUDIO_WIDTH))
                                if volume_rms > 100:
                                    volume_rms = 100

                                # Send volume
                                self.update_audio_rms.emit(int(volume_rms))
                            else:
                                # Send 0 volume
                                self.update_audio_rms.emit(0)
                    except:
                        pass
                else:
                    self.controller.update_state_microphone(Controller.MICROPHONE_STATE_ERROR)
                    time.sleep(0.1)

            except Exception as e:
                logging.exception(e)
                self.controller.update_state_microphone(Controller.MICROPHONE_STATE_ERROR)
                time.sleep(0.1)

        logging.warning("Audio loop exited")
