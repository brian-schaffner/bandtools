# src/ai_ocr.py
from rapidocr_onnxruntime import RapidOCR
from pathlib import Path
from PIL import Image
import json

def ocr_image_paths_to_lines(image_paths):
    ocr = RapidOCR()  # CPU inference via onnxruntime
    lines = []
    for p in image_paths:
        img = Image.open(p).convert("RGB")
        res, _ = ocr(img)
        # res is a list: [ [ [x1,y1]...[x4,y4], "text", score ], ... ]
        for _, text, score in (res or []):
            if text and score >= 0.3:
                lines.append(text)
    return lines

if __name__ == "__main__":
    # Example: python src/ai_ocr.py work/page_*.png > work/ai_lines.txt
    import sys, glob
    paths = sorted(glob.glob(sys.argv[1])) if len(sys.argv) > 1 else []
    for line in ocr_image_paths_to_lines(paths):
        print(line)