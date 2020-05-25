#!/bin/bash

set -e
set -u

encoding="$1"
ass_root_dir="$(realpath "$2")"

cd "$(dirname "$0")"
rm -rf collected
./parse_ass.py "$encoding" "$ass_root_dir" | ./scan_font.py .
