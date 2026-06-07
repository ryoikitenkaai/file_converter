#!/usr/bin/env bash
# installs conv + nautilus scripts
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAUTILUS_SCRIPTS="$HOME/.local/share/nautilus/scripts"
NEMO_SCRIPTS="$HOME/.local/share/nemo/scripts"

echo "installing conv..."
sudo cp "$SCRIPT_DIR/conv.py" /usr/local/bin/conv
sudo chmod +x /usr/local/bin/conv

echo "installing nautilus scripts..."
mkdir -p "$NAUTILUS_SCRIPTS"
cp "$SCRIPT_DIR/Convert File" "$NAUTILUS_SCRIPTS/Convert File"
cp "$SCRIPT_DIR/Merge to PDF" "$NAUTILUS_SCRIPTS/Merge to PDF"
chmod +x "$NAUTILUS_SCRIPTS/Convert File"
chmod +x "$NAUTILUS_SCRIPTS/Merge to PDF"

if command -v nemo &>/dev/null; then
    echo "nemo detected, installing there too..."
    mkdir -p "$NEMO_SCRIPTS"
    cp "$SCRIPT_DIR/Convert File" "$NEMO_SCRIPTS/Convert File"
    cp "$SCRIPT_DIR/Merge to PDF" "$NEMO_SCRIPTS/Merge to PDF"
    chmod +x "$NEMO_SCRIPTS/Convert File"
    chmod +x "$NEMO_SCRIPTS/Merge to PDF"
fi

echo ""
echo "done. right-click any file → Scripts → Convert File"
echo ""
echo "if scripts don't appear, restart nautilus:"
echo "  nautilus -q; nautilus &"
