import logging
import torch
import torchvision
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from PIL import Image
import fitz  # PyMuPDF
import torchvision.transforms as T
import os
import pytesseract
import pandas as pd
import re
import json

# --- Global Configuration ---
DISCOVERED_LABELS = sorted([
    'PID', 'Supplemental Specifications', 'Sheet Index', 'FAN',
    'Standard Construction Drawings', 'Special Provisions'
])
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


# --- Model Loading ---
def get_model(num_classes):
    """Defines the Faster R-CNN model architecture."""
    model = torchvision.models.detection.fasterrcnn_resnet50_fpn(weights=None)
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
    return model


def load_trained_model(model_path):
    """Loads the trained model weights and prepares it for inference."""
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found at: {model_path}")
    logging.info(f"Using device: {DEVICE}")
    num_classes = len(DISCOVERED_LABELS) + 1
    model = get_model(num_classes)
    model.load_state_dict(torch.load(model_path, map_location=DEVICE))
    model.to(DEVICE)
    model.eval()
    logging.info("✅ Model loaded successfully!")
    return model


# --- Core Extraction Logic (Internal) ---
def _find_section_in_pdf(model, pdf_path, target_label, page_number=1):
    doc = fitz.open(pdf_path)
    page_index = page_number - 1
    if not (0 <= page_index < len(doc)):
        doc.close();
        return None
    page = doc[page_index]
    pix = page.get_pixmap(dpi=300)
    doc.close()
    original_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return _find_section_in_image(model, original_image, target_label)


def _find_section_in_image(model, image_obj, target_label):
    id2label = {i + 1: name for i, name in enumerate(DISCOVERED_LABELS)}
    transform = T.ToTensor()
    img_tensor = transform(image_obj).to(DEVICE)
    with torch.no_grad():
        prediction = model([img_tensor])[0]
    best_box, best_score = None, 0.0
    for score, label_id, box in zip(prediction["scores"], prediction["labels"], prediction["boxes"]):
        if id2label.get(label_id.item()) == target_label and score > best_score:
            best_score, best_box = score, box.cpu().numpy()
    if best_box is not None:
        logging.info(f"  - Found '{target_label}' with confidence {best_score:.4f}")
        return {"best_box": best_box, "image": image_obj}
    return None


def _ocr_and_extract(section_info: dict) -> tuple[pd.DataFrame, Image.Image | None]:
    """
    Performs OCR on a cropped image section and reconstructs a DataFrame.

    Args:
        section_info (dict): A dictionary containing the bounding box and original image.

    Returns:
        tuple: A pandas DataFrame with the OCR data and the cropped PIL Image object.
               Returns an empty DataFrame and None if OCR fails.
    """
    if not section_info:
        return pd.DataFrame(), None

    best_box, original_image = section_info["best_box"], section_info["image"]
    img_width, img_height = original_image.size

    # Expand the bounding box to capture the full table
    xmin, ymin, xmax, ymax = best_box
    ymin_exp = max(0, ymin - 150)
    ymax_exp = min(img_height, ymax + 400)
    xmin_exp = max(0, xmin - 50)
    xmax_exp = min(img_width, xmax + 50)

    cropped_image = original_image.crop((xmin_exp, ymin_exp, xmax_exp, ymax_exp))

    try:
        ocr_data = pytesseract.image_to_data(cropped_image, output_type=pytesseract.Output.DATAFRAME)
    except pytesseract.TesseractNotFoundError:
        logging.error("\n--- OCR ERROR: Tesseract is not installed or not in your PATH. ---")
        return pd.DataFrame(), None

    ocr_data = ocr_data[ocr_data.conf > -1].dropna(subset=['text'])

    # --- THIS IS THE CORRECTED LINE ---
    ocr_data['text'] = ocr_data['text'].astype(str).str.strip()
    # ------------------------------------

    ocr_data = ocr_data[ocr_data.text != '']

    if ocr_data.empty:
        return pd.DataFrame(), None

    # Reconstruct table from OCR words
    grouped = ocr_data.groupby(['block_num', 'par_num', 'line_num'])
    table_rows = [' '.join(words.sort_values('left')['text']).split() for _, words in grouped]
    max_cols = max(len(row) for row in table_rows) if table_rows else 0
    padded_rows = [row + [None] * (max_cols - len(row)) for row in table_rows]

    return pd.DataFrame(padded_rows), cropped_image


