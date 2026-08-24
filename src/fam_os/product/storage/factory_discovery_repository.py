"""Owner-private append-only persistence for factory failure discovery."""

from __future__ import annotations

import sqlite3

from fam_os.expert_factory.failure_discovery import (
    FactoryCapabilityProposal,
    VerifiedFailureCluster,
    VerifiedFailureTrace,
)
from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract


class SqliteFactoryDiscoveryRepository:
    def __init__(self, database, cipher, owner_id: str) -> None:
        if not owner_id.strip():
            raise ValueError("factory repository owner must not be empty")
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def add_trace(self, trace: VerifiedFailureTrace) -> bool:
        return self._insert(
            "factory_failure_traces",
            (
                "owner_id", "trace_id", "verification_id", "family_id",
                "capability_id", "failed_requirement_id", "verifier_id",
                "observed_at", "payload_ciphertext",
            ),
            (
                self._owner_id, trace.trace_id, trace.verification_id,
                trace.family_id, trace.capability_id, trace.failed_requirement_id,
                trace.verifier_id, trace.observed_at.isoformat(),
                self._encrypt("factory-failure-trace", trace.trace_id, trace),
            ),
        )

    def add_cluster(self, cluster: VerifiedFailureCluster) -> bool:
        return self._insert(
            "factory_failure_clusters",
            (
                "owner_id", "cluster_id", "family_id", "observation_count",
                "last_observed_at", "payload_ciphertext",
            ),
            (
                self._owner_id, cluster.cluster_id, cluster.family_id,
                len(cluster.trace_ids), cluster.last_observed_at.isoformat(),
                self._encrypt("factory-failure-cluster", cluster.cluster_id, cluster),
            ),
        )

    def add_proposal(self, proposal: FactoryCapabilityProposal) -> bool:
        return self._insert(
            "factory_capability_proposals",
            (
                "owner_id", "proposal_id", "cluster_id", "family_id",
                "capability_id", "observation_count", "proposed_at",
                "payload_ciphertext",
            ),
            (
                self._owner_id, proposal.proposal_id, proposal.cluster_id,
                proposal.family_id, proposal.capability_id,
                proposal.observation_count, proposal.proposed_at.isoformat(),
                self._encrypt("factory-capability-proposal", proposal.proposal_id, proposal),
            ),
        )

    def traces(self, family_id: str | None = None) -> tuple[VerifiedFailureTrace, ...]:
        where, parameters = self._family_filter(family_id)
        rows = self._database.fetchall(
            "SELECT trace_id,payload_ciphertext FROM factory_failure_traces "
            f"WHERE owner_id=?{where} ORDER BY observed_at,trace_id",
            (self._owner_id, *parameters),
        )
        return tuple(
            self._decrypt("factory-failure-trace", row[0], row[1], VerifiedFailureTrace)
            for row in rows
        )

    def clusters(
        self, family_id: str | None = None,
    ) -> tuple[VerifiedFailureCluster, ...]:
        where, parameters = self._family_filter(family_id)
        rows = self._database.fetchall(
            "SELECT cluster_id,payload_ciphertext FROM factory_failure_clusters "
            f"WHERE owner_id=?{where} "
            "ORDER BY observation_count,last_observed_at,cluster_id",
            (self._owner_id, *parameters),
        )
        return tuple(
            self._decrypt(
                "factory-failure-cluster", row[0], row[1], VerifiedFailureCluster,
            )
            for row in rows
        )

    def proposals(
        self, family_id: str | None = None,
    ) -> tuple[FactoryCapabilityProposal, ...]:
        where, parameters = self._family_filter(family_id)
        rows = self._database.fetchall(
            "SELECT proposal_id,payload_ciphertext FROM factory_capability_proposals "
            f"WHERE owner_id=?{where} "
            "ORDER BY observation_count,proposed_at,proposal_id",
            (self._owner_id, *parameters),
        )
        return tuple(
            self._decrypt(
                "factory-capability-proposal", row[0], row[1],
                FactoryCapabilityProposal,
            )
            for row in rows
        )

    def latest_proposals(self) -> tuple[FactoryCapabilityProposal, ...]:
        latest: dict[str, FactoryCapabilityProposal] = {}
        for proposal in self.proposals():
            current = latest.get(proposal.family_id)
            if current is None or (
                proposal.observation_count, proposal.proposed_at, proposal.proposal_id
            ) > (
                current.observation_count, current.proposed_at, current.proposal_id
            ):
                latest[proposal.family_id] = proposal
        return tuple(latest[key] for key in sorted(latest))

    def _insert(self, table: str, columns, values) -> bool:
        placeholders = ",".join("?" for _ in columns)
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    f"INSERT INTO {table}({','.join(columns)}) VALUES ({placeholders})",
                    values,
                )
        except sqlite3.IntegrityError:
            return False
        return True

    @staticmethod
    def _family_filter(family_id: str | None) -> tuple[str, tuple[str, ...]]:
        if family_id is None:
            return "", ()
        if not family_id.strip():
            raise ValueError("factory family identity must not be empty")
        return " AND family_id=?", (family_id,)

    def _encrypt(self, kind: str, identifier: str, value: object) -> str:
        return encrypt_contract(self._cipher, self._owner_id, kind, identifier, value)

    def _decrypt(self, kind: str, identifier, token, expected):
        if not isinstance(identifier, str) or not isinstance(token, str):
            raise TypeError("stored factory discovery row is invalid")
        value = decrypt_contract(
            self._cipher, self._owner_id, kind, identifier, token, expected,
        )
        if not isinstance(value, expected):
            raise TypeError("stored factory discovery contract has an invalid type")
        return value
