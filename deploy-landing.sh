#!/usr/bin/env bash
#
# Publish the landing page to Cloudflare Pages.
#
# Only the landing page goes up, as the site root. The app itself needs a Python
# backend with TensorFlow, OpenCV and ffmpeg, none of which can run on Pages, so
# deploying it would put a permanently broken app behind the link. What a
# portfolio visitor wants is the description and the recording, which are static.
#
#   ./deploy-landing.sh            build and deploy
#   ./deploy-landing.sh --build    build only, no deploy
#
# First time: npx wrangler login
set -euo pipefail
cd "$(dirname "$0")"

OUT=landing-dist
PROJECT=${CF_PROJECT:-polly-ai}
SRC=frontend/public

rm -rf "$OUT"
mkdir -p "$OUT"

# landing.html becomes index.html so the bare domain serves it.
cp "$SRC/landing.html" "$OUT/index.html"
cp "$SRC/landing.js"   "$OUT/"
cp "$SRC/polly-mark.svg" "$OUT/"

if [ -f "$SRC/demo.mp4" ]; then
    cp "$SRC/demo.mp4" "$OUT/"
else
    echo "warning: $SRC/demo.mp4 not found. The page will deploy with its" >&2
    echo "         placeholder instead of the video." >&2
fi

# Headers for this bundle rather than the app's: the landing page talks to
# nothing but its own origin, so connect-src can be 'self', and it runs no WASM,
# so none of the MediaPipe allowances apply.
cat > "$OUT/_headers" <<'HEADERS'
/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: DENY
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'

/demo.mp4
  Cache-Control: public, max-age=604800

/polly-mark.svg
  Cache-Control: public, max-age=604800
HEADERS

echo "Built $OUT:"
du -sh "$OUT" | sed 's/^/  /'
ls -la "$OUT" | tail -n +2 | awk '{printf "  %8s  %s\n", $5, $9}'

# Pages rejects any single file over 25 MB, so say so here rather than after an
# upload that fails.
if [ -f "$OUT/demo.mp4" ]; then
    bytes=$(wc -c < "$OUT/demo.mp4")
    if [ "$bytes" -gt 26214400 ]; then
        echo >&2
        echo "error: demo.mp4 is $((bytes / 1048576)) MB. Cloudflare Pages rejects" >&2
        echo "       files over 25 MB. Re-encode it smaller, or host it elsewhere." >&2
        exit 1
    fi
fi

[ "${1:-}" = "--build" ] && { echo; echo "Built only. Deploy with: npx wrangler pages deploy $OUT --project-name $PROJECT"; exit 0; }

echo
echo "Deploying to Cloudflare Pages project '$PROJECT'..."
npx wrangler pages deploy "$OUT" --project-name "$PROJECT" --commit-dirty=true
