#!/bin/sh
# ローカル確認用：ビルドして site/ を一時フォルダへ複製し、そこから配信する
# （iCloud 配下はアプリのサンドボックスから読めないことがあるため）
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
# Python の探し方：環境変数 PYTHON → 本体チェックアウトの .venv → ワークツリー直下の .venv → python3
if [ -z "$PYTHON" ]; then
  for cand in "$HERE/../../../../../.venv/bin/python" "$HERE/../../.venv/bin/python" "$HOME/Library/Mobile Documents/com~apple~CloudDocs/healthcare-development/.venv/bin/python"; do
    if [ -x "$cand" ]; then PYTHON="$cand"; break; fi
  done
fi
PY="${PYTHON:-python3}"
echo "python: $PY ($("$PY" --version 2>&1))"
"$PY" "$HERE/build.py"
MIRROR="${PREVIEW_DIR:-/tmp/shibagaki-test-site}"   # .claude/launch.json もこの場所を配信する
mkdir -p "$MIRROR"
rsync -a --delete "$HERE/site/" "$MIRROR/"
echo "serving $MIRROR at http://127.0.0.1:${PORT:-8787}/"
exec "$PY" -m http.server "${PORT:-8787}" --bind 127.0.0.1 --directory "$MIRROR"
