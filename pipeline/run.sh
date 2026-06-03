#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# VisionRetail AI — Detection Pipeline Runner
#
# Runs the YOLO → ByteTrack → OSNet → Event pipeline on one or more CCTV clips
# and ingests the resulting events into the running FastAPI backend.
#
# Usage:
#   ./pipeline/run.sh                          # process all clips in data/videos/
#   ./pipeline/run.sh --video path/to/clip.mp4 # process a single clip
#   ./pipeline/run.sh --dry-run                # write events.jsonl, skip ingest
#
# Prerequisites:
#   - Python 3.11+ with pipeline dependencies installed (pip install -r backend/requirements.txt)
#   - A running API (docker compose up -d) or local uvicorn
#   - A store_layout.json at data/store_layout.json (or override with --layout)
#
# Output:
#   - events.jsonl          — all generated events in the required schema
#   - Ingested batches sent to POST /events/ingest on the running API
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
STORE_ID="${STORE_ID:-STORE_BLR_002}"
LAYOUT="${LAYOUT:-datasets/raw/store_layout.json}"
API_URL="${API_URL:-http://localhost:8000}"
OUTPUT="${OUTPUT:-events.jsonl}"
YOLO_MODEL="${YOLO_MODEL:-yolov8m.pt}"
DRY_RUN=false
SINGLE_VIDEO=""

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --video)    SINGLE_VIDEO="$2"; shift 2 ;;
        --store)    STORE_ID="$2";     shift 2 ;;
        --layout)   LAYOUT="$2";       shift 2 ;;
        --output)   OUTPUT="$2";       shift 2 ;;
        --api-url)  API_URL="$2";      shift 2 ;;
        --dry-run)  DRY_RUN=true;      shift   ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Ensure output file is clean ───────────────────────────────────────────────
> "$OUTPUT"
echo "[run.sh] Output: $OUTPUT | Store: $STORE_ID | API: $API_URL"

# ── Camera map: camera_id → video file ───────────────────────────────────────
declare -A CAMERA_MAP=(
    ["CAM_01"]="datasets/raw/CCTV Footage/CAM 1.mp4"
    ["CAM_02"]="datasets/raw/CCTV Footage/CAM 2.mp4"
    ["CAM_03"]="datasets/raw/CCTV Footage/CAM 3.mp4"
    ["CAM_04"]="datasets/raw/CCTV Footage/CAM 4.mp4"
    ["CAM_05"]="datasets/raw/CCTV Footage/CAM 5.mp4"
)

run_processor() {
    local camera_id="$1"
    local video_path="$2"
    local tmp_output="${OUTPUT%.jsonl}_${camera_id}.jsonl"

    echo "[run.sh] Processing camera=$camera_id video=$video_path"

    python -m pipeline.video_processor \
        --video      "$video_path"  \
        --store      "$STORE_ID"    \
        --camera     "$camera_id"   \
        --layout     "$LAYOUT"      \
        --output     "$tmp_output"  \
        --api-url    "$([ "$DRY_RUN" = true ] && echo "" || echo "$API_URL")"

    # Merge into combined output
    cat "$tmp_output" >> "$OUTPUT"
    echo "[run.sh] ✓ $camera_id: $(wc -l < "$tmp_output") events → $tmp_output"
}

# ── Run ───────────────────────────────────────────────────────────────────────
if [[ -n "$SINGLE_VIDEO" ]]; then
    run_processor "CAM_01" "$SINGLE_VIDEO"
else
    for camera_id in "${!CAMERA_MAP[@]}"; do
        video_path="${CAMERA_MAP[$camera_id]}"
        if [[ -f "$video_path" ]]; then
            run_processor "$camera_id" "$video_path"
        else
            echo "[run.sh] ⚠ Skipping $camera_id — $video_path not found"
        fi
    done
fi

TOTAL=$(wc -l < "$OUTPUT")
echo ""
echo "[run.sh] Pipeline complete."
echo "[run.sh] Total events generated: $TOTAL"
echo "[run.sh] Output written to: $OUTPUT"

if [[ "$DRY_RUN" = true ]]; then
    echo "[run.sh] DRY RUN — skipped API ingestion."
    echo "[run.sh] To ingest manually:"
    echo "         python -c \""
    echo "           import json, httpx"
    echo "           events = [json.loads(l) for l in open('$OUTPUT')]"
    echo "           for i in range(0, len(events), 500):"
    echo "             batch = events[i:i+500]"
    echo "             r = httpx.post('$API_URL/events/ingest', json={'events': batch})"
    echo "             print(r.json())"
    echo "         \""
fi
