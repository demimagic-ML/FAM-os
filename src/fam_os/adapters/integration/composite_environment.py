"""All-or-cleaned orchestration across Docker and process backends."""

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from fam_os.adapters.integration.composite_state import CompositeEnvironmentState
from fam_os.adapters.integration.composite_network import (
    CompositeNetworkLifecycle, network_evidence,
)
from fam_os.adapters.integration.composite_planning import (
    ordered_service_receipts as _ordered_service_receipts,
    partitions as _partitions,
    subreceipt as _subreceipt,
)
from fam_os.adapters.integration.retained_artifacts import capture_retained_artifacts
from fam_os.core.engineering import (
    IntegrationEnvironmentReceipt, IntegrationEnvironmentStatus,
)


class MixedIntegrationEnvironmentAdapter:
    def __init__(self, docker, process, identifier=None, clock=None, network=None) -> None:
        if docker is None or process is None:
            raise ValueError("mixed integration adapter requires both backends")
        self._backends = {"docker": docker, "process": process}
        self._identifier = identifier or (lambda: str(uuid4()))
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._network = CompositeNetworkLifecycle(network)

    def launch(self, plan, candidate_root, permit, control):
        partitions = _partitions(plan)
        state = CompositeEnvironmentState(candidate_root, plan.environment_id)
        state.claim(tuple(name for name, _subplan in partitions))
        launched = []
        branch_permit, lease = permit, None
        try:
            branch_permit, lease = self._network.open(plan, permit, state)
            for name, subplan in partitions:
                receipt = self._backends[name].launch(
                    subplan, candidate_root, branch_permit, control,
                )
                launched.append((name, subplan, receipt))
                state.record_launched(name)
            receipts = tuple(item[2] for item in launched)
            usage = self._network.observe(lease)
        except BaseException as launch_error:
            errors = self._compensate(
                launched, candidate_root, branch_permit, permit, state,
            )
            if errors:
                state.finish("cleanup_required", terminal=False)
                raise RuntimeError(
                    "mixed integration launch compensation failed"
                ) from errors[-1]
            state.finish("failed_cleaned", terminal=True)
            raise launch_error
        state.finish("ready", terminal=False)
        return IntegrationEnvironmentReceipt(
            self._identifier(), plan.environment_id, permit.permit_id,
            IntegrationEnvironmentStatus.READY,
            min(item.started_at for item in receipts),
            max(item.completed_at for item in receipts),
            _ordered_service_receipts(plan, receipts), (), (),
            network_usage=usage,
        )

    def cleanup(self, plan, receipt, candidate_root, permit):
        return self._retire(
            plan, receipt, candidate_root, permit, reconcile=False,
        )

    def reconcile(self, plan, candidate_root, permit):
        return self._retire(
            plan, None, candidate_root, permit, reconcile=True,
        )

    def recover(self, plan, candidate_root, permit):
        """Recover every deterministic branch after a pre-result interruption."""
        partitions = _partitions(plan, retain=False)
        order = tuple(name for name, _subplan in partitions)
        state = CompositeEnvironmentState(candidate_root, plan.environment_id)
        try:
            document = state.load()
        except FileNotFoundError:
            state.claim(order)
            document = state.load()
        if tuple(document["backend_order"]) != order:
            raise PermissionError("composite recovery order does not match plan")
        launched = set(document["launched_backends"])
        for name in order:
            if name not in launched:
                state.record_launched(name)
        document = state.load()
        branch_permit = self._network.permit_from(document, permit)
        evidence = [
            item for name in reversed(order)
            for item in document["cleanup_evidence"].get(name, ())
        ]
        errors = []
        for name, subplan in reversed(partitions):
            if name in document["cleanup_evidence"]:
                continue
            try:
                result = self._backends[name].recover(
                    subplan, candidate_root, branch_permit,
                )
                evidence.extend(result.cleanup_evidence_ids)
                state.record_cleaned(name, result.cleanup_evidence_ids)
            except BaseException as error:
                errors.append(error)
        usage = None
        if not document["network_cleanup_evidence"]:
            try:
                usage = self._network.recover(plan, document, permit)
                ids = network_evidence(usage)
                if ids: state.record_network_cleaned(ids); evidence.extend(ids)
            except BaseException as error:
                errors.append(error)
        else:
            evidence.extend(document["network_cleanup_evidence"])
        if errors:
            state.finish("cleanup_required", terminal=False)
            raise RuntimeError("mixed interrupted launch recovery is incomplete") from errors[-1]
        artifacts = capture_retained_artifacts(
            candidate_root, plan.retained_artifact_paths,
            plan.resource_impact.max_changed_bytes,
        )
        instant = self._clock()
        final = IntegrationEnvironmentReceipt(
            self._identifier(), plan.environment_id, permit.permit_id,
            IntegrationEnvironmentStatus.CLEANED, instant, instant, (),
            artifacts, tuple(evidence),
            network_usage=usage,
        )
        state.finish("interrupted_recovered", terminal=True)
        return final

    def _retire(self, plan, receipt, root, permit, *, reconcile):
        partitions = _partitions(plan, retain=False)
        state = CompositeEnvironmentState(root, plan.environment_id)
        document = state.load()
        branch_permit = self._network.permit_from(document, permit)
        order = tuple(name for name, _subplan in partitions)
        if tuple(document["backend_order"]) != order:
            raise PermissionError("composite backend order does not match plan")
        if tuple(document["launched_backends"]) != order or document["terminal"]:
            raise PermissionError("composite active launch evidence is incomplete")
        cleaned = set(document["cleanup_evidence"])
        evidence = [
            item for name in reversed(order)
            for item in document["cleanup_evidence"].get(name, ())
        ]
        errors = []
        for name, subplan in reversed(partitions):
            if name in cleaned:
                continue
            try:
                if reconcile:
                    result = self._backends[name].reconcile(
                        subplan, root, branch_permit,
                    )
                else:
                    result = self._backends[name].cleanup(
                        subplan, _subreceipt(receipt, subplan), root, branch_permit,
                    )
                evidence.extend(result.cleanup_evidence_ids)
                state.record_cleaned(name, result.cleanup_evidence_ids)
            except BaseException as error:
                errors.append(error)
        usage = None
        if not document["network_cleanup_evidence"]:
            try:
                usage = self._network.close(document, permit)
                ids = network_evidence(usage)
                if ids: state.record_network_cleaned(ids); evidence.extend(ids)
            except BaseException as error:
                errors.append(error)
        else:
            evidence.extend(document["network_cleanup_evidence"])
        if errors:
            state.finish("cleanup_required", terminal=False)
            raise RuntimeError("mixed integration cleanup is incomplete") from errors[-1]
        artifacts = capture_retained_artifacts(
            root, plan.retained_artifact_paths,
            plan.resource_impact.max_changed_bytes,
        )
        instant = self._clock()
        if reconcile:
            instants, services = [instant, instant], ()
        else:
            instants, services = [receipt.started_at, instant], receipt.services
        final = IntegrationEnvironmentReceipt(
            self._identifier(), plan.environment_id, permit.permit_id,
            IntegrationEnvironmentStatus.CLEANED, instants[0], instants[1],
            services, artifacts, tuple(evidence),
            network_usage=usage,
        )
        state.finish("reconciled_cleaned" if reconcile else "cleaned", terminal=True)
        return final

    def _compensate(self, launched, root, branch_permit, permit, state):
        errors = []
        for name, subplan, receipt in reversed(launched):
            try:
                result = self._backends[name].cleanup(
                    replace(subplan, retained_artifact_paths=()),
                    receipt, root, branch_permit,
                )
                state.record_cleaned(name, result.cleanup_evidence_ids)
            except BaseException as error:
                errors.append(error)
        document = state.load()
        if not document["network_cleanup_evidence"]:
            try:
                usage = self._network.close(document, permit)
                ids = network_evidence(usage)
                if ids: state.record_network_cleaned(ids)
            except BaseException as error:
                errors.append(error)
        return errors

