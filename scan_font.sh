#!/bin/bash

set -e
set -u

if [[ "$#" -ne 2 ]]; then
  echo "Usage: $0 encoding ass_root_dir" >&2
  exit 1
fi

encoding="$1"
ass_root_dir="$(realpath "$2")"

cd "$(dirname "$0")"
rm -rf collected
./parse_ass.py "$encoding" "$ass_root_dir" | ./scan_font.py .
