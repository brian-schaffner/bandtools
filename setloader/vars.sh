#!/bin/sh
# Local dev env — copy to .env or source after filling in values. Do not commit secrets.

export SECRET='change-me'
export SMTP_USER=''
export SMTP_PASS=''
export FROM_NAME='Set Loader'
export EMAIL_FALLBACK_TO=''
export OPENAI_API_KEY=''
export RUN_EXTRA_FLAGS='--ai'
