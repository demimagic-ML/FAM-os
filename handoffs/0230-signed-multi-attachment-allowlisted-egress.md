# Handoff 0230: Signed multi-attachment allowlisted egress

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 allowlisted network enforcement  
**Status:** Partial  
**Previous handoff:** `0229-allowlisted-egress-accounting-contract.md`

## Objective

Implement the source enforcement path behind ADR 0196 without granting models,
candidates, or the unprivileged product raw host-network authority.

## Scope completed

- Added provider-neutral Supervisor network enforcement contracts, authenticated
  admission, temporary exact authority, and mandatory audit.
- Added a bounded authenticated Unix broker with Ed25519 request verification,
  exact Core UID plus cgroup peer admission, durable intent, and terminal
  open/observe/close/recover lifecycle.
- Added CONNECT-only exact-destination proxying, global-only domain resolution,
  DNS-rebinding denial, aggregate pre-forward byte accounting, quota exhaustion,
  expiry, and bounded shutdown.
- Added deterministic Linux namespace/veth/nftables attachment source.
- Added deterministic Docker IPv6-only internal network plus host input/forward
  nftables policy source.
- Added one shared proxy quota and one lease for Linux, Docker, or mixed
  attachments.
- Wired process, Docker, mixed orchestration, product composition, persistent
  device signing, and explicit owner opt-in.
- Added durable `network_opening` intent so broker response loss recovers while
  substituted plans never contact the broker.
- Added a public-key-only owner export command and a root-owned runtime
  requirement for the broker system service.
- Rerendered and validated all public schemas.
- Built a fresh wheel and ran 129 installed package/source-contract tests under
  each same-host profile label; the artifact explicitly records that no root
  broker or allowlisted enforcement was exercised.

## Explicitly not completed

- No root broker was installed or started in this session.
- No real namespace, veth, nftables, proxy-bypass, DNS-rebinding, byte-exhaustion,
  expiry, restart, or residue qualification has run from a signed installed
  broker runtime.
- The root-owned `/usr/libexec/fam-os-network` deployment remains a
  host-administrator action.
- Independent `compat-cpu-16gb` and `full-reference-workstation` installed runs,
  the 24-hour soak, portable browser packaging, and human review remain open.
- Phase 27.13 and coverage gate 31.6 remain unchecked.

## Architecture and decisions

