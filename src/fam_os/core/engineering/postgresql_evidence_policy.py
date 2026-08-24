"""Exact PostgreSQL integration evidence admission at changeset preview."""


def postgresql_verification_evidence_ids(
    definition, preparation, changeset_id, evidence, environments,
) -> tuple[str, ...]:
    values = tuple(evidence)
    environment_by_id = {
        plan.environment_id: (plan, start, cleanup)
        for plan, start, cleanup in environments
    }
    for plan, receipt in values:
        linked = environment_by_id.get(plan.environment_id)
        if linked is None:
            raise ValueError(
                "PostgreSQL verification lacks its integration environment evidence"
            )
        environment, start, cleanup = linked
        services = tuple(
            item for item in environment.services
            if item.service_id == plan.service_id
        )
        service_receipts = tuple(
            item for item in start.receipt.services
            if item.service_id == plan.service_id
        )
        if (
            plan.task_id != definition.task.task_id
            or plan.candidate_id != preparation.candidate.candidate_id
            or plan.approved_changeset_id != changeset_id
            or plan.production
            or receipt.plan_id != plan.plan_id
            or receipt.task_id != plan.task_id
            or receipt.candidate_id != plan.candidate_id
            or receipt.environment_id != plan.environment_id
            or receipt.service_id != plan.service_id
            or receipt.permit_id != start.permit.permit_id
            or not receipt.passed
            or not receipt.backup_encrypted
            or receipt.applied_asset_ids
            != tuple(item.asset_id for item in plan.migration_assets)
            or len(services) != 1
            or len(service_receipts) != 1
            or service_receipts[0].runtime_id != receipt.runtime_id
            or services[0].image_sha256 != service_receipts[0].image_sha256
            or cleanup.environment_id != plan.environment_id
            or cleanup.permit_id != receipt.permit_id
            or cleanup.status.value != "cleaned"
        ):
            raise ValueError("PostgreSQL verification evidence is not exact")
    identities = tuple(receipt.receipt_id for _plan, receipt in values)
    if len(set(identities)) != len(identities):
        raise ValueError("PostgreSQL verification evidence is duplicated")
    return identities
