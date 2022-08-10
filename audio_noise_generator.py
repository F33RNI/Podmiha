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

import numpy as np

# Settings
NOISE_FILE = "audio_noise.raw"
NOISE_DTYPE = np.float32

# How many samples to generate? length (s) = NUMBERS_TO_GENERATE / sample rate (Hz)
FILE_CHUNK_NUMBERS = 32000
NUMBERS_TO_GENERATE = 10 * FILE_CHUNK_NUMBERS

# Open file to write
with open("audio_noise.raw", "wb") as noise_file:
    # Initialize chunk counter
    chunk_counter = 0

    # Write all samples
    while chunk_counter < NUMBERS_TO_GENERATE:
        # Generate chunk of noise
        random_data = np.random.rand(FILE_CHUNK_NUMBERS).astype(NOISE_DTYPE)

        # Convert to bytes
        data_bytes = random_data.tobytes()

        # Write to file
        noise_file.write(data_bytes)

        # Increment counter
        chunk_counter += FILE_CHUNK_NUMBERS

        # Display progress
        progress = (chunk_counter / NUMBERS_TO_GENERATE) * 100.
        print("Progress: ", int(progress), "%")

    # Close file
    noise_file.close()