ADR 0197 extends ADR 0196. It requires one signed request and one aggregate
quota across all attachments, exact UID+cgroup peer authentication, temporary
Supervisor authority, deterministic namespace/Docker enforcement, and an
owner-opt-in client. It explicitly rejects executing an owner-writable FAM_OS
installation as root.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/integration_network.py` | Signed request, multi-attachment lease, and usage contracts |
| `src/fam_os/core/engineering/integration_environment_service.py` | Exact signed network request creation and evidence policy |
| `src/fam_os/supervisor/network_*.py` | Admission, contracts, audit, CONNECT proxy, shared-quota runtime |
| `src/fam_os/adapters/integration/network_broker_*.py` | Client, peer-authenticated daemon, durable state, handler, service |
| `src/fam_os/adapters/integration/multi_network_enforcement.py` | One enforcement lifecycle across attachment providers |
| `src/fam_os/adapters/linux/network_namespace.py` | Namespace/veth/nftables attachment |
| `src/fam_os/adapters/integration/docker_network_enforcement.py` | Docker internal-network and bypass policy attachment |
| `src/fam_os/adapters/integration/process_*.py` | Process lease, intent, lifecycle, and recovery wiring |
| `src/fam_os/adapters/integration/docker_*.py` | Docker lease, proxy usability, lifecycle, and recovery wiring |
| `src/fam_os/adapters/integration/composite_*.py` | Shared mixed lease, partitioning, and terminal accounting |
| `src/fam_os/product/composition/integration_network.py` | Opt-in product signer and broker client composition |
| `src/fam_os/product/network_authority_*.py` | Public-only owner authority export |
| `packaging/systemd/fam-network-broker.service` | Root broker confinement and root-owned runtime requirement |
| `packaging/systemd/fam-os.service` | Optional owner network-client environment file |
| `docs/operations/INTEGRATION_NETWORK_BROKER.md` | Provisioning, revocation, recovery, and limitations |
| `docs/decisions/0197-signed-multi-attachment-integration-egress.md` | Durable architecture decision |

## Public interfaces

- `IntegrationNetworkEnforcementRequest`
- `IntegrationNetworkAttachment`
- `IntegrationNetworkLease`
- `IntegrationNetworkUsage`
- `NetworkEnforcementSpec`, `NetworkEnforcementLease`, `NetworkUsageSnapshot`
- `UnixIntegrationNetworkBroker`
- `fam-network-broker`
- `fam-network-authority`
- `FAM_INTEGRATION_NETWORK_BROKER_SOCKET`
- `fam-network-broker.service`

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_integration_network_authority \
  tests.unit.test_integration_network_broker \
  tests.unit.test_integration_network_broker_handler \
  tests.unit.test_integration_network_broker_server \
  tests.unit.test_integration_network_broker_service \
  tests.unit.test_integration_network_supervisor_authorizer \
  tests.unit.test_linux_namespace_network_enforcement \
  tests.unit.test_supervisor_network_enforcement \
  tests.unit.test_supervisor_network_proxy \
  tests.unit.test_supervisor_network_proxy_runtime \
  tests.unit.test_docker_network_enforcement \
  tests.unit.test_multi_network_enforcement \
  tests.unit.test_process_integration_environment \
  tests.unit.test_process_environment_state \
  tests.unit.test_docker_integration_environment \
  tests.unit.test_mixed_integration_environment \
  tests.integration.test_real_mixed_integration_environment \
  tests.unit.test_product_integration_network_composition \
  tests.unit.test_product_network_authority_export \
  tests.unit.test_integration_environment_service \
  tests.unit.test_integration_environment_composition \
  tests.unit.test_product_service_startup_safety \
  tests.unit.test_network_broker_systemd_unit \
  tests.unit.test_network_broker_root_entrypoint \
  tests.unit.test_signed_bundle_installation \
  tests.unit.test_installation_marker
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_installed_integration_recipes \
  tests.integration.test_process_api_integration_environment \
  tests.unit.test_process_integration_environment \
  tests.unit.test_process_environment_state \
  tests.unit.test_engineering_secret_repository \
  tests.unit.test_engineering_secret_api \
  tests.unit.test_integration_retained_artifacts \
  tests.integration.test_docker_integration_environment \
  tests.unit.test_docker_integration_environment \
  tests.unit.test_integration_environment_repository \
  tests.unit.test_integration_environment_service \
  tests.unit.test_production_database \
  tests.unit.test_product_integration_environment_api \
  tests.integration.test_console_integration_environments \
  tests.integration.test_console_engineering_secrets \
  tests.unit.test_fam_shell_integration_environment_transport \
  tests.unit.test_fam_shell_engineering_secret_transport \
  tests.unit.test_integration_environment_router \
  tests.unit.test_mixed_integration_environment \
  tests.integration.test_real_mixed_integration_environment \
  tests.integration.test_installed_process_owner_restart_chain \
  tests.unit.test_bounded_devtools_client \
  tests.integration.test_real_browser_integration_environment \
  tests.unit.test_integration_environment_composition \
  tests.unit.test_product_integration_network_composition \
  tests.unit.test_product_network_authority_export \
  tests.unit.test_product_service_startup_safety \
  tests.unit.test_network_broker_systemd_unit \
  tests.unit.test_network_broker_root_entrypoint \
  tests.unit.test_signed_bundle_installation \
  tests.unit.test_installation_marker \
  tests.unit.test_integration_network_authority \
  tests.unit.test_integration_network_broker \
  tests.unit.test_integration_network_broker_handler \
  tests.unit.test_integration_network_broker_server \
  tests.unit.test_integration_network_broker_service \
  tests.unit.test_integration_network_supervisor_authorizer \
  tests.unit.test_linux_namespace_network_enforcement \
  tests.unit.test_docker_network_enforcement \
  tests.unit.test_multi_network_enforcement \
  tests.unit.test_supervisor_network_enforcement \
  tests.unit.test_supervisor_network_proxy \
  tests.unit.test_supervisor_network_proxy_runtime \
  tests.contract.test_integration_coverage \
  tests.contract.test_schema_compatibility
PYTHONPATH=src:. python3 -m unittest discover -s tests/architecture -t .
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src:. python3 \
  tools/run_phase27_integration_environment_qualification.py \
  --output artifacts/engineering/phase27/integration-environment-installed-20260719-attempt16.json \
  --repository . --builder-python /usr/bin/python3
docker network create --internal --ipv4=false --ipv6 \
  --subnet fd43:1234:5678:9abc::/64 \
  --gateway fd43:1234:5678:9abc::1 \
  --opt com.docker.network.bridge.name=fdverify0719 \
  fam-source-verify-20260719
docker network inspect fam-source-verify-20260719
docker network rm fam-source-verify-20260719
```

Result: 93 focused tests passed in 7.147 seconds; 169 affected tests passed
in 31.102 seconds; all 41 architecture tests passed in 0.759 seconds; all 375
schema artifacts validate. Docker 29.1.3 accepted the IPv6-only internal
network flags and returned the exact internal, IPv6, bridge, subnet, empty
IP-range, and gateway configuration. The temporary network was removed and a
follow-up inspect returned not found. Installed package attempt 15 deliberately
failed six repository-layout schema fixture cases and remains preserved.
Corrected attempt 16 passes 129 tests per same-host profile label from wheel
`d8004dce42d4ad9b9ea328219e38f8826f5052e2084bf48e382c5137a1b28542`;
its machine-readable fields state `source_contract_only` and
`installed_root_broker_exercised: false`.

## Evidence and artifacts

- `docs/decisions/0197-signed-multi-attachment-integration-egress.md`
- `docs/operations/INTEGRATION_NETWORK_BROKER.md`
- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt15.json`
- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt16.json`
- Larry test logs under `.larry/.../runs/` for the commands above

## Known limitations and risks

- This is source evidence, not installed privileged evidence.
- Docker's daemon socket is a highly privileged dependency; only the trusted,
  root-owned broker runtime may reach it in this path.
- CONNECT tunnel headers are not charged to the payload quota.
- Host TCP/HTTP health access to process services inside a dedicated namespace
  still requires an explicitly designed ingress/probe bridge; signed in-scope
  health recipes are the current safe path.
- The product service and broker are not installed on this host; their exact
  systemd cgroups therefore cannot yet be qualified.

## Operational notes

No root process, namespace, nftables table, service, or broker socket was
created. Two bounded Docker compatibility probes used the exact temporary
network `fam-source-verify-20260719`; both removed it successfully. Do not point
the root system unit at the repository or owner installation.

## Recommended next entry point

Build a fresh signed release and provision a root-owned broker runtime using
`docs/operations/INTEGRATION_NETWORK_BROKER.md`. First qualify one process-only
allowlisted environment with deliberate direct-socket, alternate-cgroup,
private-DNS, quota, expiry, restart, and zero-residue failures. Then qualify
Docker-only and mixed attachments against the same aggregate byte ceiling.
