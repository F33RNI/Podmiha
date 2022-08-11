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

import os
import shutil
import subprocess
import sys

# Name of the first file
import time

import Podmiha

MAIN_FILE = "Podmiha"

# Path to OpenCV to include into --paths
OPENCV_PATH = os.path.expanduser('~') + "/AppData/Local/Programs/Python/Python37/Lib/site-packages/cv2/python-3.7"
#OPENCV_PATH = "./cv2/python-3.7"

# Text to add to the spec file
SPEC_FILE_HEADER = "import PyInstaller.config\n" \
                   "PyInstaller.config.CONF[\"workpath\"] = \"./build\"\n"

# Files and folders to include in final build directory (dist/Podmiha folder)
INCLUDE_FILES = ["icons",
                 "Podmiha-serial-controller/.pio/build/nanoatmega328",
                 "gui.ui",
                 "noise.avi",
                 "README.md",
                 "LICENSE",
                 "camera_calibration.py",
                 "camera_calibration.bat",
                 "charuco_board.jpg",
                 "audio_noise.raw"]

# Files and folders to exclude from final build directory (dist/Podmiha folder)
EXCLUDE_FILES = ["cv2"]

# *.py files to exclude from final build
EXCLUDE_FROM_BUILD = ["camera_calibration.py",
                      "audio_noise_generator.py"]

if __name__ == "__main__":
    pyi_command = []

    # Remove dist folder is exists
    if "dist" in os.listdir("./"):
        shutil.rmtree("dist", ignore_errors=True)
        print("dist folder deleted")

    # Remove build folder is exists
    if "build" in os.listdir("./"):
        shutil.rmtree("build", ignore_errors=True)
        print("build folder deleted")

    # Add all .py files to pyi_command
    for file in os.listdir("./"):
        if file.endswith(".py") and str(file) != MAIN_FILE \
                and str(file) != os.path.basename(__file__) \
                and str(file) not in EXCLUDE_FROM_BUILD:
            pyi_command.append(str(file))

    # Add main file to pyi_command
    pyi_command.insert(0, MAIN_FILE + ".py")

    # OpenCV path
    OPENCV_PATH = OPENCV_PATH.replace("\\", "/").replace("//", "/")
    pyi_command.insert(0, OPENCV_PATH)
    pyi_command.insert(0, "--paths")

    # OpenCV .dll path
    pyi_command.insert(0, "D:/opencv/opencv-4.5.5/build/install/x64/vc16/bin")
    pyi_command.insert(0, "--paths")

    # Add icon
    pyi_command.insert(0, "--icon=./icons/icon.ico")

    # Other command arguments
    pyi_command.insert(0, "--windowed")
    # pyi_command.insert(0, "--onefile")
    pyi_command.insert(0, "pyi-makespec")

    # Delete previous spec
    if os.path.exists(MAIN_FILE + ".spec"):
        os.remove(MAIN_FILE + ".spec")

    # Execute pyi
    subprocess.run(pyi_command, text=True)

    # Spec file generated
    if os.path.exists(MAIN_FILE + ".spec"):
        with open(MAIN_FILE + ".spec", 'r') as spec_file:
            # Read spec file
            spec_data = spec_file.read()
            spec_file.close()

            # Add header to spec file
            spec_data = SPEC_FILE_HEADER + spec_data

            # Disable console
            spec_data = spec_data.replace("console=True", "console=False")

            # spec_data = spec_data.replace("excludes=[]", "excludes=[\"cv2\"]")
            # spec_data = spec_data.replace("hiddenimports=[]", "hiddenimports=[\"cv2\"]")

            with open(MAIN_FILE + ".spec", "w") as spec_file_output:
                # Write updated spec file
                spec_file_output.write(spec_data)
                spec_file_output.close()

                # Create new pyi command
                pyi_command = ["pyinstaller", MAIN_FILE + ".spec", "--clean"]

                # Execute pyi
                subprocess.run(pyi_command, text=True)

                # If dist folder created
                if "dist" in os.listdir(".") and MAIN_FILE in os.listdir("./dist"):

                    # Remove build folder is exists
                    if "build" in os.listdir("./"):
                        shutil.rmtree("build", ignore_errors=True)
                        print("build folder deleted")

                    # Wait some time
                    print("Waiting 1 second...")
                    time.sleep(1)

                    # Copy include files to it
                    for file in INCLUDE_FILES:
                        try:
                            if os.path.isfile(file):
                                shutil.copy(file, "dist/" + MAIN_FILE + "/" + file)
                            elif os.path.isdir(file):
                                shutil.copytree(file, "dist/" + MAIN_FILE + "/" + file)
                            print("Added", file, "to dist/", MAIN_FILE, "folder")
                        except Exception as e:
                            print("Error copying file!", e)

                    # Wait some time
                    print("Waiting 1 second...")
                    time.sleep(1)

                    # Exclude files to it
                    for file in EXCLUDE_FILES:
                        try:
                            if os.path.isfile("dist/" + MAIN_FILE + "/" + file):
                                os.remove("dist/" + MAIN_FILE + "/" + file)
                            elif os.path.isdir("dist/" + MAIN_FILE + "/" + file):
                                shutil.rmtree("dist/" + MAIN_FILE + "/" + file)
                            print("Removed", file, "from dist/", MAIN_FILE, "folder")
                        except Exception as e:
                            print("Error excluding file!", e)

                    # Wait some time
                    print("Waiting 1 second...")
                    time.sleep(1)

                    # Rename final folder
                    os.rename("dist/" + MAIN_FILE, "dist/" + MAIN_FILE + "-" + Podmiha.APP_VERSION + "-windows")

                else:
                    print("Error. No dist/" + MAIN_FILE + " folder!")

    # Spec file not generated
    else:
        print("Error generating spec!")
