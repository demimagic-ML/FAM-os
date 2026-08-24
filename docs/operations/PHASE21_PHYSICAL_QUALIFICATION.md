# Phase 21.7 two-physical-host qualification

Phase 21.7 is not satisfied by localhost, two installation prefixes, containers,
virtual machines, network namespaces, or a simulated peer. It requires one
signed FAM_OS release installed on two distinct physical Linux machines. The
final artifact is assembled only from live requester evidence, device-signed
peer checkpoints, installed diagnoses, and post-removal observations.

## Required machines

- **Requester:** the current workstation, with local `qwen3:1.7b` available for
  the unchanged-acceptance recovery path.
- **Expert peer:** a second physical Linux machine reachable over a non-loopback
  TCP address, with Ollama and downloaded `gemma4:26b`.
- Both hosts need independent owner-private state and install roots.
- Both hosts must report `systemd-detect-virt` as `none`, distinct machine-ID
  hashes, and distinct hardware-anchor hashes from an accessible DMI product
  UUID, device-tree serial, or physical block-device serial.
- Shell access is an operating convenience only. FAM pairing and mutual TLS are
  the trust boundary.

Use a unique identifier for one entire attempt, for example:

```bash
export QUALIFICATION_ID=phase21.7-20260717-01
export FAM_PREFIX="$HOME/.local/share/fam-os-phase21.7"
export FAM_STATE="$HOME/.local/share/fam-os-phase21.7-state"
export FAM_RUNTIME="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/fam-os-phase21.7"
```

Never point `FAM_STATE` at an existing user installation.

## Build one portable signed release

On the trusted build workstation:

```bash
mkdir -p .phase21.7/wheelhouse
.verification-venv/bin/python -m pip wheel . \
  --wheel-dir .phase21.7/wheelhouse --no-build-isolation
openssl genpkey -algorithm ED25519 -out .phase21.7/release-key.pem
chmod 600 .phase21.7/release-key.pem
openssl pkey -in .phase21.7/release-key.pem -pubout \
  -out .phase21.7/release-key.pub.pem
PYTHONPATH=src:. .verification-venv/bin/python tools/build_signed_release.py \
  --release-id phase21.7-physical \
  --wheelhouse .phase21.7/wheelhouse \
  --key-id phase21.7-physical-key \
  --private-key .phase21.7/release-key.pem \
  --output .phase21.7/release \
  --repository .
```

Keep the private key on the build workstation. Copy only the release directory,
public key, and this qualification checkout to each host.

## Install and configure both hosts

Run on each machine from the copied checkout:

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m fam_os.product.cli \
  --prefix "$FAM_PREFIX" \
  --trusted-key phase21.7-physical-key=.phase21.7/release-key.pub.pem \
  install --bundle .phase21.7/release
"$FAM_PREFIX/bin/fam-os" --prefix "$FAM_PREFIX" diagnose
```

Choose each host's real LAN address. On the requester use device name
`Requester`; on the peer use `Expert peer`. Configure the listener on each host:

```bash
"$FAM_PREFIX/bin/fam-os" --prefix "$FAM_PREFIX" peer \
  --state-root "$FAM_STATE" --device-name "DEVICE NAME" configure \
  --listen-host "LAN_ADDRESS" --listen-port 48121 \
  --advertised-host "LAN_ADDRESS" --advertised-port 48121 --confirm
```

Generate one offer on each host and exchange the two files:

```bash
"$FAM_PREFIX/bin/fam-os" --prefix "$FAM_PREFIX" peer \
  --state-root "$FAM_STATE" --device-name "DEVICE NAME" offer \
  > local-offer.json
```

On both hosts, calculate the code with the local offer first and compare it
visually. Then approve with the exact matching code:

```bash
"$FAM_PREFIX/bin/fam-os" --prefix "$FAM_PREFIX" peer \
  --state-root "$FAM_STATE" --device-name "DEVICE NAME" code \
  --local-offer local-offer.json --peer-offer peer-offer.json
