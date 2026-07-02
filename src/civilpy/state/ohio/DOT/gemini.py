#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

import os
from dotenv import load_dotenv
import google.generativeai as genai
import PIL.Image
import json
import typing_extensions as typing

# 1. SETUP: Load environment variables
load_dotenv()  # This loads the .env file
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("API Key not found. Make sure you have a .env file with GOOGLE_API_KEY defined.")

genai.configure(api_key=api_key)

# 2. DEFINE THE INTERMEDIATE SCHEMA
# We ask Gemini for a list first to ensure stability.
class DrawingEntry(typing.TypedDict):
    drawing_code: str
    date: str

class ExtractionResult(typing.TypedDict):
    drawings: list[DrawingEntry]

# 3. LOAD THE IMAGE
# Ensure 'image_5101a8.png' is in your directory
try:
    img = PIL.Image.open('image_5101a8.png')
except FileNotFoundError:
    print("Error: Image file not found.")
    exit()

# 4. THE CALL
model = genai.GenerativeModel("gemini-1.5-flash")

prompt = """
Analyze this image of a "Supplemental Prints of Standard Construction Drawings" table.
Extract all drawing codes (like F-1, BP-2, etc.) and their corresponding dates.
Ignore empty rows.
"""

try:
    response = model.generate_content(
        [prompt, img],
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=ExtractionResult
        )
    )

    # 5. POST-PROCESSING
    raw_data = json.loads(response.text)

    # Transform list into your specific "StdConstructionDrawings" dictionary format
    formatted_output = {
        "StdConstructionDrawings": {
            item['drawing_code']: item['date']
            for item in raw_data['drawings']
        }
    }

    # 6. PRINT RESULT
    print(json.dumps(formatted_output, indent=4))

except Exception as e:
    print(f"An error occurred: {e}")
