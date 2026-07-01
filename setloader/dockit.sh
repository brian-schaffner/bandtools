#!/bin/sh

#docker run --rm -p 8000:8000 \

docker run --rm -it \
  -p 8000:8000 \
  -v "$PWD:/setloader" \
  -e SECRET='change-me' \
  -e SMTP_USER='brian@schaffner.net' \
  -e SMTP_PASS='your_app_password' \
  -e FROM_NAME='Set Loader' \
  -e EMAIL_FALLBACK_TO='brian@schaffner.net' \
  -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
  -e RUN_EXTRA_FLAGS='--ai' \
  --name setloader \
  setloader:latest