"$FAM_PREFIX/bin/fam-os" --prefix "$FAM_PREFIX" peer \
  --state-root "$FAM_STATE" --device-name "DEVICE NAME" approve \
  --local-offer local-offer.json --peer-offer peer-offer.json \
  --code "SAME DISPLAYED CODE" --confirm
```

Keep the two enrollment JSON outputs. On the build workstation, derive the
reciprocal pairing record from their signed approvals:

```bash
PYTHONPATH=src:tools:. .verification-venv/bin/python \
  tools/phase21_physical_exit/assemble_pairing.py \
  --requester-enrollment requester-enrollment.json \
  --peer-enrollment peer-enrollment.json --output pairing.json
```

Record the enrollment IDs and device IDs from the generated `pairing.json`.

## Start both installed services

Run the requester with its local recovery model:

```bash
"$FAM_PREFIX/bin/fam-service" \
  --state-root "$FAM_STATE" --runtime-root "$FAM_RUNTIME" \
  --external-ollama --ollama-url http://127.0.0.1:11434 \
  --model qwen3:1.7b --device-name Requester --console-port 8765
```

Run the peer with Gemma:

```bash
"$FAM_PREFIX/bin/fam-service" \
  --state-root "$FAM_STATE" --runtime-root "$FAM_RUNTIME" \
  --external-ollama --ollama-url http://127.0.0.1:11434 \
  --model gemma4:26b --device-name "Expert peer" --console-port 8765
```

Console remains loopback-only on each machine. Its bootstrap token is
`$FAM_RUNTIME/console.token`.

## Capture device-signed host evidence

Run on the requester with role `requester`, and on the peer with role
`expert_peer`:

```bash
PYTHONPATH=tools:. .verification-venv/bin/python \
  tools/phase21_physical_exit/host_probe.py \
  --installed-python "$FAM_PREFIX/active/python" --repository . \
  --prefix "$FAM_PREFIX" --state-root "$FAM_STATE" \
  --device-name "DEVICE NAME" --qualification-id "$QUALIFICATION_ID" \
  --role ROLE --output host.json
```

The installed device root signs the hardware observation. Validation rejects a
modified observation, different qualification identifier, different signed
manifest, virtualized host, unhealthy install, or matching machine/hardware
identity.

## Capture real remote success

On the peer, before the request:

```bash
PYTHONPATH=tools:. .verification-venv/bin/python \
  tools/phase21_physical_exit/capture_peer_observation.py \
  --installed-python "$FAM_PREFIX/active/python" --repository . \
  --state-root "$FAM_STATE" --device-name "Expert peer" \
  --qualification-id "$QUALIFICATION_ID" \
  --checkpoint before_remote_success --console-url http://127.0.0.1:8765 \
  --console-token-file "$FAM_RUNTIME/console.token" \
  --output peer-before-success.json
```

On the requester, submit the exact verified task. The two privacy flags are
required together and are valid only for a fresh qualification state at privacy
revision zero:

```bash
PYTHONPATH=tools:. .verification-venv/bin/python \
  tools/phase21_physical_exit/capture_requester.py success \
  --installed-python "$FAM_PREFIX/active/python" --repository . \
  --state-root "$FAM_STATE" --device-name Requester \
  --qualification-id "$QUALIFICATION_ID" \
  --console-url http://127.0.0.1:8765 \
  --console-token-file "$FAM_RUNTIME/console.token" \
  --enrollment-id PEER_ENROLLMENT_ID --peer-device-id PEER_DEVICE_ID \
  --configure-privacy --confirm-privacy \
  --request-id phase21-physical-success --output requester-success.json
