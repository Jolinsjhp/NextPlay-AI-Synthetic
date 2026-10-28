#!/bin/sh
set -eu
export TOUCHLINE_HOST=0.0.0.0
export TOUCHLINE_PORT=8000
export NEXTPLAY_STATE_DIR="${NEXTPLAY_STATE_DIR:-/home/nextplay}"
if [ -z "${NEXTPLAY_PUBLIC_ORIGIN:-}" ]; then
  : "${WEBSITE_HOSTNAME:?App Service hostname is required}"
  export NEXTPLAY_PUBLIC_ORIGIN="https://${WEBSITE_HOSTNAME}"
fi
mkdir -p "$NEXTPLAY_STATE_DIR"
chmod 700 "$NEXTPLAY_STATE_DIR"
exec python3 server.py
