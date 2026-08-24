"""Deterministic interrupted-launch recovery for process environments."""

import hashlib

from fam_os.adapters.integration.docker_support import runtime_name
from fam_os.adapters.integration.process_state import ProcessEnvironmentState
from fam_os.adapters.integration.retained_artifacts import capture_retained_artifacts
from fam_os.core.engineering import (
    IntegrationEnvironmentReceipt, IntegrationEnvironmentStatus,
)


def recover_process_environment(
    plan, root, permit, *, stop, secrets, clock, identifier,
):
    state = ProcessEnvironmentState(root, plan.environment_id)
    try:
        document = state.load()
    except FileNotFoundError:
        document = {"units": [], "secret_roots": []}
        has_state = False
    else:
        has_state = True
    expected_units = tuple(
        runtime_name("process", plan.environment_id + ":" + item.service_id)
        for item in plan.services
    )
    units = tuple(dict.fromkeys(tuple(document["units"]) + expected_units))
    expected_roots = tuple(
        _secret_relative_root(plan.environment_id, item.service_id)
        for item in plan.services if item.secret_refs
    )
    roots = tuple(dict.fromkeys(
        tuple(document["secret_roots"]) + expected_roots
    ))
    stop(units)
    secret_evidence = secrets.cleanup(root, roots)
    artifacts = capture_retained_artifacts(
        root, plan.retained_artifact_paths,
        plan.resource_impact.max_changed_bytes,
    )
    if has_state:
        state.finish("interrupted_recovered")
    instant = clock()
    return IntegrationEnvironmentReceipt(
        identifier(), plan.environment_id, permit.permit_id,
        IntegrationEnvironmentStatus.CLEANED, instant, instant, (), artifacts,
        tuple(f"recovery-probed-unit:{item}" for item in units) + secret_evidence,
    )


def _secret_relative_root(environment_id, service_id):
    identity = hashlib.sha256(
        f"{environment_id}:{service_id}".encode(),
    ).hexdigest()[:24]
    return f".fam/secret-injection/process-{identity}"
