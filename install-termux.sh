#!/data/data/com.termux/files/usr/bin/sh
# Diviso installer — Android Termux.
set -e
pkg install -y python git || true
python -m pip install -e "$(dirname "$0")"
echo "Installed (lite profile recommended). Try: diviso doctor"
