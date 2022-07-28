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

import PyQt5
import cv2
import numpy as np
import pyvirtualcam
import qimage2ndarray
import win32con
import win32gui
import win32ui
from PIL import ImageGrab
from PyQt5 import QtCore
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication
from cv2 import aruco

import winguiauto

VIDEO_NOISE_FILE = "noise.avi"

PREVIEW_OUTPUT = 0
PREVIEW_WINDOW = 1
PREVIEW_SOURCE = 2

FAKE_MODE_ARUCO = 0
FAKE_MODE_FLICKER = 1

WINDOW_CAPTURE_STABLE = 0
WINDOW_CAPTURE_EXPERIMENTAL = 1


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


def calculate_and_apply_brightness(marker_tl, marker_tr, marker_br, marker_bl, input_gray,
                                   window_image, use_gradient=False):
    # Calculate max white value
    # Top left
    aruco_mask = np.zeros(input_gray.shape, dtype=input_gray.dtype)
    cv2.drawContours(aruco_mask, [np.array([marker_tl], dtype=int)], -1, (255, 255, 255), -1)
    masked = cv2.bitwise_and(input_gray, aruco_mask)
    max_white_tl = int(masked.max())

    # Top right
    aruco_mask = np.zeros(input_gray.shape, dtype=input_gray.dtype)
    cv2.drawContours(aruco_mask, [np.array([marker_tr], dtype=int)], -1, (255, 255, 255), -1)
    masked = cv2.bitwise_and(input_gray, aruco_mask)
    max_white_tr = int(masked.max())

    # Bottom right
    aruco_mask = np.zeros(input_gray.shape, dtype=input_gray.dtype)
    cv2.drawContours(aruco_mask, [np.array([marker_br], dtype=int)], -1, (255, 255, 255), -1)
    masked = cv2.bitwise_and(input_gray, aruco_mask)
    max_white_br = int(masked.max())

    # Bottom left
    aruco_mask = np.zeros(input_gray.shape, dtype=input_gray.dtype)
    cv2.drawContours(aruco_mask, [np.array([marker_bl], dtype=int)], -1, (255, 255, 255), -1)
    masked = cv2.bitwise_and(input_gray, aruco_mask)
    max_white_bl = int(masked.max())

    # Calculate average white values
    white_left = (max_white_tl + max_white_bl) // 2
    white_top = (max_white_tl + max_white_tr) // 2
    white_right = (max_white_tr + max_white_br) // 2
    white_bottom = (max_white_bl + max_white_br) // 2

    # Brightness gradient
    if use_gradient:
        # Create horizontal gradient
        if white_left > white_right:
            horizontal_brightness_gradient = list(range(white_right, white_left + 1))
            horizontal_brightness_gradient.reverse()
        else:
            horizontal_brightness_gradient = list(range(white_left, white_right + 1))

        # Create vertical gradient
        if white_top > white_bottom:
            vertical_brightness_gradient = list(range(white_bottom, white_top + 1))
            vertical_brightness_gradient.reverse()
        else:
            vertical_brightness_gradient = list(range(white_top, white_bottom + 1))

        # Stretch gradients to match window image size
        horizontal_brightness_gradient = stretch_to(horizontal_brightness_gradient,
                                                    window_image.shape[1])
        vertical_brightness_gradient = stretch_to(vertical_brightness_gradient,
                                                  window_image.shape[0])

        # Tile gradients to 2D images
        horizontal_brightness_gradient = np.array([horizontal_brightness_gradient], dtype=window_image.dtype)
        horizontal_brightness_gradient = np.tile(horizontal_brightness_gradient, (window_image.shape[0], 1))
        vertical_brightness_gradient = np.array([vertical_brightness_gradient], dtype=window_image.dtype)
        vertical_brightness_gradient = np.tile(vertical_brightness_gradient, (window_image.shape[1], 1))
        vertical_brightness_gradient = np.transpose(vertical_brightness_gradient)

        # Combine gradients
        brightness_gradient = cv2.addWeighted(horizontal_brightness_gradient, 0.5,
                                              vertical_brightness_gradient, 0.5, 0.)

        # Apply blur
        # brightness_gradient = cv2.GaussianBlur(brightness_gradient, (49, 49), 0)

        # Add brightness gradient
        window_image_hsv = cv2.cvtColor(window_image, cv2.COLOR_BGR2HSV)
        window_image_hsv[:, :, 2] = cv2.bitwise_and(window_image_hsv[:, :, 2], brightness_gradient)

    # Average brightness
    else:
        # Calculate average brightness
        average_brightness = (white_left + white_top + white_right + white_bottom) // 4

        # Add average brightness
        window_image_hsv = cv2.cvtColor(window_image, cv2.COLOR_BGR2HSV)
        window_image_hsv[:, :, 2] = cv2.bitwise_and(window_image_hsv[:, :, 2], average_brightness)

    return cv2.cvtColor(window_image_hsv, cv2.COLOR_HSV2BGR)


