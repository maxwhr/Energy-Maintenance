#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${BACKEND_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$BACKEND_DIR/.." && pwd)}"
FRONTEND_SOURCE_DIR="${FRONTEND_SOURCE_DIR:-$PROJECT_ROOT/frontend}"
DIST_DIR="$FRONTEND_SOURCE_DIR/dist"
STATIC_ROOT="$BACKEND_DIR/static"
TARGET_DIR="$STATIC_ROOT/frontend"

if [ ! -d "$FRONTEND_SOURCE_DIR" ]; then
  echo "Frontend source directory does not exist: $FRONTEND_SOURCE_DIR" >&2
  exit 1
fi

cd "$FRONTEND_SOURCE_DIR"
npm install
npm run build

if [ ! -f "$DIST_DIR/index.html" ]; then
  echo "Frontend build output is missing index.html: $DIST_DIR" >&2
  exit 1
fi

mkdir -p "$STATIC_ROOT"
rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"
cp -R "$DIST_DIR"/. "$TARGET_DIR"/

FILE_COUNT="$(find "$TARGET_DIR" -type f | wc -l | tr -d ' ')"
echo "Frontend installed to: $TARGET_DIR"
echo "Copied files: $FILE_COUNT"
echo "Index: $TARGET_DIR/index.html"
