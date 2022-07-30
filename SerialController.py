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

import serial
import serial.tools.list_ports

import Controller
import SettingsHandler
import TelegramHandler

SERIAL_BAUDRATE = 9600
SERIAL_PARITY = serial.PARITY_NONE
SERIAL_STOPBITS = serial.STOPBITS_ONE
SERIAL_BYTESIZE = serial.EIGHTBITS
SERIAL_TIMEOUT = 2

PACKET_SUFFIX_1 = 0xFE
PACKET_SUFFIX_2 = 0xFF


def get_available_ports():
    serial_port_names = []
    try:
        ports = serial.tools.list_ports.comports(include_links=False)
        for port, desc, hwid in sorted(ports):
            serial_port_names.append(str(port))
    except Exception as e:
        logging.exception(e)
    return serial_port_names


class SerialController:
    def __init__(self, settings_handler: SettingsHandler, telegram_handler: TelegramHandler):
        self.settings_handler = settings_handler
        self.telegram_handler = telegram_handler

        self.serial_port = None
        self.port_name = ""
        self.serial_thread_running = False
        self.request_camera_pause = True
        self.request_microphone_pause = True
        self.request_camera_resume = False
        self.request_microphone_resume = False
        self.camera_current_state = Controller.CAMERA_STATE_ERROR
        self.microphone_current_state = Controller.MICROPHONE_STATE_ERROR

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

    def update_state_camera(self, new_state: int):
        """
        Updates camera state
        :param new_state:
        :return:
        """
        self.camera_current_state = new_state

    def update_state_microphone(self, new_state: int):
        """
        Updates microphone state
        :param new_state:
        :return:
        """
        self.microphone_current_state = new_state

    def open_port(self):
        """
        Opens serial port
        :return:
        """
        if self.serial_port is None:
            self.port_name = self.settings_handler.settings["serial_port_name"]
            if len(self.port_name) > 0:
                try:
                    # Open serial port
                    self.serial_port = serial.Serial(
                        port=self.port_name,
                        baudrate=SERIAL_BAUDRATE,
                        parity=SERIAL_PARITY,
                        stopbits=SERIAL_STOPBITS,
                        bytesize=SERIAL_BYTESIZE,
                        timeout=SERIAL_TIMEOUT
                    )

                    # Check port
                    if self.serial_port.isOpen():
                        logging.info("Serial port opened")

                        # Start main loop
                        self.serial_thread_running = True
                        thread = threading.Thread(target=self.serial_thread)
                        thread.start()
                        logging.info("Serial Thread: " + thread.getName())
                    else:
                        logging.error("Error opening serial port!")
                except Exception as e:
                    logging.exception(e)
                    logging.error("Error opening serial port!")
            else:
                logging.error("No serial port!")

    def close_port(self):
        """
        Closes serial port
        :return:
        """
        # Stop main loop
        self.serial_thread_running = False
        if self.serial_port is not None:
            try:
                # Close serial port
                self.serial_port.close()
            except Exception as e:
                logging.exception(e)
                logging.error("Error closing serial port!")
            self.serial_port = None

    def serial_thread(self):
        """
        Main serial loop
        :return:
        """
        # Serial buffers
        serial_tx_buffer = [0] * 5
        serial_rx_buffer = [0] * 8
        serial_rx_buffer_position = 0
        serial_rx_buffer_previous = 0

        # Storage variables
        camera_state_request_last = False
        microphone_state_request_last = False
        telegram_plus_request_last = 0
        telegram_minus_request_last = 0
        telegram_screenshot_request_last = 0
        while self.serial_thread_running:
            try:
                # No serial port
                if self.serial_port is None:
                    # Open serial port
                    self.serial_port = serial.Serial(
                        port=self.port_name,
                        baudrate=SERIAL_BAUDRATE,
                        parity=SERIAL_PARITY,
                        stopbits=SERIAL_STOPBITS,
                        bytesize=SERIAL_BYTESIZE,
                        timeout=SERIAL_TIMEOUT
                    )

                # Check serial port
                if self.serial_port is not None and self.serial_port.isOpen():
                    # Read current byte
                    serial_rx_buffer[serial_rx_buffer_position] = int.from_bytes(self.serial_port.read(1),
                                                                                 byteorder="big", signed=False) & 0xFF

                    # Found suffix
                    if serial_rx_buffer_previous == PACKET_SUFFIX_1 \
                            and serial_rx_buffer[serial_rx_buffer_position] == PACKET_SUFFIX_2:
                        # Reset buffer
                        serial_rx_buffer_position = 0

                        # Calculate checksum
                        check_byte = 0
                        for i in range(5):
                            check_byte ^= serial_rx_buffer[i] & 0xFF
                            check_byte &= 0xFF

                        # Checksum is correct
                        if check_byte == serial_rx_buffer[5]:
                            # Parse packet
                            camera_state_request = True if (serial_rx_buffer[0]) & 0xFF > 0 else False
                            microphone_state_request = True if int(serial_rx_buffer[1]) & 0xFF > 0 else False
                            telegram_plus_request = int(serial_rx_buffer[2]) & 0xFF
                            telegram_minus_request = int(serial_rx_buffer[3]) & 0xFF
                            telegram_screenshot_request = int(serial_rx_buffer[4]) & 0xFF

                            # Camera resume request changed
                            if camera_state_request is not camera_state_request_last:
                                camera_state_request_last = camera_state_request
                                # Paused -> Resume
                                if self.camera_current_state is Controller.CAMERA_STATE_PAUSED:
                                    self.request_camera_resume = True
                                # Not paused -> Pause
                                else:
                                    self.request_camera_pause = True

                            # Microphone resume request changed
                            if microphone_state_request is not microphone_state_request_last:
                                microphone_state_request_last = microphone_state_request
                                # Paused -> Resume
                                if self.microphone_current_state is Controller.MICROPHONE_STATE_PAUSED:
                                    self.request_microphone_resume = True
                                # Not paused -> Pause
                                else:
                                    self.request_microphone_pause = True

                            # Send plus
                            if telegram_plus_request != telegram_plus_request_last:
                                telegram_plus_request_last = telegram_plus_request
                                self.telegram_handler.send_plus()

                            # Send minus
                            if telegram_minus_request != telegram_minus_request_last:
                                telegram_minus_request_last = telegram_minus_request
                                self.telegram_handler.send_minus()

                            # Send screenshot
                            if telegram_screenshot_request != telegram_screenshot_request_last:
                                telegram_screenshot_request_last = telegram_screenshot_request
                                self.telegram_handler.send_screenshot()

                            # Form response packet
                            serial_tx_buffer[0] \
                                = 1 & 0xFF if self.camera_current_state is not Controller.CAMERA_STATE_PAUSED \
                                else 0 & 0xFF
                            serial_tx_buffer[1] \
                                = 1 & 0xFF if self.microphone_current_state is not Controller.MICROPHONE_STATE_PAUSED \
                                else 0 & 0xFF

                            serial_tx_buffer[2] = 0
                            for i in range(2):
                                serial_tx_buffer[2] ^= serial_tx_buffer[i] & 0xFF
                                serial_tx_buffer[2] &= 0xFF

                            serial_tx_buffer[3] = int(PACKET_SUFFIX_1) & 0xFF
                            serial_tx_buffer[4] = int(PACKET_SUFFIX_2) & 0xFF

                            # Send response
                            self.serial_port.write(serial_tx_buffer)

                            # print("RX:", serial_rx_buffer)
                            # print("TX:", serial_tx_buffer)

                        # Checksum isn't correct
                        else:
                            logging.error("Wrong serial checksum")

                    else:
                        # Store previous byte
                        serial_rx_buffer_previous = serial_rx_buffer[serial_rx_buffer_position]

                        # Increment buffer position
                        serial_rx_buffer_position += 1

                        # Reset buffer position
                        if serial_rx_buffer_position >= 8:
                            serial_rx_buffer_position = 0

                # Unable to open serial port
                else:
                    raise Exception("No serial port!")

            except Exception as e:
                logging.exception(e)
                logging.error("Serial exception. Disconnecting")
                try:
                    # Close serial port
                    self.serial_port.close()
                except:
                    pass
                self.serial_port = None
                time.sleep(1)

        logging.warning("Serial loop exited")
