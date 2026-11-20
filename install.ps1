# Diviso installer — Windows PowerShell. Requires Python 3.10+.
python --version
python -m pip install -e "$PSScriptRoot"
Write-Host "Installed. Try: diviso doctor; diviso run --provider mock 'hello'"
