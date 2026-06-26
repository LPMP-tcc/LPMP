#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing system dependencies..."
sudo apt install -y python3-pip vlc

echo "Creating virtual environment..."
python3 -m venv "$REPO_DIR/.venv"
source "$REPO_DIR/.venv/bin/activate"

echo "Installing Python dependencies..."
pip install pyside6 python-vlc requests mutagen rapidfuzz

echo "Writing go-librespot config..."
mkdir -p "$HOME/.config/go-librespot"
cat > "$HOME/.config/go-librespot/config.yml" <<'EOF'
zeroconf_enabled: false
credentials:
  type: interactive

server:
  enabled: true
  address: localhost
  port: 24879
log_level: debug
bitrate: 320
disable_autoplay: true
EOF

echo ""
echo "Done. To run the app:"
echo "  source $REPO_DIR/.venv/bin/activate"
echo "  python $REPO_DIR/main.py"
echo ""
echo "Remember to download go-librespot and run it separately before launching the app."
