# Omarchy live release gate

The automated unit and contract suites run everywhere. The destructive live
gate runs only in disposable Omarchy VMs through `tools/omarchy/vm-e2e.sh`.
Set `FAM_OS_LIVE_OMARCHY_APP` inside the VM to include a real Chromium and
Playwright application session in the Python live suite.
