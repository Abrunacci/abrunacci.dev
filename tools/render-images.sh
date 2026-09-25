#!/usr/bin/env bash
# Renders the share image and the touch icon from the HTML templates in this
# directory into public/. Needs a Chromium or Chrome binary:
#   CHROME=/path/to/chrome tools/render-images.sh
set -euo pipefail

cd "$(dirname "$0")/.."
chrome="${CHROME:-chromium}"

render() {
  local src="$1" out="$2" size="$3"
  rm -f "$out"
  # Chrome logs harmless GPU and D-Bus noise to stderr; a missing output file is the real failure.
  "$chrome" --headless --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --window-size="$size" --virtual-time-budget=3000 --screenshot="$out" "file://$PWD/tools/$src" >/dev/null 2>&1
  if [[ ! -s "$out" ]]; then
    echo "failed to render $out" >&2
    exit 1
  fi
  echo "wrote $out"
}

render og-image.html public/og-image.png 1200,630
render apple-touch-icon.html public/apple-touch-icon.png 180,180
