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
: "${HF_TOKEN:?HF_TOKEN is not set, create one at https://huggingface.co/settings/tokens}"

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
  409)     echo "    already exists, updating it" ;;
  402)     echo "    Hugging Face requires a PRO subscription to run a Docker" >&2
           echo "    Space on the free cpu-basic tier. Only static Spaces are" >&2
           echo "    free. See docs/SETUP.md for hosts that can run this image." >&2
           exit 1 ;;
  403)     echo "    Token lacks write access. Create one with the 'write' role" >&2
           echo "    at https://huggingface.co/settings/tokens" >&2
           exit 1 ;;
  *)       echo "    Could not create the Space (HTTP ${CREATE})." >&2
           exit 1 ;;
esac
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "==> Assembling Space tree"
# Export tracked files only. Copying the working tree and deleting artefacts
# afterwards inverts the safety: it ships anything the cleanup list forgot, and
# copies a ~200 MB node_modules just to remove it. git archive cannot emit an
# untracked file, so venvs, node_modules, *.db and .env are excluded by
# construction rather than by a list that has to stay complete.
git -C "$REPO_ROOT" archive --format=tar HEAD | tar -x -C "$WORK"

# The Space needs its own README front-matter at the repository root.
cp "$REPO_ROOT/deploy/huggingface/README.md" "$WORK/README.md"

if [ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]; then
  echo "    note: uncommitted changes are NOT deployed, commit them first." >&2
fi

echo "==> Pushing to https://huggingface.co/spaces/$USERNAME/$SPACE"
cd "$WORK"
git init -q
git add -A
git -c user.email=deploy@local -c user.name=deploy commit -qm "Deploy Polly AI"
git push -q --force "https://oauth2:${HF_TOKEN}@huggingface.co/spaces/${USERNAME}/${SPACE}" HEAD:main

echo "==> Done. Build progress: https://huggingface.co/spaces/${USERNAME}/${SPACE}"
echo "    First build takes ~10 minutes (TensorFlow layer)."
