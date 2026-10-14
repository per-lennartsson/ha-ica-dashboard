#!/bin/sh
# Run a Node command for the card inside Docker (Node is not installed on the host).
#   ./scripts/node.sh npm ci
#   ./scripts/node.sh npm test
# Extra docker flags can be given in DOCKER_FLAGS, e.g. DOCKER_FLAGS="-p 5173:5173".
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${NODE_IMAGE:-node:22-alpine}"
# shellcheck disable=SC2086
exec docker run --rm ${DOCKER_FLAGS:-} \
  --user "$(id -u):$(id -g)" -e HOME=/tmp -e npm_config_cache=/tmp/.npm \
  -v "$ROOT":/repo -w /repo/frontend \
  "$IMAGE" "$@"
