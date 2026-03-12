#!/bin/bash
# substrate-iterate.sh — One-click substrate iteration (Mac/Linux)
#
# Usage:
#   ./substrate-iterate.sh
#   If there's a session capture on your clipboard, it gets ingested.
#   If not, it runs on existing captures.
#
# Make executable: chmod +x substrate-iterate.sh

ITER_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  ============================================"
echo "   SUBSTRATE ITERATION SYSTEM"
echo "  ============================================"
echo ""

# Check for clipboard content (Mac: pbpaste, Linux: xclip/xsel)
CLIP=""
if command -v pbpaste &> /dev/null; then
    CLIP="$(pbpaste 2>/dev/null)"
elif command -v xclip &> /dev/null; then
    CLIP="$(xclip -selection clipboard -o 2>/dev/null)"
elif command -v xsel &> /dev/null; then
    CLIP="$(xsel --clipboard 2>/dev/null)"
fi

# Check if clipboard looks like a session capture
if echo "$CLIP" | grep -qi -e "session capture" -e "Goal:" -e "Progress:" -e "Momentum:"; then
    echo "  Found session capture on clipboard. Ingesting..."
    echo ""
    echo "$CLIP" | python3 "$ITER_DIR/auto.py"
else
    echo "  No capture on clipboard. Running on existing captures..."
    echo ""
    python3 "$ITER_DIR/auto.py" --skip-ingest
fi

echo ""
read -p "  Press Enter to close..."
