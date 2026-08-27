#!/usr/bin/env bash
#
# Put MediaPipe's WASM runtime and models where the browser can fetch them.
#
# Tracking runs in the browser, not on the server: a round trip to Python for
# every frame put ~90 ms between a movement and its indicator, which reads as
# lag however fast the server itself is. The browser can only load the runtime
# over HTTP, so it has to sit under public/.
#
# None of it is committed -- the WASM comes from node_modules and the models
# from Google, both reproducibly.
set -euo pipefail
cd "$(dirname "$0")/.."

WASM_SRC=node_modules/@mediapipe/tasks-vision/wasm
DEST=public/mediapipe

if [ ! -d "$WASM_SRC" ]; then
    echo "MediaPipe not installed. Run: npm install" >&2
    exit 1
fi

mkdir -p "$DEST/wasm" "$DEST/models"

# Both variants: FilesetResolver picks the SIMD build where the browser supports
# it and falls back to the other, so shipping only one breaks older browsers.
cp "$WASM_SRC"/vision_wasm_internal.js "$WASM_SRC"/vision_wasm_internal.wasm "$DEST/wasm/"
cp "$WASM_SRC"/vision_wasm_nosimd_internal.js "$WASM_SRC"/vision_wasm_nosimd_internal.wasm "$DEST/wasm/"

fetch() {
    local url=$1 out=$2
    if [ -f "$out" ]; then echo "  have $(basename "$out")"; return; fi
    echo "  fetching $(basename "$out")"
    curl -sSLf -o "$out" "$url"
}

fetch "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task" \
      "$DEST/models/hand_landmarker.task"
fetch "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite" \
      "$DEST/models/blaze_face_short_range.tflite"

echo "MediaPipe staged in $DEST"
