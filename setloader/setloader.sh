#!/usr/bin/env bash
set -euo pipefail
PDF="${1:?usage: pdf2container.sh <pdf> [set-name] [datafile]}"
SET_NAME="${2:-one}"
DATAFILE="${3:-dataFile.txt}"

BASE="${PDF%.*}"
RAW="$BASE.raw.txt"
VER="$BASE.verified.txt"
OUT="$BASE.container.json"
BIN="./bin"
ETC="./etc"
SRC="./src"
PACK="./pack"

# 1) PDF → titles (tuned for numeric-only too)
python $SRC/pdf_to_titles.py --in "$PDF" --out "$RAW" --page 1 --psm 7 --whitelist 0123456789

# 2) Map/normalize against your catalog
python $SRC/titles_verify.py --in "$RAW" --catalog etc/catalog.txt --mapper etc/title_mapper.json --out "$VER"

# 3) Build single-line container JSON + sets[] from verified order
python $SRC/extract_songs.py --verified "$VER"  --datafile $ETC/fullcat.txt  --out $PACK/dataFile.txt  --format container   --make-set "$SET_NAME"
echo "Wrote $OUT"
./pack.sh "$SET_NAME"


# Define the destination path in iCloud Drive
#icloud_path="/Users/brian/Library/Mobile Documents/com~apple~CloudDocs/sets"
icloud_path="/media/psf/Projects/dev/setloader/output"

# Copy the mix to iCloud Drive
echo "Copying file to iCloud Drive..." >> /tmp/loaderlog.txt
cp "$PACK/$SET_NAME.sbp" "$icloud_path"

# Define the message to send
msg="$SET_NAME is ready"

# Send the text message via AppleScript
#osascript -e "tell application \"Messages\" to send \"$msg\" to buddy \"brian@schaffner.net\""
#osascript -e "tell application \"Messages\" to send \"https://www.icloud.com/iclouddrive/002iPP0fTctX82hOB7pXjaHUQ#sets˚\" to buddy \"brian@schaffner.net\""


