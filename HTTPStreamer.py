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
from threading import Thread

import cv2
import numpy
import requests
from flask import Flask, Response, request


class HTTPStreamer:
    app_ = Flask(__name__)

    def __init__(self, settings_handler):
        """
        Initializes HTTP Stream class
        :param settings_handler:
        """
        self.settings_handler = settings_handler

        self.frame = None
        # self.app = None
        self.server_process = None
        self.server_ip = ""
        self.server_port = 0
        self.stopping_flag = False

        @self.app_.route("/live")
        def video_feed():
            """
            Video from camera as JPEG image
            """

            if self.frame is not None:
                # Make response with encoded frame as JPEG image
                new_response = Response(self.gen(),
                                        mimetype="multipart/x-mixed-replace; boundary=frame")
                new_response.headers.add("Connection", "close")
                new_response.headers.add("Max-Age", "0")
                new_response.headers.add("Expires", "0")
                new_response.headers.add("Cache-Control",
                                         "no-store, no-cache, "
                                         "must-revalidate, pre-check=0, post-check=0, max-age=0")
                new_response.headers.add("Pragma", "no-cache")
                new_response.headers.add("Access-Control-Allow-Origin", "*")
                return new_response
            else:
                # Clear flag to reconnect to camera
                return '', 204

        @self.app_.route("/shutdown", methods=["GET"])
        def shutdown():
            shutdown_func = request.environ.get("werkzeug.server.shutdown")
            shutdown_func()
            return "Server shutting down..."

    def start_server(self):
        if self.server_process is None:
            try:
                self.frame = numpy.zeros((480, 640, 3))

                # Start the server
                self.stopping_flag = False
                self.server_ip = self.settings_handler.settings["http_server_ip"]
                self.server_port = int(self.settings_handler.settings["http_server_port"])
                self.server_process = Thread(target=self.app_.run,
                                             args=(self.server_ip, self.server_port, False,))
                self.server_process.start()
                logging.info("HTTP server process: " + self.server_process.name)

            # Error starting server
            except Exception as e:
                logging.exception(e)

    def stop_server(self):
        if self.server_process is not None:
            try:
                self.stopping_flag = True
                if "200" in str(requests.get("http://" + self.server_ip + ":" + str(self.server_port) + "/shutdown")):
                    self.server_process = None
                else:
                    logging.error("Error stopping server!")

            # Error stopping server
            except Exception as e:
                logging.exception(e)

    def set_frame(self, frame):
        self.frame = frame

    def gen(self):
        """
        Encodes camera image to JPEG
        :return:
        """
        while True:
            if self.frame is not None or self.stopping_flag:
                quality = self.settings_handler.settings["jpeg_quality"]
                (flag, encoded_image) = cv2.imencode(".jpg", self.frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
                if not flag or self.stopping_flag:
                    continue
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +
                       bytearray(encoded_image) + b'\r\n')
            else:
                break

            if self.stopping_flag and threading.Lock().locked():
                threading.Lock().release()
