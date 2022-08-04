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
import numpy as np

print("Enter camera ID: ")
CAMERA_ID = int(input())
print()
print("Camera ID:", CAMERA_ID)

cap = cv2.VideoCapture(CAMERA_ID)
WAIT_TIME = 10
# Termination criteria
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# Prepare object points
obj_p = np.zeros((6 * 7, 3), np.float32)
obj_p[:, :2] = np.transpose(np.mgrid[0:7, 0:6]).reshape(-1, 2)

# Arrays to store object points and image points from all the images.
object_points = []  # 3d point in real world space
image_points = []  # 2d points in image plane.

# Calibration images counter
i = 0

while True:
    # Read frame from camera
    _, frame = cap.read()

    # operations on the frame
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Find the chess board corners
    ret, corners = cv2.findChessboardCorners(gray, (7, 6), None)

    # If found, add object points, image points (after refining them)
    if ret:
        # Find corners
        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

        # Draw detected chessboard
        frame = cv2.drawChessboardCorners(frame, (7, 6), corners2, ret)

        # Print help message
        print("Press SPACE to append calibration")

        # Append calibration on Space bar press
        if cv2.waitKey(1) & 0xFF == 32:
            # Append data
            object_points.append(obj_p)
            image_points.append(corners2)

            # Print image number
            i += 1
            print("Calibration image: ", i)

    # Show image
    cv2.imshow("Frame", frame)

    # Exit on Q key
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# Close camera and image preview
cap.release()
cv2.destroyAllWindows()

# Calculate camera matrix and distortion coefficients
_, mtx, dist, _, _ = cv2.calibrateCamera(object_points, image_points, gray.shape[::-1], None, None)

# Save to file
cv_file = cv2.FileStorage("camera_calibration.yaml", cv2.FILE_STORAGE_WRITE)
cv_file.write("camera_matrix", mtx)
cv_file.write("dist_coeff", dist)
cv_file.release()
