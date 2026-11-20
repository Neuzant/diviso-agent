#!/bin/sh
# Diviso installer — Linux / macOS. Requires Python 3.10+.
set -e
python3 --version
python3 -m pip install --user -e "$(dirname "$0")"
echo "Installed. Try: diviso doctor && diviso run --provider mock \"hello\""
