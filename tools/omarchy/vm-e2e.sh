#!/bin/bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
usage: vm-e2e.sh --target user@disposable-omarchy-vm [options]
  --package PATH           current FAM_OS Arch package
  --previous-package PATH  package to install before testing upgrade
  --offline                run setup once with outbound networking denied
  --reboot                 reboot and verify durable state
  --verify-paused-goal     pause the current goal before reboot and verify it
  --remove-reinstall       verify integration removal and package reinstall

The target must be a disposable Omarchy VM. Set FAM_OS_DISPOSABLE_VM=1 to
acknowledge that the gate installs/removes packages and can reboot it.
USAGE
  exit 2
}

target="" package="" previous="" offline=false reboot=false remove_reinstall=false verify_paused=false
while (( $# > 0 )); do
  case "$1" in
    --target) target=${2:-}; shift 2 ;;
    --package) package=${2:-}; shift 2 ;;
    --previous-package) previous=${2:-}; shift 2 ;;
    --offline) offline=true; shift ;;
    --reboot) reboot=true; shift ;;
    --verify-paused-goal) verify_paused=true; reboot=true; shift ;;
    --remove-reinstall) remove_reinstall=true; shift ;;
    *) usage ;;
  esac
done
[[ -n $target ]] || usage
[[ ${FAM_OS_DISPOSABLE_VM:-0} == 1 ]] || {
  echo "Refusing to mutate an unconfirmed host; set FAM_OS_DISPOSABLE_VM=1." >&2
  exit 1
}

remote_root=/tmp/fam-os-vm-e2e
ssh "$target" 'command -v omarchy >/dev/null && test "$(uname -m)" = x86_64'
ssh "$target" "rm -rf '$remote_root' && mkdir -p '$remote_root'"
scp -r tests/fixtures/omarchy_browser_app "$target:$remote_root/browser-app" >/dev/null
scp tests/live/omarchy/test_application_e2e.py "$target:$remote_root/test_application_e2e.py" >/dev/null

copy_package() {
  local source=$1 name=$2
  [[ -f $source ]] || { echo "Package does not exist: $source" >&2; exit 1; }
  scp "$source" "$target:$remote_root/$name" >/dev/null
}
[[ -z $previous ]] || copy_package "$previous" previous.pkg.tar.zst
[[ -z $package ]] || copy_package "$package" current.pkg.tar.zst

if [[ -n $previous ]]; then
  ssh "$target" "sudo pacman -U --needed --noconfirm '$remote_root/previous.pkg.tar.zst'"
  ssh "$target" 'fam-os setup omarchy --yes --enable-widget'
  ssh "$target" 'mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}/fam-os-vm-e2e" && printf preserved >"${XDG_STATE_HOME:-$HOME/.local/state}/fam-os-vm-e2e/upgrade-marker"'
fi
if [[ -n $package ]]; then
  ssh "$target" "sudo pacman -U --needed --noconfirm '$remote_root/current.pkg.tar.zst'"
else
  ssh "$target" 'sudo pacman -S --needed --noconfirm fam-os'
fi

if $offline; then
  ssh "$target" 'systemd-run --user --wait --collect --pipe -p IPAddressDeny=any fam-os setup omarchy --yes --no-enable-widget'
else
  ssh "$target" 'fam-os setup omarchy --yes --enable-widget'
fi

ssh "$target" 'bash -se' <<'REMOTE'
set -euo pipefail
fam-os doctor --omarchy --json >/tmp/fam-os-doctor.json
jq -e '.capabilities.host.omarchy == true' /tmp/fam-os-doctor.json >/dev/null
systemctl --user is-active --quiet fam-os.service
systemctl --user is-active --quiet fam-os-desktop.service
systemctl --user is-active --quiet fam-os-usage.timer
test -s "$XDG_RUNTIME_DIR/fam-os/widget.json"
test -s "$XDG_RUNTIME_DIR/fam-os/widget.token"
test -s "$HOME/.config/omarchy/plugins/fam.os/manifest.json"
omarchy-agent-usage-fam --force | jq -e '.schemaVersion == 1 and .id == "fam-os"' >/dev/null
FAM_OS_LIVE_OMARCHY_APP=1 \
FAM_OS_LIVE_OMARCHY_FIXTURE=/tmp/fam-os-vm-e2e/browser-app \
python /tmp/fam-os-vm-e2e/test_application_e2e.py
fam-os repair omarchy
fam-os setup omarchy --yes --enable-widget
if test -e "${XDG_STATE_HOME:-$HOME/.local/state}/fam-os-vm-e2e/upgrade-marker"; then
  grep -qx preserved "${XDG_STATE_HOME:-$HOME/.local/state}/fam-os-vm-e2e/upgrade-marker"
