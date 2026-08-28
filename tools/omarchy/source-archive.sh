#!/bin/bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
reference=${1:-HEAD}
version=${2:-$(git -C "$root" describe --tags --exact-match "$reference" 2>/dev/null | sed 's/^v//')}
output=${3:-$root/dist/omarchy}

[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "usage: source-archive.sh [git-reference] [semantic-version] [output-directory]" >&2
  exit 1
}
git -C "$root" rev-parse --verify "$reference^{commit}" >/dev/null
mkdir -p "$output"
archive="$output/fam-os-$version.tar.gz"
temporary="$archive.tmp"
git -C "$root" archive --format=tar --prefix="fam-os-$version/" "$reference" \
  | gzip -n -9 >"$temporary"
mv "$temporary" "$archive"
sha256sum "$archive"
