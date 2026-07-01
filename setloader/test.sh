#!/bin/sh

curl -sS -X POST https://glowing-barnacle-jjrj759jjr9xcq4v-8000.app.github.dev/run \
  -H "X-Secret: change-me" \
  -F "name=Bonnie" \
  -F "whateverKeyName=@bs.pdf;type=application/pdf" | jq .