#!/usr/local/bin/python3
"""
Reusable library for extracting songs from setlist files using AI prompts.
Supports PDF, plain text, and image uploads (JPEG/PNG/WebP/GIF).
"""

import base64
import json
import mimetypes
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from openai import OpenAI
import PyPDF2

SUPPORTED_EXTENSIONS = {'.pdf', '.txt', '.jpg', '.jpeg', '.png', '.webp', '.gif'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


class PDFExtractionError(Exception):
    """Custom exception for file extraction errors."""
    pass


class UnsupportedFileTypeError(Exception):
    """Raised when the uploaded file type cannot be processed."""
    pass


def _read_header(path: Path, n: int = 12) -> bytes:
    with open(path, 'rb') as f:
        return f.read(n)


def detect_file_type(path: Path) -> str:
    """
    Detect file type by magic bytes, falling back to extension.
    Returns one of: 'pdf', 'txt', 'image'.
    """
    header = _read_header(path)
    ext = path.suffix.lower()

    if header.startswith(b'%PDF'):
        return 'pdf'
    if header.startswith(b'\xff\xd8\xff'):
        return 'image'
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image'
    if header.startswith(b'GIF87a') or header.startswith(b'GIF89a'):
        return 'image'
    if len(header) >= 12 and header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'image'

    if ext == '.txt':
        return 'txt'
    if ext == '.pdf':
        return 'pdf'
    if ext in IMAGE_EXTENSIONS:
        return 'image'

    raise UnsupportedFileTypeError(
        f"Unsupported file type '{ext or '(none)'}'. "
        f"Supported formats: PDF, TXT, JPEG, PNG, WebP, GIF."
    )


def _image_mime_type(path: Path) -> str:
    header = _read_header(path)
    if header.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if header.startswith(b'GIF87a') or header.startswith(b'GIF89a'):
        return 'image/gif'
    if len(header) >= 12 and header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'image/webp'
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or 'image/jpeg'


class PDFExtractor:
    """
    A reusable library for extracting songs from setlist files using AI prompts.
    """

    def __init__(self):
        """Initialize the PDF extractor."""
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from PDF file."""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            raise PDFExtractionError(f"Error reading PDF {pdf_path}: {e}")

    def extract_text_from_txt(self, txt_path: Path) -> str:
        """Read plain text file."""
        try:
            return txt_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            return txt_path.read_text(encoding='latin-1')
        except Exception as e:
            raise PDFExtractionError(f"Error reading text file {txt_path}: {e}")

    def extract_text_from_image(self, image_path: Path, model: str = "gpt-4o") -> str:
        """Use OpenAI vision to OCR text from a setlist image."""
        try:
            mime = _image_mime_type(image_path)
            with open(image_path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')

            response = self.client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract all text from this setlist image. "
                                "Return the raw text exactly as it appears, preserving "
                                "line breaks, set headers, song titles, keys, and numbering."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        },
                    ],
                }],
                temperature=0.1,
            )
            text = response.choices[0].message.content or ""
            if not text.strip():
                raise PDFExtractionError("Vision OCR returned no text from image")
            return text
        except PDFExtractionError:
            raise
        except Exception as e:
            raise PDFExtractionError(f"Error extracting text from image {image_path}: {e}")

    def extract_text_from_file(self, file_path: Path, model: str = "gpt-4o") -> str:
        """Extract text from a setlist file (PDF, TXT, or image)."""
        file_type = detect_file_type(file_path)
        if file_type == 'pdf':
            return self.extract_text_from_pdf(file_path)
        if file_type == 'txt':
            return self.extract_text_from_txt(file_path)
        if file_type == 'image':
            return self.extract_text_from_image(file_path, model=model)
        raise UnsupportedFileTypeError(f"Unsupported file type for {file_path}")

    def load_prompt(self, prompt_path: Path) -> str:
        """Load the AI prompt from file."""
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise PDFExtractionError(f"Error loading prompt {prompt_path}: {e}")

    def call_openai_api(self, text: str, prompt: str, model: str = "gpt-4o", temperature: float = 0.1) -> str:
        """Call OpenAI API with the extracted text and prompt."""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            raise PDFExtractionError(f"Error calling OpenAI API: {e}")

    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse the JSON response from OpenAI, handling extra text."""
        try:
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx == -1 or end_idx == 0:
                raise PDFExtractionError("No JSON found in OpenAI response")

            json_str = response[start_idx:end_idx]
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise PDFExtractionError(f"Error parsing JSON response: {e}")
        except Exception as e:
            raise PDFExtractionError(f"Error processing OpenAI response: {e}")

    def extract_songs(self, file_path: Path, prompt_path: Path, model: str = "gpt-4o", temperature: float = 0.1, progress_callback=None) -> Dict[str, Any]:
        """
        Extract songs from a setlist file using AI.

        Args:
            file_path: Path to the setlist file (PDF, TXT, or image)
            prompt_path: Path to the AI prompt file
            model: OpenAI model to use
            temperature: Temperature for response generation
            progress_callback: Optional callback function for progress updates

        Returns:
            Dictionary containing extracted song data
        """
        try:
            file_type = detect_file_type(file_path)
            type_label = {'pdf': 'PDF', 'txt': 'text', 'image': 'image'}[file_type]

            if progress_callback:
                progress_callback(f"📄 Reading {type_label} file...")
            text = self.extract_text_from_file(file_path, model=model)
            if progress_callback:
                progress_callback(f"✅ File read successfully ({len(text)} characters)")

            if progress_callback:
                progress_callback("📝 Loading AI prompt...")
            prompt = self.load_prompt(prompt_path)
            if progress_callback:
                progress_callback("✅ Prompt loaded successfully")

            if progress_callback:
                progress_callback("🔗 Connecting to OpenAI...")

            if progress_callback:
                progress_callback("📤 Submitting prompt to OpenAI...")
            response = self.call_openai_api(text, prompt, model, temperature)
            if progress_callback:
                progress_callback("✅ Received response from OpenAI")

            if progress_callback:
                progress_callback("🔍 Parsing AI response...")
            result = self.parse_json_response(response)
            if progress_callback:
                progress_callback("✅ JSON parsed successfully")

            return {
                "success": True,
                "data": result,
                "error": None
            }

        except UnsupportedFileTypeError:
            raise
        except PDFExtractionError as e:
            if progress_callback:
                progress_callback(f"❌ Error: {str(e)}")
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }
        except Exception as e:
            if progress_callback:
                progress_callback(f"❌ Unexpected error: {str(e)}")
            return {
                "success": False,
                "data": None,
                "error": f"Unexpected error during extraction: {e}"
            }

    def save_results(self, result: Dict[str, Any], output_path: Path) -> None:
        """Save the extraction results to a JSON file."""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise PDFExtractionError(f"Error saving results to {output_path}: {e}")

    def get_summary(self, result: Dict[str, Any]) -> str:
        """Generate a summary of the extraction results."""
        try:
            counts = result.get('counts', {})
            total = counts.get('total', 0)
            per_set = counts.get('per_set', {})
            extras = counts.get('extras', 0)

            summary_lines = []
            summary_lines.append(f"✅ Successfully extracted {total} songs")

            if per_set:
                for set_name, count in per_set.items():
                    summary_lines.append(f"  - {set_name}: {count} songs")

            if extras > 0:
                summary_lines.append(f"  - Extras: {extras} songs")

            return "\n".join(summary_lines)

        except Exception as e:
            return f"Summary generation failed: {e}"
