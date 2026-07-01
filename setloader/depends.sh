#!/bin/sh
pip install -r requirements.txt && sudo apt-get update && sudo apt-get install -y poppler-utils tesseract-ocr ocrmypdf jq zip

sudo apt-get install python3-openai python3-fastapi python3-watchfiles
sudo apt install uvicorn
