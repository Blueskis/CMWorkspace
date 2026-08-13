#!/usr/bin/env bash
# Generate a synthetic "ERP demo" recording for exercising the pipeline.
#
#   ./make_fixture.sh [output_dir]
#
# Produces inputs/demo.mp4 — 70 seconds, seven flat-colour "screens" with hard cuts between
# them, matching the scene boundaries in capture_map.json. The hard cuts are the point: they
# give ffmpeg's scene detection real boundaries to find, so ingest_capture.py can be tested
# without a real screen recording and without anyone's client system.
#
# Nothing here resembles a real system and no data is real. That is deliberate — the same
# fictional-input discipline as examples/acme-erp/.
#
# Requires ffmpeg. Everything downstream of Stage 1 can be tested without this script, using
# the capture_map.json and video_script.json that ship alongside it.

set -euo pipefail

OUT_DIR="${1:-inputs}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

command -v ffmpeg >/dev/null 2>&1 || {
    echo "ffmpeg not found — see skills/training-video-generator/scripts/preflight.py" >&2
    exit 1
}

# drawtext needs a font. Prefer an explicit file; fall back to fontconfig by name.
FONT_ARG=""
for candidate in \
    /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf \
    /usr/share/fonts/dejavu/DejaVuSans.ttf \
    /System/Library/Fonts/Supplemental/Arial.ttf \
    /usr/share/fonts/TTF/DejaVuSans.ttf; do
    if [ -f "$candidate" ]; then
        FONT_ARG="fontfile=${candidate}:"
        break
    fi
done
if [ -z "$FONT_ARG" ]; then
    FONT_ARG="font=sans:"
    echo "note: no font file found, falling back to fontconfig 'sans'" >&2
fi

# scene_id | seconds | background | headline | subtitle
SCENES=(
    "S01|12|0x1F3A5F|Fiori Launchpad|Procurement"
    "S02|15|0x2E6DA4|Create Purchase Requisition|Item Details"
    "S03|4|0x8A5A2B|My Requisitions|(opened in error)"
    "S04|10|0x2E6DA4|Create Purchase Requisition|Account Assignment"
    "S05|8|0x555555|Posting...|please wait"
    "S06|7|0x1E7A46|Saved|Pending approval"
    "S07|14|0x1E7A46|Requisition 4500001234|Created successfully"
)

mkdir -p "$OUT_DIR"
LIST="$WORK/list.txt"
: >"$LIST"

echo "Generating ${#SCENES[@]} scenes..."
index=0
for row in "${SCENES[@]}"; do
    IFS='|' read -r id secs colour headline subtitle <<<"$row"
    index=$((index + 1))
    segment="$WORK/seg_${index}.mp4"

    ffmpeg -hide_banner -loglevel error -y \
        -f lavfi -i "color=c=${colour}:s=1920x1080:r=30:d=${secs}" \
        -vf "drawtext=${FONT_ARG}text='${headline}':fontcolor=white:fontsize=72:x=(w-text_w)/2:y=(h-text_h)/2-60,\
drawtext=${FONT_ARG}text='${subtitle}':fontcolor=0xCCCCCC:fontsize=44:x=(w-text_w)/2:y=(h-text_h)/2+60,\
drawtext=${FONT_ARG}text='${id}':fontcolor=0x888888:fontsize=32:x=48:y=48" \
        -c:v libx264 -preset veryfast -pix_fmt yuv420p \
        "$segment"

    echo "file '$segment'" >>"$LIST"
    printf '  %s  %2ss  %s\n' "$id" "$secs" "$headline"
done

ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$LIST" -c copy "$OUT_DIR/demo.mp4"

echo
echo "Wrote $OUT_DIR/demo.mp4 (70s)"
echo
echo "Next:"
echo "  python ../../skills/training-video-generator/scripts/ingest_capture.py \\"
echo "      $OUT_DIR/demo.mp4 -o capture_map.json --frames frames/"
echo
echo "Compare the result against the capture_map.json in this folder — the boundaries"
echo "should land at 12, 27, 31, 41, 49 and 56 seconds."
