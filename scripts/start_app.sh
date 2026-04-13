#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
"$HOME/.local/bin/uv" run --project "$PROJECT_DIR" "$PROJECT_DIR/src/main.py" >"$HOME/train_script.log" 2>&1
