#!/usr/bin/env bash
# Deploy Polly AI to a Hugging Face Space.
#
# Spaces are git repositories. This creates the Space if it does not exist,
# assembles a Space tree from the app source (the Space needs the Dockerfile and
# README front-matter at *its* root), and pushes it.
#
# Requires: HF_TOKEN with write scope, from https://huggingface.co/settings/tokens
#
#   HF_TOKEN=hf_... ./deploy/huggingface/deploy.sh <hf-username> [space-name]

set -euo pipefail

USERNAME="${1:?usage: deploy.sh <hf-username> [space-name]}"
SPACE="${2:-polly-ai}"
: "${HF_TOKEN:?HF_TOKEN is not set — create one at https://huggingface.co/settings/tokens}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "==> Checking the token"
WHOAMI=$(curl -sS -H "Authorization: Bearer ${HF_TOKEN}" https://huggingface.co/api/whoami-v2)
if ! grep -q '"name"' <<<"$WHOAMI"; then
  echo "    Token rejected by Hugging Face. Create a *write* token at" >&2
  echo "    https://huggingface.co/settings/tokens" >&2
  exit 1
fi
echo "    authenticated"

echo "==> Ensuring the Space exists"
# Idempotent: an existing Space returns 409, which is success for our purposes.
CREATE=$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
  -H "Authorization: Bearer ${HF_TOKEN}" -H "Content-Type: application/json" \
  -d "{\"type\":\"space\",\"name\":\"${SPACE}\",\"sdk\":\"docker\",\"private\":false}" \
  https://huggingface.co/api/repos/create)
case "$CREATE" in
  200|201) echo "    created ${USERNAME}/${SPACE}" ;;
  409)     echo "    already exists — updating it" ;;
  *)       echo "    could not create the Space (HTTP ${CREATE})." >&2
           echo "    Check the token has write scope, then retry." >&2
           exit 1 ;;
esac
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
