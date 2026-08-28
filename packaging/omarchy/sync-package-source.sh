#!/bin/bash
set -euo pipefail

source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
target=${1:?usage: sync-package-source.sh /path/to/omarchy-pkgs}
package_root="$target/pkgbuilds/fam-os"

install -d "$package_root/.omarchy"
install -m 0644 "$source_root/packaging/omarchy/omarchy-pkgs/fam-os/PKGBUILD" "$package_root/PKGBUILD"
install -m 0644 "$source_root/packaging/arch/fam-os.install" "$package_root/fam-os.install"
install -m 0644 "$source_root/packaging/omarchy/omarchy-pkgs/fam-os/.omarchy/package.json" "$package_root/.omarchy/package.json"
install -m 0755 "$source_root/packaging/omarchy/omarchy-pkgs/fam-os/.omarchy/upstream.sh" "$package_root/.omarchy/upstream.sh"
echo "Synchronized FAM_OS package source into $package_root"
