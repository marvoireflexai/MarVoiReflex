#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
root="$(pwd -P)"
exe="$root/MarVoiReflex.app/Contents/MacOS/MarVoiReflex"
[[ -x "$exe" && -f "$root/assets/gemma4-e2b/gemma-4-E2B_q4_0-it.gguf" && -f "$root/assets/gemma4-e2b/gemma-4-E2B-it-mmproj.gguf" ]] || { echo "請先完成安裝。"; exit 1; }
if /usr/bin/pgrep -x MarVoiReflex >/dev/null; then echo "請先關閉現有 MarVoiReflex。"; exit 1; fi
/usr/bin/codesign --verify --deep --strict "$root/MarVoiReflex.app"
exec "$exe" --presentation
