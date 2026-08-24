import base64
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.fabric import (
    DeviceIdentity,
    HardwareAnchorKind,
    PhysicalHostRole,
    PhysicalPeerCheckpoint,
    create_physical_peer_observation,
    create_physical_host_evidence,
    verify_physical_peer_observation,
    verify_physical_host_evidence,
)
from fam_os.schemas import dumps_document
from tools.phase21_physical_exit.validation import (
    phase21_7_passed,
    phase21_7_tooling_smoke_passed,
    physical_hosts_valid,
)
from tools.phase21_physical_exit.assemble_report import main as assemble_report


class PhysicalFabricQualificationTests(unittest.TestCase):
    def test_requires_distinct_signed_nonvirtual_hosts_on_exact_release(self):
        requester = host(PhysicalHostRole.REQUESTER, 1, "a", "b")
        peer = host(PhysicalHostRole.EXPERT_PEER, 2, "c", "d")
        self.assertTrue(physical_hosts_valid(requester, peer))
        for changed in (
            {"physical_host": False, "virtualization_kind": "kvm"},
            {"machine_id_sha256": "a" * 64},
            {"hardware_anchor_sha256": "b" * 64},
            {"release_id": "other"},
            {"release_manifest_sha256": "f" * 64},
            {"qualification_id": "qualification-other"},
            {"installation_healthy": False},
        ):
            with self.subTest(changed=changed):
                changed_peer = json.loads(json.dumps(peer))
                changed_peer["payload"].update(changed)
                self.assertFalse(physical_hosts_valid(
                    requester, changed_peer,
                ))

    def test_host_signature_detects_hardware_tampering(self):
        value = signed_host(PhysicalHostRole.REQUESTER, 3, "a", "b")
        verify_physical_host_evidence(value)

        with self.assertRaisesRegex(ValueError, "signature"):
            verify_physical_host_evidence(
                replace(value, block_device_bytes=value.block_device_bytes + 1),
            )

    def test_peer_checkpoint_signature_detects_count_tampering(self):
        value = create_physical_peer_observation(
            credentials(4, "Peer"),
            observation_id="observation-before-success",
            qualification_id="qualification-physical-1",
            checkpoint=PhysicalPeerCheckpoint.BEFORE_REMOTE_SUCCESS,
            context_evidence_count=0,
            inspected_database_file_count=1,
            prompt_sha256=hashlib.sha256(b"Reply with exactly READY").hexdigest(),
            prompt_retained=False,
            captured_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        verify_physical_peer_observation(value)
        with self.assertRaisesRegex(ValueError, "signature"):
            verify_physical_peer_observation(
                replace(value, context_evidence_count=1),
            )

    def test_complete_report_cross_checks_remote_and_recovery_evidence(self):
        report = qualification_report()
        self.assertTrue(phase21_7_passed(report))

        rejected = (
            ("remote_success", "peer_device_id", "device-forged"),
            ("remote_success", "requester_context_evidence_delta", 0),
            ("peer_loss_recovery", "remote_attempt_consumed", False),
            ("peer_loss_recovery", "peer_authenticated_after_restart", False),
            ("removal", "peer_state_absent", False),
        )
        for section, name, value in rejected:
            with self.subTest(section=section, name=name):
                changed = json.loads(json.dumps(report))
                changed[section][name] = value
                self.assertFalse(phase21_7_passed(changed))

    def test_malformed_report_fails_closed(self):
        self.assertFalse(phase21_7_passed({}))
        self.assertFalse(physical_hosts_valid({}, {}))

    def test_report_assembler_uses_component_evidence(self):
        report = qualification_report()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = {
                "requester-host": report["requester_host"],
                "peer-host": report["peer_host"],
                "pairing": report["pairing"],
                "remote-success": report["remote_success"],
                "peer-loss-recovery": report["peer_loss_recovery"],
                "requester-diagnosis": {
                    "role": "requester", "healthy": True,
                },
                "peer-diagnosis": {
                    "role": "expert_peer", "healthy": True,
                },
                "requester-removal": {
                    "role": "requester", "install_absent": True,
                    "state_absent": True,
                },
                "peer-removal": {
                    "role": "expert_peer", "install_absent": True,
                    "state_absent": True,
                },
            }
            arguments = ["assemble_report.py"]
            for name, value in inputs.items():
                path = root / f"{name}.json"
                path.write_text(json.dumps(value), encoding="utf-8")
                arguments.extend((f"--{name}", str(path)))
            output = root / "report.json"
            arguments.extend(("--output", str(output)))
            with patch("sys.argv", arguments):
                self.assertEqual(0, assemble_report())
            assembled = json.loads(output.read_text("utf-8"))
            self.assertTrue(assembled["passed"])
            self.assertTrue(phase21_7_passed(assembled))

    def test_same_host_tooling_smoke_cannot_become_physical_evidence(self):
        report = qualification_report()
        report.update({
            "phase": "21.7-tooling-smoke",
            "same_physical_host": True,
            "physical_gate_satisfied": False,
            "peer_host": host(PhysicalHostRole.EXPERT_PEER, 2, "a", "b"),
            "requester_diagnosis_healthy": True,
            "peer_diagnosis_healthy": True,
            "complete_removal": True,
        })
        self.assertTrue(phase21_7_tooling_smoke_passed(report))
        self.assertFalse(phase21_7_passed(report))


def signed_host(
    role: PhysicalHostRole, seed: int, machine: str, anchor: str,
):
    device = credentials(seed, role.value)
    return create_physical_host_evidence(
        device,
        evidence_id="physical-host-" + role.value,
        qualification_id="qualification-physical-1",
        role=role,
        machine_id_sha256=machine * 64,
        hardware_anchor_kind=HardwareAnchorKind.DMI_PRODUCT_UUID,
        hardware_anchor_sha256=anchor * 64,
        hostname_sha256=("e" if role is PhysicalHostRole.REQUESTER else "f") * 64,
        kernel_release="6.8.0",
        architecture="x86_64",
        virtualization_kind="none",
        physical_host=True,
        cpu_threads=24,
        memory_bytes=64 * 1024**3,
        block_device_bytes=2 * 1024**4,
        network_interface_count=1,
        non_loopback_address_sha256=(("1" if seed == 1 else "2") * 64,),
        release_id="phase21-physical",
        signer_key_id="physical-key",
        release_manifest_sha256="9" * 64,
        release_component_count=7,
        installation_healthy=True,
        captured_at=datetime(2026, 7, 17, tzinfo=UTC),
    )


def credentials(seed: int, display_name: str):
    key = Ed25519PrivateKey.from_private_bytes(bytes((seed,)) * 32)
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    fingerprint = hashlib.sha256(public).hexdigest()
    identity = DeviceIdentity(
        "device-" + fingerprint[:24], display_name,
        base64.b64encode(public).decode("ascii"), fingerprint,
    )
    return SimpleNamespace(identity=identity, identity_key=key)


def host(role: PhysicalHostRole, seed: int, machine: str, anchor: str) -> dict:
    return json.loads(dumps_document(signed_host(role, seed, machine, anchor)))


def qualification_report() -> dict:
    requester = host(PhysicalHostRole.REQUESTER, 1, "a", "b")
    peer = host(PhysicalHostRole.EXPERT_PEER, 2, "c", "d")
    requester_payload = requester["payload"]
    peer_payload = peer["payload"]
    requester_id = requester_payload["device_id"]
    peer_id = peer_payload["device_id"]
    ready = hashlib.sha256(b"READY").hexdigest()
    success_verification = "verification-success"
    success_evidence = "remote-evidence-success"
    loss_verification = "verification-loss"
    recovery_evidence = "remote-recovery-loss"
    acceptance = "7" * 64
    success_plan = "remote-plan-success"
    loss_plan = "remote-plan-loss"
    return {
        "phase": "21.7",
        "qualification_id": requester_payload["qualification_id"],
        "release_id": requester_payload["release_id"],
        "signer_key_id": requester_payload["signer_key_id"],
        "release_manifest_sha256": requester_payload["release_manifest_sha256"],
        "requester_host": requester,
        "peer_host": peer,
        "pairing": {
            "requester_device_id": requester_id,
            "peer_device_id": peer_id,
            "pairing_codes_match": True,
            "requester_enrollment_active": True,
            "peer_enrollment_active": True,
            "requester_enrollment_id": "enrollment-requester",
            "peer_enrollment_id": "enrollment-peer",
            "ceremony_sha256": "5" * 64,
        },
        "remote_success": {
            "request_id": "physical-success",
            "requester_device_id": requester_id,
            "peer_device_id": peer_id,
            "mutual_tls_version": "TLSv1.3",
            "remote_model": "gemma4:26b",
            "verified": True,
            "content": "READY",
            "requester_context_evidence_delta": 1,
            "peer_context_evidence_delta": 1,
            "unauthorized_context_count": 0,
            "requester_prompt_retained": False,
            "peer_prompt_retained": False,
            "remote_execution_evidence": {
                "contract_version": "fam.fabric.remote-execution-evidence/v1alpha1",
                "evidence_id": success_evidence,
                "request_id": "physical-success",
                "peer_device_id": peer_id,
                "model_ref": "gemma4:26b",
                "disposition": "released",
                "verification_outcome": "passed",
                "verification_run_id": success_verification,
                "budget_reservation_id": "budget-success",
                "remote_plan_id": success_plan,
                "result_content_sha256": ready,
                "raw_content_retained": False,
                "partial_output_retained": False,
            },
            "remote_budget_reservation": {
                "reservation_id": "budget-success",
                "kind": "remote",
                "route_plan_id": success_plan,
                "acceptance_sha256": "6" * 64,
            },
            "verification_run": {
                "verification_id": success_verification,
                "status": "passed",
                "effective_trust": "signed",
            },
            "terminal_result": {
                "request_id": "physical-success",
                "status": "verified",
                "verified": True,
                "content": "READY",
                "evidence_ids": [success_evidence, success_verification],
            },
        },
        "peer_loss_recovery": {
            "request_id": "physical-loss",
            "requester_device_id": requester_id,
            "peer_device_id": peer_id,
            "peer_stopped_before_request": True,
            "peer_port_closed": True,
            "remote_attempt_consumed": True,
            "remote_execution_evidence": None,
            "verified": True,
            "content": "READY",
            "requester_context_evidence_delta": 0,
            "peer_context_evidence_delta": 0,
            "requester_prompt_retained": False,
            "peer_prompt_retained": False,
            "peer_authenticated_after_restart": True,
            "remote_recovery_evidence": {
                "contract_version": "fam.fabric.remote-recovery-evidence/v1alpha1",
                "evidence_id": recovery_evidence,
                "request_id": "physical-loss",
                "failure": "disconnected",
                "disposition": "recovered",
                "unchanged_acceptance": True,
                "local_retry_allowed": True,
                "accepted_contract_sha256": acceptance,
                "observed_contract_sha256": acceptance,
                "remote_plan_id": loss_plan,
                "remote_budget_reservation_id": "budget-loss-remote",
                "local_budget_reservation_id": "budget-loss-local",
                "partial_output_retained": False,
                "raw_content_retained": False,
            },
            "remote_budget_reservation": {
                "reservation_id": "budget-loss-remote", "kind": "remote",
                "acceptance_sha256": acceptance, "route_plan_id": loss_plan,
            },
            "local_budget_reservation": {
                "reservation_id": "budget-loss-local", "kind": "local_recovery",
                "acceptance_sha256": acceptance, "route_plan_id": loss_plan,
            },
            "verification_run": {
                "verification_id": loss_verification,
                "status": "passed", "effective_trust": "signed",
            },
            "terminal_result": {
                "request_id": "physical-loss", "status": "verified",
                "verified": True, "content": "READY",
                "evidence_ids": [recovery_evidence, loss_verification],
            },
        },
        "diagnoses": {"requester_healthy": True, "peer_healthy": True},
        "removal": {
            "requester_install_absent": True, "peer_install_absent": True,
            "requester_state_absent": True, "peer_state_absent": True,
        },
        "raw_prompt_retained": False,
        "unauthorized_context_count": 0,
    }


if __name__ == "__main__":
    unittest.main()
