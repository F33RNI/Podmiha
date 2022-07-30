/**
 * Copyright (C) 2022 Fern Lane, Podmiha serial controller
 *
 * Licensed under the GNU Affero General Public License, Version 3.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      https://www.gnu.org/licenses/agpl-3.0.en.html
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES OR
 * OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
 * ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
 * OTHER DEALINGS IN THE SOFTWARE.
 */

#include <Arduino.h>
#include <Adafruit_NeoPixel.h>


/***************************************/
/*            Hardware pins            */
/***************************************/
// WS2812 status led pin
const uint8_t PIN_WS2812 PROGMEM = 2;

// Camera toggle button
const uint8_t PIN_CAMERA_BTN PROGMEM = 3;

// Microphone toggle button
const uint8_t PIN_MICROPHONE_BTN PROGMEM = 4;

// Send plus button
const uint8_t PIN_SEND_PLUS_BTN PROGMEM = 5;

// Send minus button
const uint8_t PIN_SEND_MINUS_BTN PROGMEM = 6;

// Send screenshot button
const uint8_t PIN_SEND_SCREENSHOT_BTN PROGMEM = 7;

// Delay (in ms) for button debouncing
const uint16_t DEBOUNCE_DELAY_MS = 100;


/**********************************************/
/*            Serial communication            */
/**********************************************/
// Communication serial port
#define COMMUNICATION_SERIAL Serial

// Serial port speed
const uint32_t SERIAL_BAUD_RATE PROGMEM = 9600;

// Serial packet ending
const uint8_t SERIAL_SUFFIX_1 PROGMEM = 0xFE;
const uint8_t SERIAL_SUFFIX_2 PROGMEM = 0xFF;

// Packet sending period (ms)
const uint64_t SERIAL_SEND_PERIOD PROGMEM = 500;

// If there are no packets during this time (ms), the connection is considered lost
const uint64_t SERIAL_TIMEOUT_MS PROGMEM = 2000;


/***************************************/
/*            WS2812 colors            */
/***************************************/
// Color if camera and microphone are active (RGB)
#define COLOR_CAM_ON_MIC_ON 40, 20, 0

// Color if camera is active and microphone is paused (RGB)
#define COLOR_CAM_ON_MIC_OFF 40, 0, 0

// Color if camera is paused and microphone is active (RGB)
#define COLOR_CAM_OFF_MIC_ON 20, 40, 0

// Color if camera and microphone are paused (RGB)
#define COLOR_CAM_OFF_MIC_OFF 0, 40, 0


// System variables
// Button states
boolean state_btn_camera, state_btn_camera_last;
boolean state_btn_microphone, state_btn_microphone_last;
boolean state_btn_send_plus, state_btn_send_plus_last;
boolean state_btn_send_minus, state_btn_send_minus_last;
boolean state_btn_send_screenshot, state_btn_send_screenshot_last;

// Actual camera and microphone states
boolean current_state_camera, current_state_microphone;

// Requested camera and microphone states
boolean request_state_camera, request_state_microphone;

// Telegram send counters
uint8_t send_plus_counter, send_minus_counter, send_screenshot_counter;

// Serial communication
uint64_t serial_send_timer;
uint8_t serial_rx_buffer[5];
uint8_t serial_rx_buffer_position, serial_rx_byte_previous, serial_temp_byte, serial_check_byte;
uint8_t serial_tx_buffer[8];
uint64_t serial_watchdog_timer;
boolean serial_timeout_flag;

// WS2812 status led
Adafruit_NeoPixel status_led = Adafruit_NeoPixel(1, PIN_WS2812, NEO_GRB + NEO_KHZ800);

// Methods
void buttons_read(void);
void show_current_status(void);
void serial_read_data(void);
void serial_send_data(void);

void setup() {
  // Initialize WS2812 LED
  status_led.begin();
  status_led.show();

  // Initialize hardware pins
  pinMode(PIN_CAMERA_BTN, INPUT_PULLUP);
  pinMode(PIN_MICROPHONE_BTN, INPUT_PULLUP);
  pinMode(PIN_SEND_PLUS_BTN, INPUT_PULLUP);
  pinMode(PIN_SEND_MINUS_BTN, INPUT_PULLUP);
  pinMode(PIN_SEND_SCREENSHOT_BTN, INPUT_PULLUP);

  // Open serial port
  COMMUNICATION_SERIAL.begin(SERIAL_BAUD_RATE);
  delay(100);
}

void loop() {
  // Read data from serial port
  serial_read_data();

  // Update current state
  show_current_status();

  // Read button commands
  buttons_read();

  // Send data
  if (millis() - serial_send_timer >= SERIAL_SEND_PERIOD) {
    // Reset timer
    serial_send_timer = millis();

    // Send packet
    serial_send_data();
  }
}

/**
 * @brief Updates buttons
 * 
 */
