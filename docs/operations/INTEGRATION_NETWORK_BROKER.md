# Integration network broker operations

The integration network broker is an optional, separately privileged service.
FAM Core does not receive allowlisted integration egress merely because FAM_OS
is installed. An owner and a host administrator must deliberately provision
both halves of the boundary.

## Authority boundary

- Core signs one exact request with the persistent device identity.
- The broker accepts only the configured Core UID in the configured exact
  cgroup and verifies the device signature.
- The deterministic Supervisor admits only that request, records mandatory
  audit events, and delegates to namespace, Docker-network, nftables, and
  CONNECT-proxy adapters.
- Candidates receive an attachment and credential-free proxy URI. They never
  receive broker, Docker, nftables, or Supervisor authority.
- Process and Docker attachments in one mixed environment share one aggregate
  transmitted-plus-received byte quota.

The source checkout or an owner-writable installation must never be executed as
root. The system unit deliberately requires a separately installed,
root-owned `/usr/libexec/fam-os-network` signed installation.

## Owner opt-in

From the signed owner installation, export only the public device authority to
a new absolute private directory:

```text
fam-network-authority \
  --state-root /absolute/owner/state/fam-os \
  --device-name "the configured device display name" \
  --output /absolute/owner/private/network-authority-export
```

The export contains `network-authority.pem` and
`network-authority.json`. It never contains the private identity key. Reusing
an existing output directory is refused.

The owner does not enable the Core client yet. First give the public export and
the intended Core service identity to the host administrator.

## Host-administrator provisioning

The administrator must independently verify the signed release, install its
wheel and dependencies into a root-owned, non-owner-writable Python runtime,
into `/usr/libexec/fam-os-network`. The system unit invokes its root-owned
`bin/fam-network-broker`, which revalidates the signed installation before it
opens the socket. Copying or executing the
owner-writable `active/python`, `bin/fam-network-broker`, repository checkout,
or an unverified wheel is forbidden.

Install the public key as `/etc/fam-os/network-authority.pem`, owned by root and
not group/world writable. Create `/etc/fam-os/network-broker.env`, also owned by
root and not group/world writable, with exactly:

```text
FAM_CORE_UID=<numeric owner UID>
FAM_CORE_GID=<numeric group allowed to connect to the broker socket>
FAM_CORE_CGROUP=<exact unified-cgroup-v2 ControlGroup for fam-os.service>
FAM_NETWORK_KEY_ID=<key_id from network-authority.json>
```

Obtain `FAM_CORE_CGROUP` from the installed user service's systemd
`ControlGroup` property, not from an interactive shell or browser process. The
broker compares the peer process against that exact cgroup on every request.

Create `/run/netns` as a root-owned, non-group/world-writable runtime directory
before starting the broker. Install
`packaging/systemd/fam-network-broker.service` as a root-owned system unit,
reload systemd, and start it. Its required writable roots are limited to the
broker socket, `/run/netns`, its three state/audit directories, and kernel or
Docker control paths reached through bounded adapters.

## Enable the Core client

Only after the broker is healthy, the owner may create
`~/.config/fam-os/network-client.env` with mode `0600`:

```text
FAM_INTEGRATION_NETWORK_BROKER_SOCKET=/run/fam-os-network/broker.sock
```

Restart `fam-os.service`. This setting gives Core the ability to request
allowlisted integration egress; every individual environment still requires
the normal owner grant, exact network decisions, signed plan, byte ceiling,
verification, cleanup, and audit path.

## Revocation and recovery

Clean active integration environments before removing authority. Then remove
or rename the owner network-client environment file, restart the user service,
and stop/disable the system broker. Removing only the proxy variables is not
revocation. Deleting broker journals before recovery is forbidden.

After an interruption, restart the broker with the same root-owned state and
trust configuration. Product intent recovery invokes the broker's exact
`recover` operation; deterministic namespace, bridge, nftables, proxy, and
quota state must reach terminal evidence before Core can record cleanup.

## Current protocol limits

- Only HTTP/1.1 `CONNECT` is supported. UDP and transparent arbitrary sockets
  are denied.
- Domain names must resolve to globally routable addresses on each connection;
  private-address DNS rebinding is denied. An explicit private IP literal is
  possible only when the owner explicitly approved that literal and port.
- The byte ceiling is aggregate transmitted plus received tunnel payload. The
  CONNECT request and response headers are not charged.
- Source tests and an unprivileged Docker-network compatibility probe are not
  installed privileged evidence. Qualification requires the signed installed
  runtime, real namespace/nftables enforcement, deliberate bypass and quota
  failures, restart recovery, zero residue, and both validation profiles.
