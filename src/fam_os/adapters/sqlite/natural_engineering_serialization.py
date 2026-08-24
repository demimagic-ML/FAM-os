"""Canonical persistence encoding for natural engineering proposals."""

import json

from fam_os.core.engineering import (
    EngineeringAuthority,
    EngineeringAuthorityGrant,
    EngineeringLoopBudget,
    EngineeringTaskDefinition,
    NaturalLanguageEngineeringProposal,
)
from fam_os.schemas import dumps_document, loads_document


STORAGE_VERSION = "fam.product.natural-engineering-record/v2"
_LEGACY_STORAGE_VERSION = "fam.product.natural-engineering-record/v1"


def proposal_values(proposal: NaturalLanguageEngineeringProposal) -> tuple:
    budget = {
        name: getattr(proposal.budget, name)
        for name in (
            "maximum_tokens", "maximum_wall_seconds", "maximum_commands",
            "maximum_network_bytes", "maximum_files", "maximum_storage_bytes",
        )
    }
    return (
        proposal.proposal_id, proposal.grant.owner_id, proposal.prompt_sha256,
        dumps_document(proposal.grant), dumps_document(proposal.definition),
        json.dumps(budget, sort_keys=True, separators=(",", ":")),
        json.dumps({
            "authorities": [
                item.value for item in proposal.separately_confirmed_authorities
            ],
            "integration_resource_grant_document": (
                None if proposal.integration_resource_grant is None else
                dumps_document(proposal.integration_resource_grant)
            ),
        }, sort_keys=True, separators=(",", ":")),
    )


def proposal_from_row(proposal_id: str, row) -> NaturalLanguageEngineeringProposal:
    grant, definition = loads_document(row[1]), loads_document(row[2])
    if not isinstance(grant, EngineeringAuthorityGrant) or not isinstance(
        definition, EngineeringTaskDefinition,
    ):
        raise TypeError("persisted natural engineering proposal is invalid")
    separate = json.loads(row[4])
    if isinstance(separate, list):
        authorities = separate
        resource_grant = None
    elif isinstance(separate, dict) and set(separate) == {
        "authorities", "integration_resource_grant_document",
    }:
        authorities = separate["authorities"]
        document = separate["integration_resource_grant_document"]
        resource_grant = None if document is None else loads_document(document)
        if resource_grant is not None and not isinstance(
            resource_grant, EngineeringAuthorityGrant,
        ):
            raise TypeError(
                "persisted natural integration resource grant is invalid"
            )
    else:
        raise TypeError("persisted natural engineering authority scope is invalid")
    return NaturalLanguageEngineeringProposal(
        proposal_id, row[0], grant, definition,
        EngineeringLoopBudget(**json.loads(row[3])),
        tuple(EngineeringAuthority(item) for item in authorities),
        resource_grant,
    )


def secure_payload(proposal: NaturalLanguageEngineeringProposal) -> dict:
    values = proposal_values(proposal)
    return {
        "storage_version": STORAGE_VERSION,
        "prompt_sha256": values[2], "grant_document": values[3],
        "definition_document": values[4], "budget_json": values[5],
        "separate_authorities_json": values[6],
    }


def proposal_from_secure_payload(proposal_id: str, payload: dict):
    required = {
        "storage_version", "prompt_sha256", "grant_document",
        "definition_document", "budget_json", "separate_authorities_json",
    }
    if (
        set(payload) != required
        or payload["storage_version"] not in {
            _LEGACY_STORAGE_VERSION, STORAGE_VERSION,
        }
    ):
        raise TypeError("encrypted natural engineering proposal is invalid")
    return proposal_from_row(proposal_id, (
        payload["prompt_sha256"], payload["grant_document"],
        payload["definition_document"], payload["budget_json"],
        payload["separate_authorities_json"],
    ))
