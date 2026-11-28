#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
root="$(pwd -P)"
exe="$root/MarVoiReflex.app/Contents/MacOS/MarVoiReflex"
if [[ ! -x "$exe" ]]; then echo "請完整解壓縮 macOS 安裝資料夾。"; exit 1; fi
actual="$(uname -m)"
case "$actual" in arm64|x86_64) ;; *) echo "不支援的處理器"; exit 1;; esac
if ! /usr/bin/lipo -archs "$exe" | /usr/bin/grep -qw "$actual"; then echo "請下載對應的 Mac 架構版本。"; exit 1; fi
/usr/bin/codesign --verify --deep --strict "$root/MarVoiReflex.app"
g="$root/assets/gemma4-e2b"
mkdir -p "$g"
if [[ -L "$g" ]]; then echo "模型資料夾不可為連結。"; exit 1; fi
fetch(){
 local name="$1" expected="$2" bytes="$3" path="$g/$1"
 if [[ -L "$path" || -L "$path.partial" ]]; then echo "模型檔案不可為連結。"; return 1; fi
 if [[ -f "$path" ]] && [[ "$(/usr/bin/shasum -a 256 "$path" | cut -d ' ' -f1)" == "$expected" ]]; then echo "已驗證：$name"; return; fi
 if [[ -e "$path" ]]; then echo "模型已存在但校驗失敗，請移至其他位置再重試。"; return 1; fi
 if [[ -f "$path.partial" ]] && [[ "$(/usr/bin/stat -f %z "$path.partial")" == "$bytes" ]]; then
   if [[ "$(/usr/bin/shasum -a 256 "$path.partial" | cut -d ' ' -f1)" != "$expected" ]]; then echo "暫存模型校驗失敗，請移除該 .partial 檔後重試。"; return 1; fi
 else
   /usr/bin/curl -fL --retry 3 --connect-timeout 30 -C - -o "$path.partial" "https://huggingface.co/google/gemma-4-E2B-it-qat-q4_0-gguf/resolve/main/$name"
 fi
 [[ "$(/usr/bin/stat -f %z "$path.partial")" == "$bytes" ]]
 [[ "$(/usr/bin/shasum -a 256 "$path.partial" | cut -d ' ' -f1)" == "$expected" ]]
 mv "$path.partial" "$path"
}
fetch gemma-4-E2B_q4_0-it.gguf fa401b55b07ee70a54c6dae3903c783a6e65064312529ea57175cb5f8dec6634 3349516256
fetch gemma-4-E2B-it-mmproj.gguf 021059cce659fe7f9170d5599761d7bbaf644b798dab9503aca30dc43e6beb14 986833664
echo "已完成模型校驗。若系統要求，請依 macOS 權限提示操作。"
exec "$exe"
