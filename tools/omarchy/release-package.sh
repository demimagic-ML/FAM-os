#!/bin/bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
output=${1:-$root/dist/omarchy}
reference=${2:-HEAD}
version=${3:-$(git -C "$root" describe --tags --exact-match "$reference" 2>/dev/null | sed 's/^v//')}
mkdir -p "$output"

command -v makepkg >/dev/null || { echo "makepkg is required" >&2; exit 1; }
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "usage: release-package.sh [output] [git-reference] [semantic-version]" >&2
  exit 1
}

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp "$root/packaging/arch/PKGBUILD" "$root/packaging/arch/fam-os.install" "$work/"
"$root/tools/omarchy/source-archive.sh" "$reference" "$version" "$work"
source_archive="$work/fam-os-$version.tar.gz"
source_sha=$(sha256sum "$source_archive" | cut -d' ' -f1)
sed -i "s/^pkgver=.*/pkgver=$version/; s/^sha256sums=.*/sha256sums=('$source_sha')/" "$work/PKGBUILD"
(cd "$work" && makepkg --clean --cleanbuild --force --noconfirm)
cp "$work"/*.pkg.tar.zst "$output/"
cp "$source_archive" "$output/"
(cd "$output" && sha256sum ./*.tar.gz ./*.pkg.tar.zst >SHA256SUMS)