fi
mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}/fam-os-vm-e2e"
find "$HOME/.local/share/fam-os/engineering/candidates" -type d 2>/dev/null | sort >"${XDG_STATE_HOME:-$HOME/.local/state}/fam-os-vm-e2e/candidates-before" || :
REMOTE

if $verify_paused; then
  ssh "$target" 'bash -se' <<'REMOTE'
set -euo pipefail
mkdir -p /tmp/fam-os-vm-e2e/goal-workspace
timeout 600 fam goal --workspace /tmp/fam-os-vm-e2e/goal-workspace \
  "Create a release-gate plan, then add a goal-marker.txt file and verify its exact content." \
  >/tmp/fam-os-vm-e2e/goal-submit.json
descriptor="$XDG_RUNTIME_DIR/fam-os/widget.json"
endpoint=$(jq -r .endpoint "$descriptor")
token=$(cat "$(jq -r .tokenPath "$descriptor")")
goal=$(curl -fsS -H "X-FAM-Widget-Token: $token" "$endpoint/api/v1/goals/active")
goal_id=$(jq -er '.goal.goal_id' <<<"$goal")
command_id="vm-pause-$(date +%s%N)"
curl -fsS -X POST -H "X-FAM-Widget-Token: $token" -H 'Content-Type: application/json' -d "{\"commandId\":\"$command_id\"}" "$endpoint/api/v1/goals/$goal_id/pause" >/dev/null
for _attempt in $(seq 1 30); do
  status=$(curl -fsS -H "X-FAM-Widget-Token: $token" "$endpoint/api/v1/goals/active" | jq -r '.goal.status')
  [[ $status == paused ]] && break
  sleep 1
done
[[ $status == paused ]]
printf '%s\n' "$goal_id" >"${XDG_STATE_HOME:-$HOME/.local/state}/fam-os-vm-e2e/paused-goal-id"
REMOTE
fi

if $reboot; then
  ssh "$target" 'sudo systemctl reboot' || true
  for _attempt in $(seq 1 90); do
    sleep 2
    ssh -o ConnectTimeout=2 "$target" true >/dev/null 2>&1 && break
  done
  ssh "$target" 'bash -se' <<'REMOTE'
set -euo pipefail
systemctl --user start fam-os.service fam-os-desktop.service fam-os-usage.timer
systemctl --user is-active --quiet fam-os.service
fam-os doctor --omarchy --json | jq -e '.capabilities.host.omarchy == true' >/dev/null
find "$HOME/.local/share/fam-os/engineering/candidates" -type d 2>/dev/null | sort >"${XDG_STATE_HOME:-$HOME/.local/state}/fam-os-vm-e2e/candidates-after" || :
diff -u "${XDG_STATE_HOME:-$HOME/.local/state}/fam-os-vm-e2e/candidates-before" "${XDG_STATE_HOME:-$HOME/.local/state}/fam-os-vm-e2e/candidates-after"
if test -s "${XDG_STATE_HOME:-$HOME/.local/state}/fam-os-vm-e2e/paused-goal-id"; then
  descriptor="$XDG_RUNTIME_DIR/fam-os/widget.json"
  endpoint=$(jq -r .endpoint "$descriptor")
  token=$(cat "$(jq -r .tokenPath "$descriptor")")
  active=$(curl -fsS -H "X-FAM-Widget-Token: $token" "$endpoint/api/v1/goals/active")
  test "$(jq -r '.goal.goal_id' <<<"$active")" = "$(cat "${XDG_STATE_HOME:-$HOME/.local/state}/fam-os-vm-e2e/paused-goal-id")"
  test "$(jq -r '.goal.status' <<<"$active")" = paused
fi
REMOTE
fi

if $remove_reinstall; then
  ssh "$target" 'fam-os remove omarchy-integration && sudo pacman -Rns --noconfirm fam-os'
  ssh "$target" 'test ! -e "$HOME/.config/omarchy/plugins/fam.os" && test -d "$HOME/.local/share/fam-os"'
  if [[ -n $package ]]; then
    ssh "$target" "sudo pacman -U --needed --noconfirm '$remote_root/current.pkg.tar.zst'"
  else
    ssh "$target" 'sudo pacman -S --needed --noconfirm fam-os'
  fi
  ssh "$target" 'fam-os setup omarchy --yes --enable-widget && fam-os doctor --omarchy --json >/dev/null'
fi

echo "Omarchy VM release gate passed for $target"
