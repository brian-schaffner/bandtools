#!/bin/sh

curl -sS -X POST http://localhost:8000/run \
  -H "X-Secret: change-me" \
  -F "name=Party" \
  -F "whateverKeyName=@party.pdf;type=application/pdf" | jq .