import os
import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.shell import (
    ShellRequestDispatcher, UnixShellClientConfiguration, UnixShellCoreClient,
    UnixShellServer, UnixShellServerConfiguration,
)
from fam_os.applications.transport.auth import PeerAuthorizationPolicy
from fam_os.core.engineering import GrantLifecycleState, OwnerGrantApproval
from fam_os.core.engineering.grant_policy import engineering_grant_digest
from fam_os.product.composition.database_engineering import compose_database_engineering
from fam_os.product.composition.storage_unit import ProductStorageUnit
from fam_os.product.owner_identity import local_owner_id
from fam_os.shell import (
    ShellEngineeringActivationRequest, ShellEngineeringAuthorityOperation,
    ShellEngineeringContextRequest, ShellEngineeringGrantQuery,
    ShellEngineeringRevocationRequest,
)
from tests.integration.installed_database_authority_support import (
    ConsoleAuthorityClient, UnusedCore, authority_api, console_activate,
    database_fixture, engineering_grant, now, serve,
)


class InstalledDatabaseAuthorityChainTests(unittest.TestCase):
    def test_console_database_restart_shell_reconfirmation_and_revocation(self):
        profile = os.environ.get("FAM_ENGINEERING_HARDWARE_PROFILE")
        if profile is not None:
            self.assertIn(profile, {
                "compat-cpu-16gb", "full-reference-workstation",
            })
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            state_root = root / "product"
            state_root.mkdir(mode=0o700)
            candidate_root = root / "candidate"
            candidate_root.mkdir(mode=0o700)
            owner_id = local_owner_id(os.geteuid())
            plan, candidate = database_fixture(candidate_root)
            grant = engineering_grant(owner_id, plan, candidate)
            self._execute_console_database(root, state_root, owner_id, plan, candidate, grant)
            self._restart_reconfirm_revoke(root, state_root, owner_id, plan, candidate, grant)

    def _execute_console_database(
        self, root, state_root, owner_id, plan, candidate, grant,
    ):
        storage = ProductStorageUnit(state_root, os.geteuid())
        result = storage.start()
        self.assertFalse(result.recovery_required)
        api = authority_api(storage, owner_id)
        with ConsoleAuthorityClient(root / "console-1", api) as console:
            approval = console_activate(console, grant)
            inspected = console.get(f"/api/v1/engineering/grants/{grant.grant_id}")
            self.assertTrue(inspected["usable"])
            self.assertEqual(approval.grant_sha256, engineering_grant_digest(grant))
            engineering = compose_database_engineering(
                owner_id, result.cipher, storage.engineering_authorizer,
            )
            receipt = engineering.service.execute(
                plan, candidate, grant.grant_id, grant.principal_id,
                "database-session-1", lambda: False,
            )
            self.assertEqual("verified", receipt.verification.status.value)
            audit = console.get(
                f"/api/v1/engineering/grants/{grant.grant_id}/audit",
            )
            self.assertGreaterEqual(len(audit["decisions"]), 4)
            self.assertTrue(all(
                item["payload"]["allowed"] for item in audit["decisions"]
            ))
        storage.stop()

    def _restart_reconfirm_revoke(
        self, root, state_root, owner_id, plan, candidate, grant,
    ):
        storage = ProductStorageUnit(state_root, os.geteuid())
        result = storage.start()
        self.assertGreaterEqual(storage.engineering_reconfirmations_required, 1)
        api = authority_api(storage, owner_id)
        with ConsoleAuthorityClient(root / "console-2", api) as console:
            inspected = console.get(f"/api/v1/engineering/grants/{grant.grant_id}")
            self.assertTrue(inspected["reconfirmation_required"])
            self.assertFalse(inspected["usable"])
        self._shell_reconfirm_revoke(root, owner_id, grant, api)
        engineering = compose_database_engineering(
            owner_id, result.cipher, storage.engineering_authorizer,
        )
        with self.assertRaisesRegex(PermissionError, "exact live authority"):
            engineering.service.execute(
                plan, candidate, grant.grant_id, grant.principal_id,
                "database-session-2", lambda: False,
            )
        storage.stop()

    def _shell_reconfirm_revoke(self, root, owner_id, grant, api):
        socket_path = root / "runtime" / "shell.sock"
        socket_path.parent.mkdir(mode=0o700)
        server = UnixShellServer(
            UnixShellServerConfiguration(socket_path),
            PeerAuthorizationPolicy(os.geteuid()),
            ShellRequestDispatcher(UnusedCore(), engineering_authority=api),
        )
        server.open()
        try:
            client = UnixShellCoreClient(UnixShellClientConfiguration(socket_path))
            session = "shell-authority-session-1"
            context = serve(server, lambda: client.engineering_context(
                ShellEngineeringContextRequest(
                    "shell-context-1", session, owner_id, "engineering-grant",
                    engineering_grant_digest(grant), True,
                ),
            ))
            approval = OwnerGrantApproval(
                "shell-approval-1", grant.grant_id, owner_id,
                engineering_grant_digest(grant), now(), context.context_id,
            )
            activated = serve(server, lambda: client.engineering_activate(
                ShellEngineeringActivationRequest(
                    "shell-activate-1", session, grant, approval, None, None, True,
                ),
            ))
            self.assertTrue(activated.usable)
            inspected = serve(server, lambda: client.engineering_query(
                ShellEngineeringGrantQuery(
                    "shell-inspect-1", ShellEngineeringAuthorityOperation.INSPECT,
                    grant.grant_id,
                ),
            ))
            self.assertFalse(inspected.reconfirmation_required)
            revoked = serve(server, lambda: client.engineering_revoke(
                ShellEngineeringRevocationRequest(
                    "shell-revoke-1", grant.grant_id, owner_id, True,
                ),
            ))
            self.assertEqual(GrantLifecycleState.REVOKED, revoked.grant.state)
        finally:
            server.close()


if __name__ == "__main__":
    unittest.main()