```

On the peer, repeat the checkpoint with `--checkpoint after_remote_success` and
write `peer-after-success.json`. Exactly one peer context-evidence record must
have been added, and neither database may contain the prompt.

## Capture physical peer-loss recovery

On the peer, record `before_peer_loss` as `peer-before-loss.json`, then stop the
peer service completely. From the requester, confirm its real LAN port is
closed and run:

```bash
PYTHONPATH=tools:. .verification-venv/bin/python \
  tools/phase21_physical_exit/capture_requester.py loss \
  --installed-python "$FAM_PREFIX/active/python" --repository . \
  --state-root "$FAM_STATE" --device-name Requester \
  --qualification-id "$QUALIFICATION_ID" \
  --console-url http://127.0.0.1:8765 \
  --console-token-file "$FAM_RUNTIME/console.token" \
  --enrollment-id PEER_ENROLLMENT_ID --peer-device-id PEER_DEVICE_ID \
  --privacy-revision 1 --peer-host PEER_LAN_ADDRESS --peer-port 48121 \
  --request-id phase21-physical-loss --output requester-loss-pending.json
```

Restart the peer service. On the requester, authenticate it again:

```bash
PYTHONPATH=tools:. .verification-venv/bin/python \
  tools/phase21_physical_exit/verify_peer_restart.py \
  --loss-capture requester-loss-pending.json \
  --console-url http://127.0.0.1:8765 \
  --console-token-file "$FAM_RUNTIME/console.token" \
  --output requester-loss.json
```

On the peer, capture `after_peer_restart` as `peer-after-restart.json`. No new
peer context evidence may have been created by the failed pre-connect attempt.

Bind the live requester captures to the four device-signed peer checkpoints:

```bash
PYTHONPATH=src:tools:. .verification-venv/bin/python \
  tools/phase21_physical_exit/finalize_scenarios.py \
  --success-capture requester-success.json --loss-capture requester-loss.json \
  --peer-before-success peer-before-success.json \
  --peer-after-success peer-after-success.json \
  --peer-before-loss peer-before-loss.json \
  --peer-after-restart peer-after-restart.json \
  --success-output remote-success.json \
  --loss-output peer-loss-recovery.json
```

## Diagnose, remove, and assemble

Before stopping the services, capture diagnosis on each host with the proper
role:

```bash
PYTHONPATH=tools:. .verification-venv/bin/python \
  tools/phase21_physical_exit/capture_diagnosis.py \
  --installed-python "$FAM_PREFIX/active/python" --repository . \
  --prefix "$FAM_PREFIX" --role ROLE --output diagnosis.json
```

Stop both services. Remove each signed installation using its installed CLI,
then delete only the dedicated qualification state root:

```bash
"$FAM_PREFIX/bin/fam-os" --prefix "$FAM_PREFIX" remove
rm -rf -- "$FAM_STATE"
PYTHONPATH=tools:. .verification-venv/bin/python \
  tools/phase21_physical_exit/verify_removal.py \
  --prefix "$FAM_PREFIX" --state-root "$FAM_STATE" \
  --role ROLE --output removal.json
```

Copy the content-free JSON evidence to the trusted build workstation and run:

```bash
PYTHONPATH=src:tools:. .verification-venv/bin/python \
  tools/phase21_physical_exit/assemble_report.py \
  --requester-host requester-host.json --peer-host peer-host.json \
  --pairing pairing.json --remote-success remote-success.json \
  --peer-loss-recovery peer-loss-recovery.json \
  --requester-diagnosis requester-diagnosis.json \
  --peer-diagnosis peer-diagnosis.json \
  --requester-removal requester-removal.json \
  --peer-removal peer-removal.json \
  --output artifacts/fabric/phase21.7-physical-qualification.json
```

`pairing.json` is derived from both signed active enrollment records. The final
validator cross-checks those reciprocal device IDs against both signed host
observations and the live remote evidence.

Only an assembler exit code of zero, a report with `"passed": true`, and absent
qualification install/state roots on both machines may close Phase 21.7. Phase
22 must not start before that artifact exists.