void buttons_read(void) {
  // Read button states
  state_btn_camera = !digitalRead(PIN_CAMERA_BTN);
  state_btn_microphone = !digitalRead(PIN_MICROPHONE_BTN);
  state_btn_send_plus = !digitalRead(PIN_SEND_PLUS_BTN);
  state_btn_send_minus = !digitalRead(PIN_SEND_MINUS_BTN);
  state_btn_send_screenshot = !digitalRead(PIN_SEND_SCREENSHOT_BTN);

  // Camera button state changed
  if (state_btn_camera != state_btn_camera_last) {
    // Update state
    state_btn_camera_last = state_btn_camera;

    // Button pressed
    if (state_btn_camera)
      // Invert camera request
      request_state_camera = !request_state_camera;

    // Debouncing
    delay(DEBOUNCE_DELAY_MS);
  }

  // Microphone button state changed
  if (state_btn_microphone != state_btn_microphone_last) {
    // Update state
    state_btn_microphone_last = state_btn_microphone;

    // Button pressed
    if (state_btn_microphone)
      // Invert microphone request
      request_state_microphone = !request_state_microphone;

    // Debouncing
    delay(DEBOUNCE_DELAY_MS);
  }

  // Send plus button state changed
  if (state_btn_send_plus != state_btn_send_plus_last) {
    // Update state
    state_btn_send_plus_last = state_btn_send_plus;

    // Button pressed
    if (state_btn_send_plus) {
      // Increment counter
      send_plus_counter++;
      send_plus_counter %= 254;
    }

    // Debouncing
    delay(DEBOUNCE_DELAY_MS);
  }

  // Send minus button state changed
  if (state_btn_send_minus != state_btn_send_minus_last) {
    // Update state
    state_btn_send_minus_last = state_btn_send_minus;

    // Button pressed
    if (state_btn_send_minus) {
      // Increment counter
      send_minus_counter++;
      send_minus_counter %= 254;
    }
    
    // Debouncing
    delay(DEBOUNCE_DELAY_MS);
  }

  // Send screenshot button state changed
  if (state_btn_send_screenshot != state_btn_send_screenshot_last) {
    // Update state
    state_btn_send_screenshot_last = state_btn_send_screenshot;

    // Button pressed
    if (state_btn_send_screenshot) {
      // Increment counter
      send_screenshot_counter++;
      send_screenshot_counter %= 254;
    }

    // Debouncing
    delay(DEBOUNCE_DELAY_MS);
  }
}

/**
 * @brief Show camera and microphone state with led
 * 
 */
void show_current_status(void) {
  // Normal mode
  if (!serial_timeout_flag) {
    if (current_state_camera && current_state_microphone)
      status_led.setPixelColor(0, COLOR_CAM_ON_MIC_ON);
    else if (current_state_camera && !current_state_microphone)
      status_led.setPixelColor(0, COLOR_CAM_ON_MIC_OFF);
    else if (!current_state_camera && current_state_microphone)
      status_led.setPixelColor(0, COLOR_CAM_OFF_MIC_ON);
    else
      status_led.setPixelColor(0, COLOR_CAM_OFF_MIC_OFF);
  }

  // Connection lost
  else
    status_led.setPixelColor(0, 0);

  // Show current state
  status_led.show();
}

/**
 * @brief Receives data from serial port
 * 
 */
void serial_read_data(void) {
  // Check timeout
  if (millis() - serial_watchdog_timer >= SERIAL_TIMEOUT_MS)
    serial_timeout_flag = true;

  // Pause loop until all bytes are read
  while (COMMUNICATION_SERIAL.available()) {
    // Read current byte
    serial_rx_buffer[serial_rx_buffer_position] = COMMUNICATION_SERIAL.read();

    if (serial_rx_byte_previous == SERIAL_SUFFIX_1 && serial_rx_buffer[serial_rx_buffer_position] == SERIAL_SUFFIX_2) {
        // If data suffix appears
        // Reset buffer position
        serial_rx_buffer_position = 0;

        // Reset check sum
        serial_check_byte = 0;

        // Calculate check sum
        for (serial_temp_byte = 0; serial_temp_byte <= 1; serial_temp_byte++)
            serial_check_byte ^= serial_rx_buffer[serial_temp_byte];

        // Check if the check sums are equal
        if (serial_check_byte == serial_rx_buffer[2]) {
          // Reset watchdog timer
          serial_watchdog_timer = millis();

          // Retrieve data
          current_state_camera = serial_rx_buffer[0];
          current_state_microphone = serial_rx_buffer[1];
        }
    }
    else {
      // Store data bytes
      serial_rx_byte_previous = serial_rx_buffer[serial_rx_buffer_position];
      serial_rx_buffer_position++;

      // Reset buffer on overflow
      if (serial_rx_buffer_position >= 5)
          serial_rx_buffer_position = 0;
    }
  }
}


/**
 * @brief Sends data to serial port
 * 
 */
void serial_send_data(void) {
  // Fill payload bytes
  serial_tx_buffer[0] = request_state_camera;
  serial_tx_buffer[1] = request_state_microphone;
  serial_tx_buffer[2] = send_plus_counter;
  serial_tx_buffer[3] = send_minus_counter;
  serial_tx_buffer[4] = send_screenshot_counter;

  // Calculate checksum
  serial_tx_buffer[5] = 0;
  for (serial_temp_byte = 0; serial_temp_byte <= 4; serial_temp_byte++)
      serial_tx_buffer[5] ^= serial_tx_buffer[serial_temp_byte];

  // Fill suffix bytes
  serial_tx_buffer[6] = SERIAL_SUFFIX_1;
  serial_tx_buffer[7] = SERIAL_SUFFIX_2;

  // Send data
  COMMUNICATION_SERIAL.write(serial_tx_buffer, sizeof(serial_tx_buffer));
}
