#!/usr/bin/env bash
# Deploy Polly AI to a Hugging Face Space.
#
# Spaces are git repositories. This assembles a Space tree from the app source
# (the Space needs the Dockerfile and README front-matter at *its* root) and
# pushes it.
#
# Requires: HF_TOKEN with write scope, from https://huggingface.co/settings/tokens
#
#   HF_TOKEN=hf_... ./deploy/huggingface/deploy.sh <hf-username> [space-name]

set -euo pipefail

USERNAME="${1:?usage: deploy.sh <hf-username> [space-name]}"
SPACE="${2:-polly-ai}"
: "${HF_TOKEN:?HF_TOKEN is not set — create one at https://huggingface.co/settings/tokens}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "==> Assembling Space tree"
cp -R "$REPO_ROOT/backend" "$REPO_ROOT/frontend" "$WORK/"
cp "$REPO_ROOT/Dockerfile" "$REPO_ROOT/.dockerignore" "$WORK/"
cp "$REPO_ROOT/deploy/huggingface/README.md" "$WORK/README.md"

# Never ship local artefacts: virtualenvs, node_modules, databases, .env files.
rm -rf "$WORK/backend/venv" "$WORK/frontend/node_modules" "$WORK/frontend/dist"
find "$WORK" \( -name '*.db' -o -name '.env' -o -name '__pycache__' \) -exec rm -rf {} + 2>/dev/null || true

echo "==> Pushing to https://huggingface.co/spaces/$USERNAME/$SPACE"
cd "$WORK"
git init -q
git add -A
git -c user.email=deploy@local -c user.name=deploy commit -qm "Deploy Polly AI"
git push -q --force "https://oauth2:${HF_TOKEN}@huggingface.co/spaces/${USERNAME}/${SPACE}" HEAD:main

echo "==> Done. Build progress: https://huggingface.co/spaces/${USERNAME}/${SPACE}"
echo "    First build takes ~10 minutes (TensorFlow layer)."
