"""Command-line entrypoint for the privileged integration network broker."""

import argparse
from pathlib import Path
import signal

from fam_os.adapters.integration.network_broker_service import (
    NetworkBrokerServiceConfiguration, compose_network_broker_service,
)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fam-network-broker")
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--socket-owner-uid", type=int, required=True)
    parser.add_argument("--socket-group-id", type=int, required=True)
    parser.add_argument("--core-uid", type=int, required=True)
    parser.add_argument("--core-cgroup", required=True)
    parser.add_argument("--broker-state-root", type=Path, required=True)
    parser.add_argument("--linux-state-root", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--trusted-key-id", required=True)
    parser.add_argument("--trusted-public-key", type=Path, required=True)
    args = parser.parse_args(argv)
    configuration = NetworkBrokerServiceConfiguration(
        args.socket.absolute(), args.socket_owner_uid, args.socket_group_id,
        args.core_uid, args.core_cgroup, args.broker_state_root.absolute(),
        args.linux_state_root.absolute(), args.audit.absolute(),
        args.trusted_key_id, args.trusted_public_key.absolute(),
    )
    service = compose_network_broker_service(configuration)
    signal.signal(signal.SIGTERM, lambda *_args: service.stop())
    signal.signal(signal.SIGINT, lambda *_args: service.stop())
    service.run()


if __name__ == "__main__":
    main()
