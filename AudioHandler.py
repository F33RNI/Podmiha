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

import Controller
import SerialController
import SettingsHandler
from qt_thread_updater import get_updater

NOISE_FILE = "audio_noise.raw"
NOISE_DTYPE = np.float32

AUDIO_CHANNELS = 1
AUDIO_CHUNK_SIZE = 2048 * AUDIO_CHANNELS
AUDIO_FORMAT = pyaudio.paInt16
AUDIO_NP_FORMAT = np.int16
AUDIO_WIDTH = 2

DEVICE_TYPE_INPUT = 0
DEVICE_TYPE_OUTPUT = 1


class AudioHandler:
    def __init__(self, settings_handler: SettingsHandler, controller: Controller, serial_controller: SerialController,
                 audio_output_level_progress):
        """
        Initializes AudioHandler class
        :param settings_handler: SettingsHandler class
        :param controller: Controller class
        :param serial_controller: SerialController class
        :param audio_output_level_progress: progress bar audio level
        """
        self.settings_handler = settings_handler
        self.controller = controller
        self.serial_controller = serial_controller
        self.audio_output_level_progress = audio_output_level_progress

        self.py_audio = None
        self.input_stream = None
        self.output_stream = None
        self.input_output_sample_rate = 0
        self.audio_thread_running = False
        self.pause_output = True

    def get_device_list(self, device_type: int):
        """
        Gets list of device names
        :param device_type: DEVICE_TYPE_INPUT or DEVICE_TYPE_OUTPUT
        :return:
        """
        devices = []
        try:
            if self.py_audio is None:
                self.py_audio = pyaudio.PyAudio()
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
            if self.py_audio is None:
                self.py_audio = pyaudio.PyAudio()
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
                if self.py_audio is None:
                    self.py_audio = pyaudio.PyAudio()
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
                if self.py_audio is None:
                    self.py_audio = pyaudio.PyAudio()
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

        # Audio noise
        noise = None

        # Read noise from file
        try:
            logging.info("Reading noise from file...")
            noise_file = open(NOISE_FILE, "rb")
            noise_data_raw = noise_file.read()
            while noise_data_raw:
                noise_data_float = np.frombuffer(noise_data_raw, dtype=NOISE_DTYPE)
                if noise is None:
                    noise = noise_data_float
                else:
                    np.append(noise, noise_data_float)
                noise_data_raw = noise_file.read()
            noise_file.close()
            sample_rate = int(self.settings_handler.settings["audio_sample_rate"])
            logging.info(str(len(noise) // sample_rate) + " seconds of noise at " + str(sample_rate) + "s/s read")
        except Exception as e:
            noise = None
            logging.exception(e)
            logging.error("Error reading noise from file!")

        # Noise position counter
        noise_position_counter = 0

        while self.audio_thread_running:
            try:
                # Read input device chunk
                if self.is_input_device_opened() and self.input_output_sample_rate > 0:
                    # Retrieve microphone data
                    input_data_raw = self.input_stream.read(AUDIO_CHUNK_SIZE)

                    # Convert to numpy array
                    input_data_np = np.fromstring(input_data_raw, dtype=AUDIO_NP_FORMAT)

                    # Pause microphone
                    if self.controller.get_request_microphone_pause() \
                            or self.serial_controller.get_request_microphone_pause():
                        self.pause_output = True
                        self.controller.clear_request_microphone_pause()
                        self.serial_controller.clear_request_microphone_pause()
                        logging.info("Microphone paused")

                    # Resume microphone
                    if self.controller.get_request_microphone_resume() \
                            or self.serial_controller.get_request_microphone_resume():
                        self.pause_output = False
                        self.controller.clear_request_microphone_resume()
                        self.serial_controller.clear_request_microphone_resume()
                        logging.info("Microphone resumed")

                    # Initialize output
                    output_data = None

                    # Get amount of noise from settings
                    noise_amount = self.settings_handler.settings["audio_noise_amount"]

                    if noise_amount > 0 and noise is not None:
                        # Increment noise counter
                        noise_position_counter += AUDIO_CHUNK_SIZE

                        # Get chunk of noise
                        if noise_position_counter + AUDIO_CHUNK_SIZE < len(noise):
                            noise_chunk = noise[noise_position_counter: noise_position_counter + AUDIO_CHUNK_SIZE]
                        else:
                            noise_position_counter = 0
                            noise_chunk = noise[:AUDIO_CHUNK_SIZE]

                        # Multiply by noise level
                        noise_data_np = np.multiply(noise_chunk, noise_amount).astype(AUDIO_NP_FORMAT)

                        # Noise and paused
                        if self.pause_output:
                            # Send noise to output because input paused
                            if noise_data_np is not None:
                                output_data = noise_data_np.tobytes()

                        # Noise and not paused
                        else:
                            # Send combined data
                            if noise_data_np is not None and len(noise_data_np) == AUDIO_CHUNK_SIZE:
                                output_data_np = np.add(input_data_np, noise_data_np)

                            # Send only input data because noise is not available
                            else:
                                output_data_np = input_data_np
                            output_data = output_data_np.tobytes()

                    # No noise and not paused
                    elif not self.pause_output:
                        # Send input buffer directly to output
                        output_data = input_data_np.tobytes()

                    # Send output
                    if output_data is not None:
                        self.output_stream.write(output_data)

                    # Update microphone state
                    if not self.pause_output:
                        self.controller.update_state_microphone(Controller.MICROPHONE_STATE_ACTIVE)
                        self.serial_controller.update_state_microphone(Controller.MICROPHONE_STATE_ACTIVE)
                    else:
                        self.controller.update_state_microphone(Controller.MICROPHONE_STATE_PAUSED)
                        self.serial_controller.update_state_microphone(Controller.MICROPHONE_STATE_PAUSED)

                    # Send volume at ~30FPS
                    try:
                        if time.time() - update_audio_timer >= 0.033:
                            if output_data is not None:
                                # Measure volume in dB
                                volume_rms = 20 * math.log10(audioop.rms(output_data, AUDIO_WIDTH))
                                if volume_rms > 100:
                                    volume_rms = 100

                                # Send volume
                                get_updater().call_latest(self.audio_output_level_progress.setValue, int(volume_rms))
                            else:
                                # Send 0 volume
                                get_updater().call_latest(self.audio_output_level_progress.setValue, 0)
                    except:
                        pass
                else:
                    # Update microphone state
                    if not self.pause_output:
                        self.controller.update_state_microphone(Controller.MICROPHONE_STATE_ERROR_ACTIVE)
                        self.serial_controller.update_state_microphone(Controller.MICROPHONE_STATE_ERROR_ACTIVE)
                    else:
                        self.controller.update_state_microphone(Controller.MICROPHONE_STATE_ERROR_PAUSED)
                        self.serial_controller.update_state_microphone(Controller.MICROPHONE_STATE_ERROR_PAUSED)
                    time.sleep(0.1)

            except Exception as e:
                logging.exception(e)
                # Update microphone state
                if not self.pause_output:
                    self.controller.update_state_microphone(Controller.MICROPHONE_STATE_ERROR_ACTIVE)
                    self.serial_controller.update_state_microphone(Controller.MICROPHONE_STATE_ERROR_ACTIVE)
                else:
                    self.controller.update_state_microphone(Controller.MICROPHONE_STATE_ERROR_PAUSED)
                    self.serial_controller.update_state_microphone(Controller.MICROPHONE_STATE_ERROR_PAUSED)
                time.sleep(0.1)

        logging.warning("Audio loop exited")
