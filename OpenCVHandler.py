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
import os
import threading
import time

import cv2
import numpy as np
import qimage2ndarray
import win32gui
from PIL import ImageGrab
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import QApplication
from imutils.video import FileVideoStream

import Controller
import winguiauto
from qt_thread_updater import get_updater

VIDEO_NOISE_FILE = "noise.avi"

DEFAULT_DETECTOR_PARAMETERS = "10, 30, 1, 0.05, 5, 0.1, 4, 0.35, 0.6, 10, 23"

PREVIEW_OUTPUT = 0
PREVIEW_WINDOW = 1
PREVIEW_SOURCE = 2
PREVIEW_ARUCO = 3

FAKE_MODE_ARUCO = 0
FAKE_MODE_FLICKER = 1

WINDOW_CAPTURE_QT = 0
WINDOW_CAPTURE_OLD = 1

TIME_DEBUG = False


def _map(x, in_min, in_max, out_min, out_max):
    """
    Aluino map function
    :param x:
    :param in_min:
    :param in_max:
    :param out_min:
    :param out_max:
    :return:
    """
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


def resize_keep_ratio(source_image, target_width, target_height, interpolation=cv2.INTER_AREA):
    """
    Resize image and keeps aspect ratio (background fills with black)
    """
    border_v = 0
    border_h = 0
    if (target_height / target_width) >= (source_image.shape[0] / source_image.shape[1]):
        border_v = int((((target_height / target_width) * source_image.shape[1]) - source_image.shape[0]) / 2)
    else:
        border_h = int((((target_width / target_height) * source_image.shape[0]) - source_image.shape[1]) / 2)
    output_image = cv2.copyMakeBorder(source_image, border_v, border_v, border_h, border_h, cv2.BORDER_CONSTANT, 0)
    return cv2.resize(output_image, (target_width, target_height), interpolation)


def change_window_state(window_name: str, state):
    """
    Changes state of window with name window_name to state
    :param window_name: window title
    :param state: new state win32con.SW_....
    :return:
    """

    def window_enum_handler(hwnd, top_windows_):
        top_windows_.append((hwnd, win32gui.GetWindowText(hwnd)))

    top_windows = []
    win32gui.EnumWindows(window_enum_handler, top_windows)
    for i in top_windows:
        if window_name.lower() in i[1].lower():
            win32gui.ShowWindow(i[0], state)
            win32gui.SetForegroundWindow(i[0])
            break


def get_center(points):
    """
    Calculates center of moments of contour
    :param points:
    :return:
    """
    moments = cv2.moments(points)
    center_x = int(moments["m10"] / moments["m00"])
    center_y = int(moments["m01"] / moments["m00"])
    return np.array([center_x, center_y])


def get_lines_intersection(line1, line2):
    """
    Calculates intersection between lines
    :param line1: [[x0, y0], [x1, y1]]
    :param line2: [[x2, y2], [x3, y3]]
    :return: x, y
    """
    x_diff = (line1[0][0] - line1[1][0], line2[0][0] - line2[1][0])
    y_diff = (line1[0][1] - line1[1][1], line2[0][1] - line2[1][1])

    def det(a, b):
        return a[0] * b[1] - a[1] * b[0]

    div = det(x_diff, y_diff)

    # Check if lines intersect
    if div == 0:
        # Return center of moments instead
        return get_center(np.array([line1[0], line1[1], line2[0], line2[1]]))

    d = (det(*line1), det(*line2))
    x = det(d, x_diff) / div
    y = det(d, y_diff) / div
    return x, y


