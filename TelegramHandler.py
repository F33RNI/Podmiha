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
import time

import pyautogui
import telegram

import SettingsHandler
import Podmiha


class TelegramHandler:
    def __init__(self, settings_handler: SettingsHandler):
        self.settings_handler = settings_handler

        self.bot = None
        pass

    def start_bot(self):
        if self.bot is None:
            try:
                token = str(self.settings_handler.settings["telegram_bot_token"])
                self.bot = telegram.Bot(token=token)
                logging.info("Telegram bot token: " + token)

                # Send test message
                try:
                    chat_id = str(self.settings_handler.settings["telegram_chat_id"])
                    message = "Bot initialized. Podmiha version: " + Podmiha.APP_VERSION
                    if self.bot.send_message(chat_id=chat_id, text=message).text == message:
                        logging.info("Sent: " + message)
                    else:
                        logging.error("Error sending message")
                except Exception as e:
                    logging.exception(e)
                    logging.error("Error sending podmiha version with Telegram bot!")
            except Exception as e:
                logging.exception(e)
                logging.error("Error initializing Telegram bot!")

    def stop_bot(self):
        if self.bot is not None:
            try:
                self.bot.close()
            except Exception as e:
                logging.exception(e)
                logging.error("Error closing Telegram bot!")
            self.bot = None

    def send_plus(self):
        if self.bot is not None:
            try:
                chat_id = str(self.settings_handler.settings["telegram_chat_id"])
                message = str(self.settings_handler.settings["telegram_message_plus"])
                if self.bot.send_message(chat_id=chat_id, text=message).text == message:
                    logging.info("Sent: " + message)
                else:
                    logging.error("Error sending message")
            except Exception as e:
                logging.exception(e)
                logging.error("Error sending plus with Telegram bot!")

    def send_minus(self):
        if self.bot is not None:
            try:
                chat_id = str(self.settings_handler.settings["telegram_chat_id"])
                message = str(self.settings_handler.settings["telegram_message_minus"])
                if self.bot.send_message(chat_id=chat_id, text=message).text == message:
                    logging.info("Sent: " + message)
                else:
                    logging.error("Error sending message")
            except Exception as e:
                logging.exception(e)
                logging.error("Error sending minus with Telegram bot!")

    def send_screenshot(self):
        if self.bot is not None:
            try:
                chat_id = str(self.settings_handler.settings["telegram_chat_id"])
                pyautogui.screenshot().save(r"screenshot.png")
                time.sleep(0.5)
                self.bot.send_photo(chat_id=chat_id, photo=open("screenshot.png", "rb"))
                logging.info("Sending screenshot...")
            except Exception as e:
                logging.exception(e)
                logging.error("Error sending screenshot with Telegram bot!")
