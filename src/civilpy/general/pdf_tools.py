"""
CivilPy
Copyright (C) 2019 - Dane Parks

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import json
import subprocess
from pathlib import Path

with open(Path.home() / "secrets.json") as f:
    secrets = json.load(f)


def open_pdf_to_page(pdf_path, page_number):
    bluebeam_path = secrets["BB_PATH"]
    command = f'"{bluebeam_path}" "{pdf_path}" /A page={page_number}=OpenActions'

    try:
        subprocess.Popen(command, shell=True)
    except Exception as e:
        print(f"An error occurred: {e}")

def open_pdf_to_page_adobe(pdf_path, page_number):
    bluebeam_path = secrets["ADOBE_PATH"]
    command = f'"{bluebeam_path}" "{pdf_path}" /A page={page_number}=OpenActions'

    try:
        subprocess.Popen(command, shell=True)
    except Exception as e:
        print(f"An error occurred: {e}")