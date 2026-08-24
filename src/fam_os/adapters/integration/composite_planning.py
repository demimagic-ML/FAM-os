"""Deterministic partitioning and receipt projection for mixed backends."""

from dataclasses import replace

from fam_os.core.engineering import EngineeringAuthority, IntegrationServiceKind


_CONTAINER = {IntegrationServiceKind.CONTAINER, IntegrationServiceKind.CLUSTER_CONTROL_PLANE}
_PROCESS = {
    IntegrationServiceKind.PROCESS, IntegrationServiceKind.API,
    IntegrationServiceKind.BROWSER,
}


def partitions(plan, *, retain=True):
    backend_by_service = {
        service.service_id: _backend(service.kind) for service in plan.services
    }
    dependencies = {"docker": set(), "process": set()}
    for service in plan.services:
        target = backend_by_service[service.service_id]
        dependencies[target].update(
            backend_by_service[item] for item in service.dependency_ids
            if backend_by_service[item] != target
        )
    present, order = set(backend_by_service.values()), []
    while present:
        ready = sorted(name for name in present if not dependencies[name] & present)
        if not ready:
            raise PermissionError("cross-backend integration dependencies contain a cycle")
        order.extend(ready); present -= set(ready)
    counts = {
        name: sum(value == name for value in backend_by_service.values())
        for name in order
    }
    memory = _weighted_shares(plan.maximum_memory_bytes, order, counts)
    cpu = _weighted_shares(plan.maximum_cpu_millis_per_second, order, counts)
    processes = _weighted_shares(plan.resource_impact.max_processes, order, counts)
    values = []
    for name in order:
        services = tuple(
            replace(service, dependency_ids=tuple(
                item for item in service.dependency_ids
                if backend_by_service[item] == name
            ))
            for service in plan.services
            if backend_by_service[service.service_id] == name
        )
        secret_refs = {item for service in services for item in service.secret_refs}
        expected = {EngineeringAuthority.EXECUTE}
        if plan.network_hosts: expected.add(EngineeringAuthority.NETWORK)
        if secret_refs: expected.add(EngineeringAuthority.SECRET_USE)
        values.append((name, replace(
            plan, services=services,
            required_authorities=tuple(
                item for item in EngineeringAuthority if item in expected
            ),
            retained_artifact_paths=(plan.retained_artifact_paths if retain else ()),
            maximum_memory_bytes=memory[name],
            maximum_cpu_millis_per_second=cpu[name],
            resource_impact=replace(
                plan.resource_impact, max_processes=processes[name],
            ),
        )))
    return tuple(values)


def ordered_service_receipts(plan, receipts):
    by_id = {item.service_id: item for receipt in receipts for item in receipt.services}
    if set(by_id) != {item.service_id for item in plan.services}:
        raise RuntimeError("mixed integration service evidence is incomplete")
    return tuple(by_id[item.service_id] for item in plan.services)


def subreceipt(receipt, subplan):
    service_ids = {item.service_id for item in subplan.services}
    return replace(
        receipt,
        services=tuple(item for item in receipt.services if item.service_id in service_ids),
        retained_artifacts=(), cleanup_evidence_ids=(),
    )


def _backend(kind):
    if kind in _CONTAINER: return "docker"
    if kind in _PROCESS: return "process"
    raise PermissionError("integration service backend is unavailable")


def _weighted_shares(total, order, counts):
    if total < len(order):
        raise PermissionError("mixed integration resource budget cannot be partitioned")
    denominator = sum(counts.values())
    values, remaining = {}, total
    for name in order[:-1]:
        share = max(1, total * counts[name] // denominator)
        values[name] = share; remaining -= share
    if remaining < 1:
        raise PermissionError("mixed integration resource budget cannot be partitioned")
    values[order[-1]] = remaining
    return values
