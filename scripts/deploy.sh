#!/bin/bash

PI="${PI_HOST:-ar@raspberrypi.local}"
REMOTE_DIR="${REMOTE_DIR:-/home/ar/cta-transit-display}"

scp -r src/ scripts/ res/ .env pyproject.toml uv.lock "$PI:$REMOTE_DIR/"

echo "Restarting app on Pi..."
ssh "$PI" "pkill -f 'src/main.py'" 2>/dev/null
echo "Deploy complete. App will restart automatically via lwrespawn."