# --- Script 1 Function ---
def extract_data_for_review(model, file_path: str, review_dir: str, target_label: str, page_num: int = 1):
    """
    Processes a single file (PDF/image), extracts data, and saves outputs for manual review.

    Args:
        model: The loaded PyTorch model object.
        file_path (str): Path to the input PDF or image.
        review_dir (str): Path to the folder where review files will be saved.
        target_label (str): The specific label to search for in the document.
        page_num (int): The page number to process for PDF files.

    Returns:
        bool: True if extraction was successful, False otherwise.
    """
    logging.info(f"Processing: {os.path.basename(file_path)}...")
    if not os.path.exists(file_path):
        logging.error(f"  - Error: File not found.")
        return False

    # Find the target section
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext == '.pdf':
        section_info = _find_section_in_pdf(model, file_path, target_label, page_num)
    elif file_ext in ['.png', '.jpg', '.jpeg', '.tiff', '.tif']:
        image = Image.open(file_path).convert("RGB")
        section_info = _find_section_in_image(model, image, target_label)
    else:
        logging.error(f"  - Error: Unsupported file type '{file_ext}'.")
        return False

    if not section_info:
        logging.warning(f"  - Could not find section for label '{target_label}'.")
        return False

    # OCR the found section and get the DataFrame and cropped image
    df, cropped_image = _ocr_and_extract(section_info)

    if df.empty or cropped_image is None:
        logging.error(f"  - OCR failed or found no data.")
        return False

    # Save the files for review
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    excel_path = os.path.join(review_dir, f"{base_name}.xlsx")
    image_path = os.path.join(review_dir, f"{base_name}_table.png")

    os.makedirs(review_dir, exist_ok=True)
    df.to_excel(excel_path, index=False, header=False)
    cropped_image.save(image_path)

    logging.info(f"  - ✅ Success! Review files saved to '{review_dir}'")
    return True


def finalize_cleaned_data(cleaned_excel_path: str, final_dir: str):
    """
    Converts a cleaned Excel file to a final JSON output by pairing
    Column A (codes) with Column B (dates). Features enhanced error logging.

    Args:
        cleaned_excel_path (str): Path to the manually cleaned Excel file.
        final_dir (str): Path to the folder where the final JSON will be saved.

    Returns:
        bool: True if finalization was successful, False otherwise.
    """
    # Get the filename at the start to use in all log messages
    base_name = os.path.basename(cleaned_excel_path)

    logging.info(f"--- Processing: '{base_name}' ---")

    if not os.path.exists(cleaned_excel_path):
        logging.error(f"  - ❌ FAILED: File not found at path '{cleaned_excel_path}'")
        return False

    try:
        df = pd.read_excel(cleaned_excel_path, header=None)
    except Exception as e:
        logging.error(f"  - ❌ FAILED '{base_name}': Could not read the Excel file. Error: {e}")
        return False

    # --- UPDATED ERROR MESSAGE ---
    if df.shape[1] < 2:
        logging.error(f"  - ❌ FAILED '{base_name}': The Excel sheet has fewer than two columns.")
        logging.error("      (Hint: Open the file and check that your data is in separate cells for Column A and B.)")
        return False
    # --- END OF UPDATE ---

    df = df.dropna(subset=[0, 1])
    keys = df[0].astype(str)

    try:
        values = pd.to_datetime(df[1], format='%m/%d/%Y', errors='coerce').dt.strftime('%m/%d/%Y')
    except Exception as e:
        # --- UPDATED ERROR MESSAGE ---
        logging.error(f"  - ❌ FAILED '{base_name}': Could not parse dates in Column B.")
        logging.error(f"      Please ensure all dates are in 'M/D/YYYY' format. Details: {e}")
        return False
        # --- END OF UPDATE ---

    json_output_dict = dict(zip(keys, values))

    # --- UPDATED ERROR MESSAGE ---
    if not json_output_dict:
        logging.error(f"  - ❌ FAILED '{base_name}': No valid Code/Date pairs were found after cleaning.")
        return False
    # --- END OF UPDATE ---

    json_path = os.path.join(final_dir, f"{os.path.splitext(base_name)[0]}.json")
    os.makedirs(final_dir, exist_ok=True)

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_output_dict, f, indent=4)

    logging.info(f"  - ✅ SUCCESS: '{base_name}' was processed and saved as JSON.")
    return True