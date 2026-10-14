#!/bin/sh
# Packages the integration as dist/inkop.zip for a release (HACS zip_release).
#
#   scripts/package-release.sh v0.1.0
#
# The card must already be built with the same version (see docs/release.md); the
# release workflow does both. The zip holds the contents of custom_components/inkop/,
# which HACS unpacks into custom_components/inkop/ on the user's Home Assistant.
set -eu

TAG="${1:?usage: package-release.sh vMAJOR.MINOR.PATCH}"
case "$TAG" in
  v[0-9]*.[0-9]*.[0-9]*) ;;
  *) echo "The tag must look like v1.2.3, got: $TAG" >&2; exit 1 ;;
esac
VERSION="${TAG#v}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/custom_components/inkop"
OUT="$ROOT/dist"

if [ ! -f "$SRC/www/inkop-card.js" ]; then
  echo "The card is not built: run the frontend build first (docs/release.md)" >&2
  exit 1
fi
if ! grep -qF "$VERSION" "$SRC/www/inkop-card.js"; then
  echo "The built card does not contain version $VERSION: build it with that version" >&2
  exit 1
fi

rm -rf "$OUT"
mkdir -p "$OUT/inkop"
cp -R "$SRC/." "$OUT/inkop/"
find "$OUT/inkop" -name __pycache__ -type d -prune -exec rm -rf {} +

python3 - "$OUT/inkop/manifest.json" "$VERSION" <<'PY'
import json
import sys

path, version = sys.argv[1:3]
with open(path, encoding="utf-8") as file:
    manifest = json.load(file)
manifest["version"] = version
with open(path, "w", encoding="utf-8") as file:
    json.dump(manifest, file, indent=2, ensure_ascii=False)
    file.write("\n")
PY

(cd "$OUT/inkop" && zip -qr -X ../inkop.zip .)
echo "Built $OUT/inkop.zip for $TAG"