def stretch_to(list_, target_length: int):
    """
    Stretches list to length
    :param list_: source list
    :param target_length: target length
    :return: stretched list
    """
    # Create new list with target length
    out = [None] * target_length

    # Measure source length
    input_length = len(list_)

    # Map target list
    if input_length > 1:
        for i, x in enumerate(list_):
            out[i * (target_length - 1) // (input_length - 1)] = x

    value = list_[0]

    # Fill Nones with prev. values
    for i in range(len(out)):
        if out[i] is None:
            out[i] = value
        else:
            value = out[i]

    return out


def get_marker_white_color(image, marker_corners):
    """
    Calculates average color of "white" pixels inside marker
    :param image: source image from which corners is found
    :param marker_corners: corners of the marker
    :return:
    """
    # Find marker bounding rectangle
    rect = cv2.boundingRect(marker_corners)
    x, y, w, h = rect

    # Create marker mask
    mask = np.zeros((h, w), dtype=image.dtype)
    cv2.drawContours(mask, [np.array([marker_corners], dtype=int)], -1, 255, -1, offset=(-x, -y))

    # Create masked marker image
    marker_masked = image[y: y + h, x: x + w]
    marker_masked = cv2.bitwise_or(marker_masked, marker_masked, mask=mask)
    marker_masked_gray = cv2.cvtColor(marker_masked, cv2.COLOR_BGR2GRAY)

    # Create mask of white pixels inside marker
    mask_threshold = cv2.threshold(marker_masked_gray,
                                   int(cv2.mean(marker_masked_gray, mask)[0]), 255, cv2.THRESH_BINARY)[1]

    # Find mean white color
    mean_color = cv2.mean(marker_masked, mask_threshold)

    # Return BGR color as integer
    return int(mean_color[0]), int(mean_color[1]), int(mean_color[2])


class OpenCVHandler:
    def __init__(self, settings_handler, http_stream, virtual_camera, flicker, controller, serial_controller,
                 preview_label, label_fps):
        """
        Initializes OpenCVHandler class
        :param settings_handler: SettingsHandler class
        :param http_stream: HTTPStream class with set_frame function
        :param preview_label: preview label element
        :param label_fps: fps label
        """
        self.settings_handler = settings_handler
        self.http_stream = http_stream
        self.virtual_camera = virtual_camera
        self.flicker = flicker
        self.controller = controller
        self.serial_controller = serial_controller
        self.preview_label = preview_label
        self.label_fps = label_fps

        # Internal variables
        self.opencv_thread_running = False
        self.camera_capture_allowed = False
        self.window_capture_allowed = False
        self.output_allowed = False
        self.video_capture = None
        self.input_camera_exposure = 0
        self.input_camera_exposure_auto = False
        self.input_camera_focus = 0
        self.input_camera_focus_auto = False
        self.window_title = ""
        self.crop_top = 0
        self.crop_left = 0
        self.crop_right = 0
        self.crop_bottom = 0
        self.fake_screen = False
        self.stretch_scale_x = 0.
        self.stretch_scale_y = 0.
        self.aruco_size = 0
        self.aruco_invert = False
        self.marker_ids = [0, 0, 0, 0]
        self.blur_radius = 0
        self.hwnd = None
        self.input_frame = None
        self.final_output_frame = None
        self.preview_mode = 0
        self.output_width = 0
        self.output_height = 0
        self.output_noise_amount = 0.
        self.flick_counter = 0
        self.fake_mode = 0
        self.flicker_duration = 0
        self.flicker_interval = 0
        self.window_dc = None
        self.c_dc = None
        self.dc_object = None
        self.data_bitmap = None
        self.window_capture_method = 0
        self.window_image = None
        self.frame_blending = False
        self.brightness_gradient_enabled = False
        self.pause_output = False
        self.tl_filtered = [0., 0.]
        self.tr_filtered = [0., 0.]
        self.br_filtered = [0., 0.]
        self.bl_filtered = [0., 0.]
        self.camera_matrix = None
        self.camera_distortions = None
        self.aruco_filter_scale = 0
        self.aruco_filter_enabled = False
        self.aruco_image = None
        self.window_contrast = 0.
        self.window_brightness = 0
        self.output_contrast = 0.
        self.output_brightness = 0
        self.maximum_fps = 0
        self.real_fps = 0
        self.cuda_enabled = False

        self.new_time = 0

        # Use 4x4 50 ARUco dictionary
        self.aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)

        # ARUco detection parameters
        self.parameters = cv2.aruco.DetectorParameters_create()

    def time_debug(self, tag: str, time_started):
        """
        Prints debug messages with time for performance debugging
        :param tag: text of message
        :param time_started: started time of OpenCV loop
        :return:
        """
        if TIME_DEBUG:
            tag = tag.ljust(20)[:20]
            time_now = time.time()
            print(tag + "\t" + "{:<4}".format(str(round(((time_now - self.new_time) * 1000), 2)))
                  + "\t" + "{:<4}".format(str(round(((time_now - time_started) * 1000), 2))))
            self.new_time = time_now

    def get_final_output_frame(self):
        return self.final_output_frame

    def get_window_image(self):
        return self.window_image

    def start_opencv_thread(self):
        """
        Starts OpenCV loop as background thread
        :return:
        """
        # Read camera calibration
        if os.path.exists("camera_calibration.yaml"):
            cv_file = cv2.FileStorage("camera_calibration.yaml", cv2.FILE_STORAGE_READ)
            self.camera_matrix = cv_file.getNode("camera_matrix").mat()
            self.camera_distortions = cv_file.getNode("dist_coeff").mat()
            cv_file.release()
        else:
            self.camera_matrix = None
            self.camera_distortions = None

        # Set flags
        self.opencv_thread_running = True
        self.pause_output = True

        # Start new thread
        thread = threading.Thread(target=self.opencv_thread)
        thread.start()
        logging.info("OpenCV Thread: " + thread.getName())

    def update_from_settings(self):
        # Retrieve settings
        self.input_camera_exposure = int(self.settings_handler.settings["input_camera_exposure"])
        self.input_camera_exposure_auto = self.settings_handler.settings["input_camera_exposure_auto"]
        self.input_camera_focus = int(self.settings_handler.settings["input_camera_focus"])
        self.input_camera_focus_auto = self.settings_handler.settings["input_camera_focus_auto"]
        self.aruco_size = int(self.settings_handler.settings["aruco_size"])
        self.aruco_invert = self.settings_handler.settings["aruco_invert"]
        self.marker_ids = self.settings_handler.settings["aruco_ids"]
        self.window_title = str(self.settings_handler.settings["window_title"])
        self.window_capture_method = int(self.settings_handler.settings["window_capture_method"])
        self.window_capture_allowed = self.settings_handler.settings["fake_screen"]
        self.crop_left = int(self.settings_handler.settings["window_crop"][0])
        self.crop_top = int(self.settings_handler.settings["window_crop"][1])
        self.crop_right = int(self.settings_handler.settings["window_crop"][2])
        self.crop_bottom = int(self.settings_handler.settings["window_crop"][3])
        self.fake_screen = self.settings_handler.settings["fake_screen"]
        self.stretch_scale_x = float(self.settings_handler.settings["stretch_scale"][0])
        self.stretch_scale_y = float(self.settings_handler.settings["stretch_scale"][1])
        self.blur_radius = int(self.settings_handler.settings["output_blur_radius"])
        self.output_width = int(self.settings_handler.settings["output_size"][0])
        self.output_height = int(self.settings_handler.settings["output_size"][1])
        self.output_noise_amount = float(self.settings_handler.settings["output_noise_amount"])
        self.fake_mode = int(self.settings_handler.settings["fake_mode"])
        self.flicker_duration = int(self.settings_handler.settings["flicker_duration"])
        self.flicker_interval = int(self.settings_handler.settings["flicker_interval"])
        self.frame_blending = self.settings_handler.settings["frame_blending"]
        self.brightness_gradient_enabled = self.settings_handler.settings["brightness_gradient"]
        self.aruco_filter_scale = float(self.settings_handler.settings["aruco_filter_scale"])
        self.aruco_filter_enabled = self.settings_handler.settings["aruco_filter_enabled"]
        self.window_contrast = float(self.settings_handler.settings["window_contrast"])
        self.window_brightness = int(self.settings_handler.settings["window_brightness"])
        self.output_brightness = int(self.settings_handler.settings["output_brightness"])
        self.output_contrast = float(self.settings_handler.settings["output_contrast"])
        self.maximum_fps = int(self.settings_handler.settings["max_fps"])
        self.cuda_enabled = self.settings_handler.settings["cuda_enabled"]

        parameters = str(self.settings_handler.settings["aruco_detector_parameters"]).replace(" ", "").split(",")
        if len(parameters) is not 11:
            logging.error("Wrong detector parameters! Using default...")
            parameters = DEFAULT_DETECTOR_PARAMETERS
        try:
            self.update_detector_parameters(parameters)
        except Exception as e:
            logging.exception(e)
            logging.error("Wrong detector parameters! Using default...")
            self.update_detector_parameters(DEFAULT_DETECTOR_PARAMETERS)

        if self.video_capture is not None:
            # Focus
            self.video_capture.set(cv2.CAP_PROP_AUTOFOCUS, 1 if self.input_camera_focus_auto else 0)
            self.video_capture.set(cv2.CAP_PROP_FOCUS, self.input_camera_focus)

            # Exposure
            self.video_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1 if self.input_camera_exposure_auto else 0)
            self.video_capture.set(cv2.CAP_PROP_EXPOSURE, self.input_camera_exposure)

        # Release old window handlers and update hwnd
        self.hwnd = winguiauto.findTopWindow(self.window_title)
        # noinspection PyBroadException
        try:
            self.dc_object.DeleteDC()
            self.c_dc.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, self.window_dc)
            win32gui.DeleteObject(self.data_bitmap.GetHandle())
        except:
            pass
        # change_window_state(self.window_title, win32con.SW_SHOWMAXIMIZED)

    def update_detector_parameters(self, parameters: str):
        """
        Updates detector parameters
        :param parameters:
        :return:
        """
        self.parameters.adaptiveThreshConstant = int(parameters[0])
        self.parameters.cornerRefinementMaxIterations = int(parameters[1])
        self.parameters.cornerRefinementMethod = int(parameters[2])
        self.parameters.polygonalApproxAccuracyRate = float(parameters[3])
        self.parameters.cornerRefinementWinSize = int(parameters[4])
        self.parameters.cornerRefinementMinAccuracy = float(parameters[5])
        self.parameters.perspectiveRemovePixelPerCell = int(parameters[6])
        self.parameters.maxErroneousBitsInBorderRate = float(parameters[7])
        self.parameters.errorCorrectionRate = float(parameters[8])
        self.parameters.adaptiveThreshWinSizeStep = int(parameters[9])
        self.parameters.adaptiveThreshWinSizeMax = int(parameters[10])

    def open_camera(self):
        # Pause camera
        self.pause_output = True

        try:
            # Update variables from settings
            self.update_from_settings()

            camera_id = int(self.settings_handler.settings["input_camera"])

            # Start camera
            if self.settings_handler.settings["use_dshow"]:
                self.video_capture = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            else:
                self.video_capture = cv2.VideoCapture(camera_id)

            # Open camera settings menu
            # self.video_capture.set(cv2.CAP_PROP_SETTINGS, 1)

            # Select maximum resolution
            self.video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.settings_handler.settings["input_size"][0]))
            self.video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.settings_handler.settings["input_size"][1]))

            # Focus
            self.video_capture.set(cv2.CAP_PROP_AUTOFOCUS, 1 if self.input_camera_focus_auto else 0)
            self.video_capture.set(cv2.CAP_PROP_FOCUS, self.input_camera_focus)

            # Exposure
            self.video_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1 if self.input_camera_exposure_auto else 0)
            self.video_capture.set(cv2.CAP_PROP_EXPOSURE, self.input_camera_exposure)

            # Disable auto white balance
            self.video_capture.set(cv2.CAP_PROP_AUTO_WB, 0)

            # Read first frame
            ret, _ = self.video_capture.read()
            if ret:
                self.camera_capture_allowed = True
            else:
                logging.error("Can't read camera frame!")

        except Exception as e:
            logging.exception(e)

    def close_camera(self):
        """
        Stops source camera
        :return:
        """
        # Pause camera
        self.pause_output = True

        # Stop capturing frames
        self.camera_capture_allowed = False
        try:
            self.video_capture.release()
        except Exception as e:
            logging.exception(e)
        self.video_capture = None

    def opencv_thread(self):
        """
        Main OpenCV thread
        :return:
        """

        self.flick_counter = 0
        input_ret = False
        self.window_image = None
        black_frame = np.zeros((1280, 720, 3), dtype=np.uint8)
        flicker_key_frame_1 = None
        flicker_key_frame_2 = None
        self.aruco_image = black_frame.copy()
        noise_frame = np.zeros((1280, 720), dtype=np.uint8)
        cuda_enabled = False
        noise_stream = FileVideoStream(VIDEO_NOISE_FILE).start()

        while self.opencv_thread_running:
            try:
                # Start without error
                error = False

                # Allow aruco detection and screen faking
                allow_fake_screen = True

                # Record time
                time_started = time.time()

                # Initialize CUDA
                cuda_enabled_new = self.cuda_enabled
                if cuda_enabled_new and not cuda_enabled:
                    logging.info("Initializing CUDA...")
                    cv2.cuda.setDevice(0)
                    gpu_output_frame = cv2.cuda_GpuMat()
                    gpu_noise_frame = cv2.cuda_GpuMat()
                    gpu_h = cv2.cuda_GpuMat(gpu_output_frame.size(), cv2.CV_8UC1)
                    gpu_s = cv2.cuda_GpuMat(gpu_output_frame.size(), cv2.CV_8UC1)
                    gpu_v = cv2.cuda_GpuMat(gpu_output_frame.size(), cv2.CV_8UC1)
                cuda_enabled = cuda_enabled_new

                self.time_debug("Initializing", time_started)

                # Pause camera
                if self.controller.get_request_camera_pause() or self.serial_controller.get_request_camera_pause():
                    self.pause_output = True
                    self.controller.clear_request_camera_pause()
                    self.serial_controller.clear_request_camera_pause()
                    logging.info("Camera paused")

                # Resume camera
                if self.controller.get_request_camera_resume() or self.serial_controller.get_request_camera_resume():
                    self.pause_output = False
                    self.controller.clear_request_camera_resume()
                    self.serial_controller.clear_request_camera_resume()
                    logging.info("Camera resumed")

                # Grab window image
                window_image = None
                # noinspection PyBroadException
                try:
                    if self.window_capture_allowed and self.hwnd is not None:
                        if self.window_capture_method == WINDOW_CAPTURE_OLD:
                            rect = win32gui.GetWindowPlacement(self.hwnd)[-1]
                            window_image = cv2.cvtColor(np.array(ImageGrab.grab(rect)), cv2.COLOR_RGB2BGR)
                        elif self.window_capture_method == WINDOW_CAPTURE_QT:
                            # Get window image using PyQt5 grabWindow() function
                            window_image = qimage2ndarray. \
                                rgb_view(QPixmap(QApplication.primaryScreen().grabWindow(self.hwnd)).toImage())

                            # Check image
                            if window_image is not None \
                                    and window_image.shape[0] > 10 and window_image.shape[1] > 10 \
                                    and window_image.shape[2] == 3 \
                                    and (cv2.countNonZero(window_image[:, :, 0]) > 0
                                         or cv2.countNonZero(window_image[:, :, 1]) > 0
                                         or cv2.countNonZero(window_image[:, :, 2]) > 0):

                                # Convert to BGR
                                window_image = cv2.cvtColor(window_image, cv2.COLOR_RGB2BGR)

                            # No window image -> error
                            else:
                                window_image = black_frame.copy()
                                error = True
                    else:
                        allow_fake_screen = False
                except Exception as e:
                    logging.exception(e)
                    logging.error("Can't get window image!")
                    window_image = black_frame.copy()
                    error = True

                # Replace window image with black if error occurs
                if window_image is None:
                    window_image = black_frame.copy()

                # Crop window image
                window_image = window_image[
                                    self.crop_top:window_image.shape[0] - self.crop_bottom,
                                    self.crop_left:window_image.shape[1] - self.crop_right]
                self.window_image = window_image

                self.time_debug("Screen captured", time_started)

                # Grab the current camera frame
                # noinspection PyBroadException
                try:
                    if self.camera_capture_allowed \
                            and self.video_capture is not None and self.video_capture.isOpened() and not error:
                        if self.fake_mode == FAKE_MODE_FLICKER and self.fake_screen:
                            # Count flicker frames
                            self.flick_counter += 1

                            # Flick!
                            if self.flick_counter == self.flicker_interval:
                                self.flicker.open_()

                            # Counter ended
                            elif self.flick_counter >= self.flicker_interval + self.flicker_duration:
                                # Update frame blending
                                if flicker_key_frame_2 is not None:
                                    flicker_key_frame_1 = flicker_key_frame_2.copy()
                                flicker_key_frame_2 = None

                                # Retrieve frame
                                input_ret, flicker_key_frame_2 = self.video_capture.read()

                                # Stop flicking
                                self.flicker.close_()

                                # Reset counter
                                self.flick_counter = 0

                            # Frame blending
                            if flicker_key_frame_1 is not None and flicker_key_frame_2 is not None \
                                    and self.frame_blending:
                                # Calculate input_frame_counter for frame blending
                                input_frame_factor = _map(self.flick_counter,
                                                          0., self.flicker_interval + self.flicker_duration, 0., 1.)
                                self.input_frame = cv2.addWeighted(flicker_key_frame_1,
                                                                   1. - input_frame_factor,
                                                                   flicker_key_frame_2, input_frame_factor, 0.)
                            else:
                                self.input_frame = flicker_key_frame_2

                        # No flicker fake
                        else:
                            # Stop flicking
                            self.flicker.close_()

                            # Reset flick variables
                            self.flick_counter = 0
                            flicker_key_frame_1 = None
                            flicker_key_frame_2 = None

                            # Retrieve frame
                            input_ret, self.input_frame = self.video_capture.read()

                    # No camera image
                    else:
                        # Set error flag
                        error = True

                        # Stop flicking
                        if self.fake_mode == FAKE_MODE_FLICKER:
                            self.flicker.close_()

                        # Reset flicker variables
                        flicker_key_frame_1 = None
                        flicker_key_frame_2 = None

                        # Disable fake screen
                        allow_fake_screen = False
                except:
                    input_ret = False
                    error = True

                # Replace frame with black if error occurs
                if self.input_frame is None or not input_ret:
                    self.input_frame = black_frame.copy()

                self.time_debug("Camera captured", time_started)

                # Create copy of input frame
                output_frame = self.input_frame.copy()

                self.time_debug("Frame copied", time_started)

                # Disallow faking screen
                if not self.fake_screen or error:
                    allow_fake_screen = False

                # Convert input camera image to gray
                input_gray = cv2.cvtColor(self.input_frame, cv2.COLOR_BGR2GRAY)

                self.time_debug("Converted to gray", time_started)

                # Invert frame if needed
                if self.aruco_invert:
                    gray_for_aruco = cv2.bitwise_not(input_gray)
                else:
                    gray_for_aruco = input_gray

                # Find aruco markers
                if self.fake_screen and self.fake_mode == FAKE_MODE_ARUCO:
                    if self.camera_matrix is not None and self.camera_distortions is not None:
                        corners, ids, _ = cv2.aruco.detectMarkers(image=gray_for_aruco, dictionary=self.aruco_dict,
                                                              parameters=self.parameters,
                                                              cameraMatrix=self.camera_matrix,
                                                              distCoeff=self.camera_distortions)
                    else:
                        corners, ids, _ = cv2.aruco.detectMarkers(gray_for_aruco, self.aruco_dict,
                                                              parameters=self.parameters)

                    # Get preview of first marker
                    if np.all(ids is not None):
                        rect = cv2.boundingRect(corners[0][0])
                        self.aruco_image = cv2.resize(self.input_frame[rect[1]: rect[1] + rect[3],
                                                      rect[0]: rect[0] + rect[2]],
                                                      (self.aruco_size, self.aruco_size))

                    self.time_debug("Markers detected", time_started)
                else:
                    corners = None
                    ids = None

                if self.fake_screen \
                        and self.fake_mode == FAKE_MODE_ARUCO \
                        and allow_fake_screen \
                        and not self.flicker.is_force_fullscreen_enabled():
                    if np.all(ids is not None):
                        # Check number of markers
                        if ids.size == 4:
                            # Convert ids to list
                            ids_list = ids.reshape((len(ids))).tolist()

                            # Check all IDs
                            markers_in_list = True
                            for marker_id in self.marker_ids:
                                if marker_id not in ids_list:
                                    markers_in_list = False
                                    break

                            if markers_in_list:

                                # Get markers corners
                                marker_tl = corners[ids_list.index(0)][0]
                                marker_tr = corners[ids_list.index(1)][0]
                                marker_br = corners[ids_list.index(2)][0]
                                marker_bl = corners[ids_list.index(3)][0]

                                tl = marker_tl[0]
                                tr = marker_tr[1]
                                br = marker_br[2]
                                bl = marker_bl[3]

                                # Filter coordinates
                                if self.aruco_filter_enabled:
                                    tl, tr, br, bl = self.filter_corners(tl, tr, br, bl)

                                # Dimensions of the frames
                                overlay_height = self.window_image.shape[0]
                                overlay_width = self.window_image.shape[1]
                                source_height = self.input_frame.shape[0]
                                source_width = self.input_frame.shape[1]

                                # Color gradient
                                if self.brightness_gradient_enabled:
                                    # Create 2x2 color gradient
                                    color_gradient = np.zeros((2, 2, 3), dtype=self.input_frame.dtype)
                                    color_gradient[0, 0, :] = get_marker_white_color(self.input_frame, marker_tl)
                                    color_gradient[0, 1, :] = get_marker_white_color(self.input_frame, marker_tr)
                                    color_gradient[1, 1, :] = get_marker_white_color(self.input_frame, marker_br)
                                    color_gradient[1, 0, :] = get_marker_white_color(self.input_frame, marker_bl)

                                    # Stretch to window size
                                    color_gradient = cv2.resize(color_gradient,
                                                                (window_image.shape[1], window_image.shape[0]),
                                                                cv2.INTER_LINEAR)

                                    # Apply brightness gradient
                                    color_gradient = cv2.bitwise_not(color_gradient)
                                    window_image = cv2.subtract(window_image, color_gradient)

                                # Apply contrast and brightness
                                window_image = cv2.addWeighted(window_image, self.window_contrast, window_image, 0.,
                                                               self.window_brightness)

                                # Source points (full size of overlay image)
                                points_src = np.array([
                                    [0, 0],
                                    [overlay_width - 1, 0],
                                    [overlay_width - 1, overlay_height - 1],
                                    [0, overlay_height - 1]], dtype='float32')

                                # Destination points (projection)
                                points_dst = np.array([tl, tr, br, bl], dtype='float32')

                                # Stretch window
                                center_x, center_y = get_lines_intersection([tl, br], [tr, bl])
                                # center_x, center_y = get_center(points_dst)
                                for i in range(len(points_dst)):
                                    points_dst[i][0] = self.stretch_scale_x * (points_dst[i][0] - center_x) + center_x
                                    points_dst[i][1] = self.stretch_scale_y * (points_dst[i][1] - center_y) + center_y

                                # Warp and transform window image
                                window_matrix = cv2.getPerspectiveTransform(points_src, points_dst)
                                window_warp = cv2.warpPerspective(window_image, window_matrix,
                                                                  (source_width, source_height))

                                # Cut black region from destination_frame
                                contours = np.array([points_dst], dtype=int)
                                cv2.drawContours(output_frame, [contours], -1, 0, -1)

                                # Combine images
                                output_frame = cv2.bitwise_or(output_frame, window_warp)

                                # Blur contour of screen
                                # TODO: Make faster
                                """
                                output_blurred = cv2.GaussianBlur(output_frame, (5, 5), 0)
                                mask = np.zeros(output_frame.shape, np.uint8)

                                center_x, center_y = get_center(points_dst)
                                for i in range(len(points_dst)):
                                    contours[0][i][0] = 0.992 * (contours[0][i][0] - center_x) + center_x
                                    contours[0][i][1] = 0.992 * (contours[0][i][1] - center_y) + center_y

                                cv2.drawContours(mask, [contours], -1, (255, 255, 255), 4)

                                output_frame = np.where(mask == np.array([255, 255, 255]),
                                                        output_blurred, output_frame)
                                """

                            # Not all IDs detected
                            else:
                                error = True
                                logging.error("Not all markers detected!")

                        # Detected != 4 markers
                        else:
                            error = True
                            if ids.size > 4:
                                logging.error("Detected more than 4 markers!")
                            else:
                                logging.error("Detected less than 4 markers!")

                    # No markers detected
                    else:
                        error = True
                        logging.error("No ARUco detected!")

                # Fake aruco disabled
                else:
                    # Just copy input frame
                    output_frame = self.input_frame.copy()

                    # Detected at least 1 marker
                    if np.all(ids is not None):
                        error = True
                        logging.error("ARUco was found but should not have been!")

                self.time_debug("Markers processed", time_started)

                # Is frame totally black?
                is_output_frame_black = cv2.countNonZero(cv2.cvtColor(output_frame, cv2.COLOR_BGR2GRAY)) == 0

                # Resize output
                output_frame = cv2.resize(output_frame, (self.output_width, self.output_height))
                self.time_debug("Output resized", time_started)

                # Add effects only on non-black output frame
                if not is_output_frame_black:
                    # Add blur
                    # noinspection PyBroadException
                    try:
                        # Check blur radius
                        if self.blur_radius % 2 == 0 or self.blur_radius <= 0:
                            self.blur_radius += 1
                        output_frame = cv2.GaussianBlur(output_frame, (self.blur_radius, self.blur_radius), 0)
                    except:
                        pass

                    self.time_debug("Blur added", time_started)

                    # Upload to gpu
                    if cuda_enabled:
                        gpu_output_frame.upload(output_frame)

                    # Apply contrast and brightness
                    if cuda_enabled:
                        gpu_output_frame = cv2.cuda.addWeighted(gpu_output_frame, self.output_contrast,
                                                                gpu_output_frame, 0., self.output_brightness)
                    else:
                        output_frame = cv2.addWeighted(output_frame, self.output_contrast, output_frame, 0.,
                                                       self.output_brightness)

                    self.time_debug("Br. / Cont. added", time_started)

                    # Add noise
                    # noinspection PyBroadException
                    try:
                        # Read noise from file
                        test_noise_frame = None
                        try:
                            if noise_stream.more():
                                test_noise_frame = noise_stream.read()
                            else:
                                noise_stream.stop()
                                noise_stream = FileVideoStream(VIDEO_NOISE_FILE).start()
                                test_noise_frame = noise_stream.read()
                        except Exception as e:
                            logging.exception(e)

                        # Check noise
                        if test_noise_frame is not None and test_noise_frame.shape[0] > 1 \
                                and test_noise_frame.shape[1] > 1 and test_noise_frame.shape[2] == 3:
                            noise_frame = test_noise_frame[:, :, 0]

                        # Upload to GPU
                        if cuda_enabled:
                            gpu_noise_frame.upload(noise_frame)

                        # Crop or resize
                        if self.output_width <= noise_frame.shape[1] and self.output_height <= noise_frame.shape[0]:
                            if cuda_enabled:
                                gpu_noise_frame = cv2.cuda_GpuMat(gpu_noise_frame,
                                                                  (0, self.output_height), (0, self.output_width))
                            else:
                                noise_frame = noise_frame[0:self.output_height, 0:self.output_width]
                        else:
                            if cuda_enabled:
                                gpu_noise_frame = cv2.cuda.resize(gpu_noise_frame,
                                                                  (self.output_width, self.output_height),
                                                                  interpolation=cv2.INTER_AREA)
                            else:
                                noise_frame = cv2.resize(noise_frame,
                                                         (self.output_width, self.output_height),
                                                         interpolation=cv2.INTER_AREA)

                        # Add noise using GPU
                        if cuda_enabled:
                            # Convert output frame to HSV
                            gpu_output_frame_hsv = cv2.cuda.cvtColor(gpu_output_frame, cv2.COLOR_BGR2HSV)

                            # Split HSV
                            cv2.cuda.split(gpu_output_frame_hsv, [gpu_h, gpu_s, gpu_v])

                            # Add noise to darken areas
                            gpu_v_noisy = cv2.cuda.bitwise_not(cv2.cuda.bitwise_and(
                                cv2.cuda.bitwise_not(gpu_v), gpu_noise_frame))

                            # Combine with clear output
                            gpu_v_noisy = cv2.cuda.addWeighted(gpu_v, 1. - self.output_noise_amount,
                                                               gpu_v_noisy, self.output_noise_amount, 0.)

                            # Merge HSV
                            cv2.cuda.merge([gpu_h, gpu_s, gpu_v_noisy], gpu_output_frame_hsv)

                            # Convert back to BGR
                            gpu_output_frame = cv2.cuda.cvtColor(gpu_output_frame_hsv, cv2.COLOR_HSV2BGR)

                            # Download from GPU
                            output_frame = gpu_output_frame.download()

                        # Add noise using CPU
                        else:
                            # Convert output frame to HSV
                            output_frame_hsv = cv2.cvtColor(output_frame, cv2.COLOR_BGR2HSV)

                            # Add noise to darken areas
                            output_frame_v_noisy = cv2.bitwise_not(
                                cv2.bitwise_and(cv2.bitwise_not(output_frame_hsv[:, :, 2]), noise_frame))

                            # Combine with clear output
                            output_frame_v_noisy = cv2.addWeighted(output_frame_hsv[:, :, 2],
                                                                   1. - self.output_noise_amount,
                                                                   output_frame_v_noisy, self.output_noise_amount, 0.)
                            output_frame_hsv[:, :, 2] = output_frame_v_noisy

                            # Convert back to BGR
                            output_frame = cv2.cvtColor(output_frame_hsv, cv2.COLOR_HSV2BGR)
                    except:
                        pass

                    self.time_debug("Noise added", time_started)

                # Output enabled
                if not error and not self.pause_output:
                    # Make final image
                    self.final_output_frame = output_frame.copy()
                    # Set active state
                    self.controller.update_state_camera(Controller.CAMERA_STATE_ACTIVE)
                    self.serial_controller.update_state_camera(Controller.CAMERA_STATE_ACTIVE)

                # Set current camera state
                if error:
                    if self.pause_output:
                        self.controller.update_state_camera(Controller.CAMERA_STATE_ERROR_PAUSED)
                        self.serial_controller.update_state_camera(Controller.CAMERA_STATE_ERROR_PAUSED)
                    else:
                        self.controller.update_state_camera(Controller.CAMERA_STATE_ERROR_ACTIVE)
                        self.serial_controller.update_state_camera(Controller.CAMERA_STATE_ERROR_ACTIVE)
                else:
                    if self.pause_output:
                        self.controller.update_state_camera(Controller.CAMERA_STATE_PAUSED)
                        self.serial_controller.update_state_camera(Controller.CAMERA_STATE_PAUSED)
                    else:
                        self.controller.update_state_camera(Controller.CAMERA_STATE_ACTIVE)
                        self.serial_controller.update_state_camera(Controller.CAMERA_STATE_ACTIVE)

                self.time_debug("States updated", time_started)

                # Replace with black if none
                if self.final_output_frame is None:
                    self.final_output_frame = cv2.resize(black_frame, (self.output_width, self.output_height))

                # Send final image
                self.push_output_image()
                # cv2.waitKey(1)

                self.time_debug("Output pushed", time_started)

                # Control cycle time
                if self.maximum_fps > 0:
                    while time.time() - time_started < (1. / self.maximum_fps):
                        time.sleep(0.001)
                else:
                    while self.maximum_fps <= 0:
                        time.sleep(0.01)

                # Calculate FPS
                current_fps = 1. / (time.time() - time_started)

                # Filter FPS
                if self.real_fps == 0:
                    self.real_fps = current_fps
                self.real_fps = self.real_fps * 0.90 + current_fps * 0.10

                # Update FPS
                get_updater().call_latest(self.label_fps.setText, "FPS: " + str(round(self.real_fps, 1)))

                self.time_debug("Cycle finished", time_started)
                if TIME_DEBUG:
                    print()

            # OpenCV loop error
            except Exception as e:
                logging.exception(e)

        # End of while loop
        cv2.destroyAllWindows()
        logging.warning("OpenCV loop exited")

    def filter_corners(self, tl, tr, br, bl):
        # Convert to float
        tl_f = [float(tl[0]), float(tl[1])]
        tr_f = [float(tr[0]), float(tr[1])]
        br_f = [float(br[0]), float(br[1])]
        bl_f = [float(bl[0]), float(bl[1])]

        # Find average difference
        diff_tl = (abs(tl_f[0] - self.tl_filtered[0]) + abs(tl_f[1] - self.tl_filtered[1])) / 2.
        diff_tr = (abs(tr_f[0] - self.tr_filtered[0]) + abs(tr_f[1] - self.tr_filtered[1])) / 2.
        diff_br = (abs(br_f[0] - self.br_filtered[0]) + abs(br_f[1] - self.br_filtered[1])) / 2.
        diff_bl = (abs(bl_f[0] - self.bl_filtered[0]) + abs(bl_f[1] - self.bl_filtered[1])) / 2.
        diff = (diff_tl + diff_tr + diff_br + diff_bl) / 4.
        if diff > self.aruco_filter_scale:
            diff = self.aruco_filter_scale

        # Calculate filter factor
        filter_factor = 1. - (diff / self.aruco_filter_scale)
        if filter_factor >= 1.:
            filter_factor = 0.99

        self.tl_filtered = [self.tl_filtered[0] * filter_factor + tl_f[0] * (1. - filter_factor),
                            self.tl_filtered[1] * filter_factor + tl_f[1] * (1. - filter_factor)]

        self.tr_filtered = [self.tr_filtered[0] * filter_factor + tr_f[0] * (1. - filter_factor),
                            self.tr_filtered[1] * filter_factor + tr_f[1] * (1. - filter_factor)]

        self.br_filtered = [self.br_filtered[0] * filter_factor + br_f[0] * (1. - filter_factor),
                            self.br_filtered[1] * filter_factor + br_f[1] * (1. - filter_factor)]

        self.bl_filtered = [self.bl_filtered[0] * filter_factor + bl_f[0] * (1. - filter_factor),
                            self.bl_filtered[1] * filter_factor + bl_f[1] * (1. - filter_factor)]

        # Convert back to int
        tl = [int(self.tl_filtered[0]), int(self.tl_filtered[1])]
        tr = [int(self.tr_filtered[0]), int(self.tr_filtered[1])]
        br = [int(self.br_filtered[0]), int(self.br_filtered[1])]
        bl = [int(self.bl_filtered[0]), int(self.bl_filtered[1])]

        # Return filtered data
        return tl, tr, br, bl

    def set_preview_mode(self, preview_mode: int):
        self.preview_mode = preview_mode

    def push_output_image(self):
        # Preview output
        if self.preview_mode == PREVIEW_OUTPUT:
            preview_image = self.final_output_frame

        # Preview window
        elif self.preview_mode == PREVIEW_WINDOW:
            preview_image = self.window_image

        # Preview aruco
        elif self.preview_mode == PREVIEW_ARUCO:
            preview_image = self.aruco_image

        # Preview source
        else:
            preview_image = self.input_frame

        try:
            # Resize preview
            preview_resized = resize_keep_ratio(preview_image, self.preview_label.size().width(),
                                                self.preview_label.size().height())

            # Convert to pixmap
            pixmap = QPixmap.fromImage(
                QImage(preview_resized.data, preview_resized.shape[1], preview_resized.shape[0],
                       3 * preview_resized.shape[1], QImage.Format_BGR888))

            # Push to preview
            get_updater().call_latest(self.preview_label.setPixmap, pixmap)

            # Push to Flicker class
            # Don't update window image in fullscreen mode with old capture mode
            if not self.flicker.is_force_fullscreen_enabled():
                self.flicker.set_frame(self.window_image)

            # Push to http server
            self.http_stream.set_frame(self.final_output_frame)

            # Virtual camera
            self.virtual_camera.set_frame(self.final_output_frame)
        except Exception as e:
            logging.exception(e)
