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

import cv2
from cv2 import aruco

# ChAruco board variables
CHARUCOBOARD_ROWCOUNT = 7
CHARUCOBOARD_COLCOUNT = 5
ARUCO_DICT = aruco.Dictionary_get(aruco.DICT_5X5_1000)

# Create constants to be passed into OpenCV and Aruco methods
CHARUCO_BOARD = aruco.CharucoBoard_create(
    squaresX=CHARUCOBOARD_COLCOUNT,
    squaresY=CHARUCOBOARD_ROWCOUNT,
    squareLength=0.04,
    markerLength=0.02,
    dictionary=ARUCO_DICT)

# Create the arrays and variables we'll use to store info like corners and IDs from images processed
corners_all = []
ids_all = []
corners_all_old = []
ids_all_old = []
image_size = None

# Save ChAruco Board
charuco_image = CHARUCO_BOARD.draw((800, 800))
cv2.imwrite("charuco_board.jpg", charuco_image)

# Reset counter
i = 0

# Matrix and distortions
camera_matrix = None
camera_distortions = None

# Open camera
CAMERA_ID = int(input("Enter camera ID: "))
print("Camera ID:", CAMERA_ID)
cap = cv2.VideoCapture(CAMERA_ID)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

# Show charuco board
# cv2.imshow("ChAruco Board", charuco_image)

# Print help info
print("--------------")
print("Show ChARuCo board on camera and press SPACE to apply calibration")
print("Press X key to undo last calibration")
print("--------------")

while True:
    # Get image from camera
    ret, img = cap.read()

    # Check image
    if not ret:
        break

    # Clone source image to undistorted
    img_undistorted = img.copy()

    # Get key
    key = cv2.waitKey(1) & 0xFF

    # Grayscale the image
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Find aruco markers
    corners, ids, _ = aruco.detectMarkers(
        image=gray,
        dictionary=ARUCO_DICT)

    # Check for aruco
    if ids is not None:
        # Outline the aruco markers found
        img = aruco.drawDetectedMarkers(
            image=img,
            corners=corners)

        # Get charuco corners and ids from detected aruco markers
        response, charuco_corners, charuco_ids = aruco.interpolateCornersCharuco(
            markerCorners=corners,
            markerIds=ids,
            image=gray,
            board=CHARUCO_BOARD)

        # Undo on X
        if key == ord("x") and len(corners_all_old) > 0 and len(ids_all_old) > 0:
            print("Undoing...")
            # Restore old data
            corners_all = corners_all_old.copy()
            ids_all = ids_all_old.copy()

            # Calculate camera_matrix and camera_distortions
            print("Calculating calibration...")
            calibration, camera_matrix, camera_distortions, rvecs, tvecs = aruco.calibrateCameraCharuco(
                charucoCorners=corners_all,
                charucoIds=ids_all,
                board=CHARUCO_BOARD,
                imageSize=image_size,
                cameraMatrix=None,
                distCoeffs=None)

        # If a Charuco board was found, let's collect image/corner points
        # Requiring at least 20 squares
        if response > 20:
            print("Charuco board detected. Press SPACE to append this image")

            # Draw the Charuco board
            img = aruco.drawDetectedCornersCharuco(
                image=img,
                charucoCorners=charuco_corners,
                charucoIds=charuco_ids)

            # Append calibration on Space bar press
            if key == 32:
                corners_all_old = corners_all.copy()
                ids_all_old = ids_all.copy()
                corners_all.append(charuco_corners)
                ids_all.append(charuco_ids)

                # Print image number
                i += 1
                print("Calibration image: ", i)

                # Calculate camera_matrix and camera_distortions
                print("Calculating calibration...")
                calibration, camera_matrix, camera_distortions, rvecs, tvecs = aruco.calibrateCameraCharuco(
                    charucoCorners=corners_all,
                    charucoIds=ids_all,
                    board=CHARUCO_BOARD,
                    imageSize=image_size,
                    cameraMatrix=None,
                    distCoeffs=None)

            # If our image size is unknown, set it now
            if not image_size:
                image_size = gray.shape[::-1]

    # Fix distortion in real-time
    if camera_matrix is not None and camera_distortions is not None:
        img_undistorted = cv2.undistort(img, camera_matrix, camera_distortions, None, camera_matrix)

    # Show current images
    cv2.imshow("Frame", cv2.resize(img, (640, 360)))
    cv2.imshow("Undistorted frame", cv2.resize(img_undistorted, (640, 360)))

    # Exit on Q key
    if key == ord("q"):
        print("Exiting...")
        break

# Destroy any open CV windows and release camera
cap.release()
cv2.destroyAllWindows()

# Calculate calibration
print("Calculating calibration...")
calibration, camera_matrix, camera_distortions, rvecs, tvecs = aruco.calibrateCameraCharuco(
    charucoCorners=corners_all,
    charucoIds=ids_all,
    board=CHARUCO_BOARD,
    imageSize=image_size,
    cameraMatrix=None,
    distCoeffs=None)

# Save to file
print("Writing to file...")
cv_file = cv2.FileStorage("camera_calibration.yaml", cv2.FILE_STORAGE_WRITE)
cv_file.write("camera_matrix", camera_matrix)
cv_file.write("dist_coeff", camera_distortions)
cv_file.release()
