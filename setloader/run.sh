#!/usr/bin/env bash
set -euo pipefail

# Provide sensible defaults while allowing callers to override.
: "${SECRET:=change-me}"
: "${RUN_EXTRA_FLAGS:=}"
: "${SMTP_USER:=}"
: "${SMTP_PASS:=}"
: "${FROM_NAME:=Set Loader}"
: "${EMAIL_FALLBACK_TO:=}"

IFS=$'\n\t'

PY=${PY:-}
if [[ -z "$PY" ]]; then
  if [[ -n "${VIRTUAL_ENV:-}" && -x "$VIRTUAL_ENV/bin/python" ]]; then
    PY="$VIRTUAL_ENV/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
  else
    echo "python3 not found" >&2
    exit 1
  fi
fi

export LANG=C.UTF-8
export LC_ALL=C.UTF-8

USE_AI=0
ARGS=()
for arg in "$@"; do
  if [[ "$arg" == "--ai" ]]; then
    USE_AI=1
  else
    ARGS+=("$arg")
  fi
done
set -- "${ARGS[@]}"

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <pdf> [set-name]" >&2
  exit 1
fi

PDF="$1"
SET_NAME="${2:-one}"
ROOT="$(pwd)"
WORK="$ROOT/work"
PACK="$ROOT/pack"
mkdir -p "$WORK" "$PACK"

RAW="$PACK/raw_titles.txt"
VER="$PACK/verified.txt"
DATAFILE="$PACK/dataFile.txt"
HASHFILE="$PACK/dataFile.hash"

if [[ "$USE_AI" == "1" ]]; then
  echo "# using AI extractor"
  "$PY" src/ai_reader.py "$PDF" "$RAW"
  "$PY" src/titles_verify.py \
    --in "$RAW" \
    --catalog "$ROOT/etc/catalog.txt" \
    --mapper "$ROOT/etc/title_mapper.json" \
    --out "$VER"
  "$PY" src/extract_songs.py \
    --verified "$VER" \
    --datafile "$ROOT/etc/fullcat.txt" \
    --out "$DATAFILE" \
    --format container \
    --make-set "$SET_NAME"
else
  echo "# using legacy extractor"
  "$PY" src/pdf_to_titles.py --in "$PDF" --out "$RAW"
  "$PY" src/titles_verify.py \
    --in "$RAW" \
    --catalog "$ROOT/etc/catalog.txt" \
    --mapper "$ROOT/etc/title_mapper.json" \
    --out "$VER"
  "$PY" src/extract_songs.py \
    --verified "$VER" \
    --datafile "$ROOT/etc/fullcat.txt" \
    --out "$DATAFILE" \
    --format container \
    --make-set "$SET_NAME"
fi

md5sum "$DATAFILE" | awk '{printf $1}' > "$HASHFILE"
(
  cd "$PACK"
  zip -q "$SET_NAME.sbp" "$(basename "$DATAFILE")" "$(basename "$HASHFILE")"
)

ARTIFACT="$PACK/$SET_NAME.sbp"
echo "Wrote: $ARTIFACT"
echo "ARTIFACT=$ARTIFACT"