class OpenCVHandler:
    def __init__(self, settings_handler, http_stream, flicker,
                 update_preview: QtCore.pyqtSignal, preview_label: PyQt5.QtWidgets.QLabel):
        """
        Initializes OpenCVHandler class
        :param settings_handler: SettingsHandler class
        :param http_stream: HTTPStream class with set_frame function
        :param update_preview: qtSignal from main form
        :param preview_label: preview element for size measurement
        """
        self.settings_handler = settings_handler
        self.http_stream = http_stream
        self.flicker = flicker
        self.update_preview = update_preview
        self.preview_label = preview_label

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

        # Use 4x4 50 ARUco dictionary
        self.aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)

        # ARUco detection parameters
        # TODO: Improve this
        self.parameters = cv2.aruco.DetectorParameters_create()
        self.parameters.adaptiveThreshConstant = 10

    def set_camera_capture_allowed(self, camera_capture_allowed):
        self.camera_capture_allowed = camera_capture_allowed

    def get_final_output_frame(self):
        return self.final_output_frame

    def get_window_image(self):
        return self.window_image

    def start_opencv_thread(self):
        """
        Starts OpenCV loop as background thread
        :return:
        """
        self.opencv_thread_running = True
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
        self.crop_top = int(self.settings_handler.settings["window_crop"][0])
        self.crop_left = int(self.settings_handler.settings["window_crop"][1])
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

    def open_camera(self):
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
            self.video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self.video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

            # Focus
            self.video_capture.set(cv2.CAP_PROP_AUTOFOCUS, 1 if self.input_camera_focus_auto else 0)
            self.video_capture.set(cv2.CAP_PROP_FOCUS, self.input_camera_focus)

            # Exposure
            self.video_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1 if self.input_camera_exposure_auto else 0)
            self.video_capture.set(cv2.CAP_PROP_EXPOSURE, self.input_camera_exposure)

            # Disable auto white balance
            self.video_capture.set(cv2.CAP_PROP_AUTO_WB, 0)

        except Exception as e:
            logging.exception(e)

    def start_camera_output(self):
        cam = pyvirtualcam.Camera(width=1280, height=720, fps=20)

        print(f'Using virtual camera: {cam.device}')

        frame = np.zeros((cam.height, cam.width, 3), np.uint8)  # RGB
        while True:
            frame[:] = cam.frames_sent % 255  # grayscale animation
            cam.send(frame)
            cam.sleep_until_next_frame()

    def close_camera(self):
        """
        Stops source camera
        :return:
        """
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

        noise = cv2.VideoCapture(VIDEO_NOISE_FILE)

        while self.opencv_thread_running:
            try:
                # Start without error
                error = False

                # Allow aruco detection and screen faking
                allow_fake_screen = True

                # Record time
                time_started = time.time()

                # Grab window image
                # noinspection PyBroadException
                window_image = None
                try:
                    if self.window_capture_allowed and self.hwnd is not None:
                        if self.window_capture_method == WINDOW_CAPTURE_STABLE:
                            # Don't update window image in fullscreen mode with stable capture mode
                            if not self.flicker.is_force_fullscreen_enabled():
                                rect = win32gui.GetWindowPlacement(self.hwnd)[-1]
                                window_image = cv2.cvtColor(np.array(ImageGrab.grab(rect)), cv2.COLOR_RGB2BGR)
                        elif self.window_capture_method == WINDOW_CAPTURE_EXPERIMENTAL:
                            # Get window rectangle
                            window_rect = win32gui.GetWindowRect(self.hwnd)
                            w = window_rect[2] - window_rect[0]
                            h = window_rect[3] - window_rect[1]

                            # Get the window image data
                            self.window_dc = win32gui.GetWindowDC(self.hwnd)
                            self.dc_object = win32ui.CreateDCFromHandle(self.window_dc)
                            self.c_dc = self.dc_object.CreateCompatibleDC()
                            self.data_bitmap = win32ui.CreateBitmap()
                            self.data_bitmap.CreateCompatibleBitmap(self.dc_object, w, h)
                            self.c_dc.SelectObject(self.data_bitmap)
                            self.c_dc.BitBlt((0, 0), (w, h), self.dc_object, (0, 0), win32con.SRCCOPY)

                            # Convert the raw data into a format opencv can read
                            signed_ints_array = self.data_bitmap.GetBitmapBits(True)
                            img = np.fromstring(signed_ints_array, dtype='uint8')
                            img.shape = (h, w, 4)
                            img = img[..., :3]
                            window_image = np.ascontiguousarray(img)
                    else:
                        allow_fake_screen = False
                except:
                    logging.error("Can't get window image!")
                    window_image = black_frame.copy()
                    error = True

                # Replace window image with black if error occurs
                if window_image is None:
                    window_image = black_frame.copy()

                # Crop window image
                self.window_image = window_image[
                                    self.crop_top:window_image.shape[0] - self.crop_top - self.crop_bottom,
                                    self.crop_left:window_image.shape[1] - self.crop_left - self.crop_right]

                # Grab the current camera frame
                # noinspection PyBroadException
                try:
                    if self.camera_capture_allowed and self.video_capture.isOpened() and not error:
                        if self.fake_mode == FAKE_MODE_FLICKER and self.fake_screen:
                            # Count flicker frames
                            self.flick_counter += 1

                            # Flick!
                            if self.flick_counter == self.flicker_interval:
                                self.flicker.flick_frame_start(self.window_image)

                            # Counter ended
                            elif self.flick_counter >= self.flicker_interval + self.flicker_duration:
                                # Update frame blending
                                if flicker_key_frame_2 is not None:
                                    flicker_key_frame_1 = flicker_key_frame_2.copy()
                                flicker_key_frame_2 = None

                                # Check image
                                x_1 = self.flicker.geometry().x()
                                y_1 = self.flicker.geometry().y()
                                x_2 = x_1 + self.flicker.geometry().width()
                                y_2 = y_1 + self.flicker.geometry().height()
                                real_image = cv2.resize(cv2.cvtColor(
                                    np.array(ImageGrab.grab((x_1, y_1, x_2, y_2))), cv2.COLOR_RGB2BGR),
                                    (self.flicker.width_, self.flicker.height_))
                                if real_image[0, 0, 0] == 255 \
                                        and real_image[0, 0, 1] == 0 \
                                        and real_image[0, 0, 2] == 0 \
                                        and real_image[0, self.flicker.width_ - 1, 0] == 0 \
                                        and real_image[0, self.flicker.width_ - 1, 1] == 255 \
                                        and real_image[0, self.flicker.width_ - 1, 2] == 0 \
                                        and real_image[self.flicker.height_ - 1, self.flicker.width_ - 1, 0] == 0 \
                                        and real_image[self.flicker.height_ - 1, self.flicker.width_ - 1, 1] == 0 \
                                        and real_image[self.flicker.height_ - 1, self.flicker.width_ - 1, 2] == 255:
                                    # Stop flicking
                                    self.flicker.flick_frame_stop()

                                    # Retrieve frame
                                    input_ret, flicker_key_frame_2 = self.video_capture.read()

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
                            self.flicker.flick_frame_stop()

                            # Reset flick variables
                            self.flick_counter = 0
                            flicker_key_frame_1 = None
                            flicker_key_frame_2 = None

                            # Retrieve frame
                            input_ret, self.input_frame = self.video_capture.read()

                    # No camera image
                    else:
                        # Stop flicking
                        self.flicker.flick_frame_stop()

                        # Reset flicker variables
                        flicker_key_frame_1 = None
                        flicker_key_frame_2 = None

                        # Disable fake screen
                        allow_fake_screen = False
                except Exception as e:
                    print(e)
                    input_ret = False
                    error = True

                # Replace frame with black if error occurs
                if self.input_frame is None or not input_ret:
                    self.input_frame = black_frame.copy()

                # Create copy of input frame
                output_frame = self.input_frame.copy()

                # Disallow faking screen
                if not self.fake_screen or error:
                    allow_fake_screen = False

                # Convert input camera image to gray
                input_gray = cv2.cvtColor(self.input_frame, cv2.COLOR_BGR2GRAY)

                # Invert frame if needed
                if self.aruco_invert:
                    gray_for_aruco = cv2.bitwise_not(input_gray)
                else:
                    gray_for_aruco = input_gray

                # Find aruco markers
                corners, ids, _ = aruco.detectMarkers(gray_for_aruco, self.aruco_dict,
                                                      parameters=self.parameters)
                # corners, ids, _ = aruco.detectMarkers(image=input_gray, dictionary=self.aruco_dict,
                #                                             parameters=self.parameters,
                #                                             cameraMatrix=self.CAMERA_MATRIX,
                #                                             distCoeff=self.CAMERA_DISTORTION)

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

                                # Calculate final screen coordinates
                                # tl = self.get_marker_point(marker_tl, Marker.POSITION_TOP_LEFT)
                                # tr = self.get_marker_point(marker_tr, Marker.POSITION_TOP_RIGHT)
                                # br = self.get_marker_point(marker_br, Marker.POSITION_BOTTOM_RIGHT)
                                # bl = self.get_marker_point(marker_bl, Marker.POSITION_BOTTOM_LEFT)
                                tl = marker_tl[0]
                                tr = marker_tr[1]
                                br = marker_br[2]
                                bl = marker_bl[3]

                                # Dimensions of the frames
                                overlay_height = self.window_image.shape[0]
                                overlay_width = self.window_image.shape[1]
                                source_height = self.input_frame.shape[0]
                                source_width = self.input_frame.shape[1]

                                # Apply brightness gradient to image
                                window_image = calculate_and_apply_brightness(marker_tl, marker_tr,
                                                                              marker_br, marker_bl,
                                                                              input_gray,
                                                                              self.window_image,
                                                                              self.brightness_gradient_enabled)

                                # Source points (full size of overlay image)
                                points_src = np.array([
                                    [0, 0],
                                    [overlay_width - 1, 0],
                                    [overlay_width - 1, overlay_height - 1],
                                    [0, overlay_height - 1]], dtype='float32')

                                # Destination points (projection)
                                points_dst = np.array([tl, tr, br, bl], dtype='float32')

                                # Stretch window
                                center_x, center_y = get_center(points_dst)
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

                # Resize output
                output_frame = cv2.resize(output_frame, (self.output_width, self.output_height))

                # Is frame totally black?
                is_output_frame_black = cv2.countNonZero(cv2.cvtColor(output_frame, cv2.COLOR_BGR2GRAY)) == 0

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

                    # Add noise
                    # noinspection PyBroadException
                    try:
                        # Read noise from file
                        noise_ret, noise_frame = noise.read()
                        if not noise_ret:
                            noise = cv2.VideoCapture("noise.avi")
                            _, noise_frame = noise.read()

                        # Convert to grayscale
                        noise_frame = cv2.cvtColor(noise_frame, cv2.COLOR_BGR2GRAY)

                        # Crop or resize
                        if self.output_width <= noise_frame.shape[1] and self.output_height <= noise_frame.shape[0]:
                            noise_frame = noise_frame[0:self.output_height, 0:self.output_width]
                        else:
                            noise_frame = cv2.resize(noise_frame,
                                                     (self.output_width, self.output_height),
                                                     interpolation=cv2.INTER_AREA)

                        # Convert output frame to HSV
                        output_frame_hsv = cv2.cvtColor(output_frame, cv2.COLOR_BGR2HSV)

                        # Add noise to darken areas
                        output_frame_v_noisy = cv2.bitwise_not(
                            cv2.bitwise_and(cv2.bitwise_not(output_frame_hsv[:, :, 2]), noise_frame))

                        # Combine with clear output
                        output_frame_v_noisy = cv2.addWeighted(output_frame_hsv[:, :, 2], 1. - self.output_noise_amount,
                                                               output_frame_v_noisy, self.output_noise_amount, 0.)
                        output_frame_hsv[:, :, 2] = output_frame_v_noisy

                        # Convert back to BGR
                        output_frame = cv2.cvtColor(output_frame_hsv, cv2.COLOR_HSV2BGR)
                    except:
                        pass

                # Make final image
                if not error:
                    self.final_output_frame = output_frame.copy()

                # Replace with black if none
                if self.final_output_frame is None:
                    self.final_output_frame = black_frame.copy()

                # Send final image
                self.push_output_image()
                # cv2.waitKey(1)

                # Minimum cycle time is 33ms
                while time.time() - time_started < 0.033:
                    time.sleep(0.001)

                # Convert to ms
                # cycle_time = ((time.time() - time_started) * 1000)

            # OpenCV loop error
            except Exception as e:
                logging.exception(e)

        # End of while loop
        cv2.destroyAllWindows()
        logging.warning("OpenCV loop exited")

    def set_preview_mode(self, preview_mode: int):
        self.preview_mode = preview_mode

    def push_output_image(self):
        # Preview output
        if self.preview_mode == PREVIEW_OUTPUT:
            preview_image = self.final_output_frame

        # Preview window
        elif self.preview_mode == PREVIEW_WINDOW:
            preview_image = self.window_image

        # Preview source
        else:
            preview_image = self.input_frame

        try:
            # Convert to pixmap and resize
            # pixmap = QPixmap.fromImage(
            #     qimage2ndarray.array2qimage(
            #         cv2.resize(
            #            cv2.cvtColor(preview_image, cv2.COLOR_BGR2RGB),
            #           (self.preview_label.size().width(), self.preview_label.size().height()),
            #            interpolation=cv2.INTER_NEAREST)))

            pixmap = QPixmap.fromImage(qimage2ndarray.array2qimage(
                resize_keep_ratio(cv2.cvtColor(preview_image, cv2.COLOR_BGR2RGB),
                                  self.preview_label.size().width(),
                                  self.preview_label.size().height())))

            # Push to preview
            self.update_preview.emit(pixmap)

            # Push to http server
            self.http_stream.set_frame(self.final_output_frame)
        except Exception as e:
            logging.exception(e)
