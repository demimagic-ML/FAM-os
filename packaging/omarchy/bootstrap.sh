#!/bin/bash
set -euo pipefail

readonly repo=${FAM_OS_GITHUB_REPOSITORY:-demimagic-ML/FAM-os}
readonly trusted_fingerprint=EFBCEDEEC8C1C058C5AA64F97D8D854748E4D62A
readonly minimum_free_kib=6291456
readonly architecture=$(uname -m)

fail() { echo "FAM Omarchy installer: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null || fail "required command is missing: $1"; }

if [[ $EUID -eq 0 ]]; then
  fail "run this installer as your desktop user; it invokes sudo only for pacman"
fi
case "$architecture" in
  x86_64) ;;
  aarch64)
    [[ ${FAM_OS_ALLOW_EXPERIMENTAL_ARM:-0} == 1 ]] || fail \
      "Omarchy aarch64 is experimental; set FAM_OS_ALLOW_EXPERIMENTAL_ARM=1 to continue"
    ;;
  *) fail "no FAM package is available for architecture: $architecture" ;;
esac

for command in omarchy pacman sudo curl jq sha256sum gpg awk df; do need "$command"; done

omarchy_version=$(pacman -Q omarchy 2>/dev/null | awk '{print $2}' | sed 's/-.*//')
[[ $omarchy_version =~ ^4\. ]] || fail \
  "Omarchy 4.x is required (detected: ${omarchy_version:-unknown})"

free_kib=$(df -Pk "${XDG_DATA_HOME:-$HOME/.local/share}" | awk 'NR==2 {print $4}')
[[ $free_kib =~ ^[0-9]+$ ]] || fail "could not determine available disk space"
(( free_kib >= minimum_free_kib )) || fail \
  "at least 6 GiB free space is required for FAM and browser tooling"

work_root=$(mktemp -d /tmp/fam-os-install.XXXXXX)
trap 'rm -rf -- "$work_root"' EXIT
chmod 700 "$work_root"
curl -fsSL "https://api.github.com/repos/$repo/releases/latest" -o "$work_root/release.json"

asset_url() {
  local name=$1
  jq -er --arg name "$name" \
    '.assets[] | select(.name == $name) | .browser_download_url' \
    "$work_root/release.json"
}

version=$(jq -er '.tag_name | select(test("^v[0-9]+\\.[0-9]+\\.[0-9]+$")) | ltrimstr("v")' \
  "$work_root/release.json")
package_name="fam-os-${version}-1-${architecture}.pkg.tar.zst"
for asset in \
  "$package_name" "$package_name.sig" SHA256SUMS SHA256SUMS.asc \
  fam-os-release.asc; do
  curl -fsSL "$(asset_url "$asset")" -o "$work_root/$asset"
done

mkdir -m 700 "$work_root/gnupg"
gpg --batch --homedir "$work_root/gnupg" --import "$work_root/fam-os-release.asc" \
  >/dev/null 2>&1
actual_fingerprint=$(gpg --batch --homedir "$work_root/gnupg" --with-colons \
  --fingerprint | awk -F: '$1 == "fpr" {print $10; exit}')
[[ $actual_fingerprint == "$trusted_fingerprint" ]] || fail \
  "release signing key fingerprint does not match the pinned FAM trust root"

gpg --batch --homedir "$work_root/gnupg" \
  --verify "$work_root/SHA256SUMS.asc" "$work_root/SHA256SUMS"
(cd "$work_root" && awk -v asset="$package_name" \
  '$2 == asset || $2 == "*" asset {print; found=1} END {exit !found}' SHA256SUMS \
  | sha256sum --check -)
gpg --batch --homedir "$work_root/gnupg" \
  --verify "$work_root/$package_name.sig" "$work_root/$package_name"

# Pacman verifies the detached package signature again using its own keyring.
sudo pacman-key --add "$work_root/fam-os-release.asc"
sudo pacman-key --lsign-key "$trusted_fingerprint"
sudo pacman -U --needed --noconfirm "$work_root/$package_name"

setup=(fam-os setup omarchy --yes)
if [[ ${FAM_OS_ENABLE_WIDGET:-1} == 1 ]]; then
  setup+=(--enable-widget)
else
  setup+=(--no-enable-widget)
fi
if [[ $architecture == aarch64 ]]; then setup+=(--allow-experimental); fi
"${setup[@]}"
fam-os doctor --omarchy

cat <<'INSTRUCTIONS'

FAM is installed and verified.

Launch:    fam
Goal mode: fam goal "Build and test this project"
Console:   fam console

Rollback integration and package (goals and history are preserved):
  fam-os remove omarchy-integration
  sudo pacman -Rns fam-os

Destructive removal of preserved user data:
  fam-os purge --user-data --yes
INSTRUCTIONS
