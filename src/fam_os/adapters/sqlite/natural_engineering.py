"""Restart-safe natural-language engineering proposals."""

import sqlite3
from pathlib import Path
from threading import RLock

from fam_os.core.engineering import NaturalLanguageEngineeringProposal
from fam_os.adapters.sqlite.natural_engineering_serialization import (
    proposal_from_row, proposal_from_secure_payload, proposal_values,
    secure_payload,
)


class SQLiteNaturalEngineeringProposalStore:
    def __init__(self, path: Path, codec=None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path, check_same_thread=False)
        self._lock = RLock()
        self._codec = codec
        if codec is None:
            self._prepare_legacy_table(create=True)
        else:
            self._database.execute(
                "CREATE TABLE IF NOT EXISTS natural_engineering_proposals_secure ("
                "proposal_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, "
                "status TEXT NOT NULL CHECK(status IN ('proposed','activated')), "
                "activation_state TEXT NOT NULL DEFAULT 'idle', failure_code TEXT, "
                "record_ciphertext TEXT NOT NULL)"
            )
            if self._legacy_exists():
                self._prepare_legacy_table(create=False)
                self._migrate_legacy_records()
        self._database.execute(
            f"UPDATE {self._table} SET activation_state='interrupted' "
            "WHERE status='proposed' AND activation_state='running'"
        )
        self._database.commit()

    def put(self, proposal: NaturalLanguageEngineeringProposal) -> None:
        if self._codec is not None:
            self._put_secure(proposal)
            return
        values = proposal_values(proposal)
        with self._lock, self._database:
            row = self._database.execute(
                "SELECT prompt_sha256,grant_document,definition_document,"
                "budget_json,separate_authorities_json "
                "FROM natural_engineering_proposals WHERE proposal_id=?",
                (proposal.proposal_id,),
            ).fetchone()
            if row is not None:
                if tuple(row) != values[2:]:
                    raise RuntimeError("natural engineering proposal already exists")
                return
            self._database.execute(
                "INSERT INTO natural_engineering_proposals("
                "proposal_id,owner_id,prompt_sha256,grant_document,"
                "definition_document,budget_json,separate_authorities_json,status) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (*values, "proposed"),
            )

    def get(self, proposal_id: str) -> NaturalLanguageEngineeringProposal | None:
        if self._codec is not None:
            with self._lock:
                row = self._database.execute(
                    "SELECT record_ciphertext FROM "
                    "natural_engineering_proposals_secure WHERE proposal_id=?",
                    (proposal_id,),
                ).fetchone()
            return None if row is None else self._decode(proposal_id, row[0])
        with self._lock:
            row = self._database.execute(
                "SELECT prompt_sha256,grant_document,definition_document,"
                "budget_json,separate_authorities_json "
                "FROM natural_engineering_proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        return proposal_from_row(proposal_id, row)

    def activate(self, proposal_id: str) -> bool:
        """Claim one activation attempt; retained for the proposal-store port."""
        return self.begin_activation(proposal_id)

    def begin_activation(self, proposal_id: str) -> bool:
        with self._lock, self._database:
            changed = self._database.execute(
                f"UPDATE {self._table} SET activation_state='running',"
                "failure_code=NULL WHERE proposal_id=? AND status='proposed' "
                "AND activation_state IN ('idle','interrupted')",
                (proposal_id,),
            ).rowcount
        return changed == 1

    def mark_activated(self, proposal_id: str) -> None:
        self._transition(
            proposal_id, "status='activated',activation_state='ready',failure_code=NULL",
            "running",
        )

    def mark_interrupted(self, proposal_id: str, failure_code: str) -> None:
        self._transition(
            proposal_id, "activation_state='interrupted',failure_code=?",
            "running", failure_code,
        )

    def mark_failed(self, proposal_id: str, failure_code: str) -> None:
        self._transition(
            proposal_id, "activation_state='failed',failure_code=?",
            "running", failure_code,
        )

    def decline(self, proposal_id: str, failure_code: str) -> None:
        with self._lock, self._database:
            changed = self._database.execute(
                f"UPDATE {self._table} SET "
                "activation_state='failed',failure_code=? WHERE proposal_id=? "
                "AND status='proposed' AND activation_state IN ('idle','interrupted')",
                (failure_code, proposal_id),
            ).rowcount
        if changed != 1:
            raise RuntimeError("natural engineering proposal cannot be declined")

    def status(self, proposal_id: str) -> str | None:
        with self._lock:
            row = self._database.execute(
                f"SELECT status,activation_state FROM {self._table} "
                "WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        if row[0] == "activated":
            return "activated"
        return {
            "idle": "proposed", "running": "activating",
            "interrupted": "interrupted", "failed": "failed",
        }[row[1]]

    def failure(self, proposal_id: str) -> str | None:
        with self._lock:
            row = self._database.execute(
                f"SELECT failure_code FROM {self._table} "
                "WHERE proposal_id=?", (proposal_id,),
            ).fetchone()
        return None if row is None else row[0]

    def close(self) -> None:
        with self._lock:
            self._database.close()

    def _transition(self, proposal_id, assignment, expected, *values) -> None:
        with self._lock, self._database:
            changed = self._database.execute(
                f"UPDATE {self._table} SET {assignment} "
                "WHERE proposal_id=? AND status='proposed' AND activation_state=?",
                (*values, proposal_id, expected),
            ).rowcount
        if changed != 1:
            raise RuntimeError("natural engineering activation state changed")

    @property
    def _table(self) -> str:
        return (
            "natural_engineering_proposals_secure"
            if self._codec is not None else "natural_engineering_proposals"
        )

    def _put_secure(self, proposal) -> None:
        payload = secure_payload(proposal)
        with self._lock, self._database:
            row = self._database.execute(
                "SELECT owner_id,record_ciphertext FROM "
                "natural_engineering_proposals_secure WHERE proposal_id=?",
                (proposal.proposal_id,),
            ).fetchone()
            if row is not None:
                if row[0] != proposal.grant.owner_id or self._decode(
                    proposal.proposal_id, row[1],
                ) != proposal:
                    raise RuntimeError("natural engineering proposal already exists")
                return
            self._database.execute(
                "INSERT INTO natural_engineering_proposals_secure VALUES "
                "(?,?,?,? ,?,?)",
                (
                    proposal.proposal_id, proposal.grant.owner_id, "proposed",
                    "idle", None,
                    self._codec.encode(proposal.proposal_id, payload),
                ),
            )

    def _decode(self, proposal_id, token):
        return proposal_from_secure_payload(
            proposal_id, self._codec.decode(proposal_id, token),
        )

    def _legacy_exists(self) -> bool:
        return self._database.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            ("natural_engineering_proposals",),
        ).fetchone() is not None

    def _prepare_legacy_table(self, *, create: bool) -> None:
        if create:
            self._database.execute(
                "CREATE TABLE IF NOT EXISTS natural_engineering_proposals ("
                "proposal_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, "
                "prompt_sha256 TEXT NOT NULL, grant_document TEXT NOT NULL, "
                "definition_document TEXT NOT NULL, budget_json TEXT NOT NULL, "
                "separate_authorities_json TEXT NOT NULL, "
                "status TEXT NOT NULL CHECK(status IN ('proposed','activated')))"
            )
        columns = {
            row[1] for row in self._database.execute(
                "PRAGMA table_info(natural_engineering_proposals)"
            ).fetchall()
        }
        if "activation_state" not in columns:
            self._database.execute(
                "ALTER TABLE natural_engineering_proposals ADD COLUMN "
                "activation_state TEXT NOT NULL DEFAULT 'idle'"
            )
        if "failure_code" not in columns:
            self._database.execute(
                "ALTER TABLE natural_engineering_proposals ADD COLUMN failure_code TEXT"
            )

    def _migrate_legacy_records(self) -> None:
        self._database.execute("PRAGMA secure_delete=ON")
        rows = self._database.execute(
            "SELECT proposal_id,owner_id,prompt_sha256,grant_document,"
            "definition_document,budget_json,separate_authorities_json,status,"
            "activation_state,failure_code FROM natural_engineering_proposals"
        ).fetchall()
        for row in rows:
            proposal = proposal_from_row(row[0], row[2:7])
            if proposal.grant.owner_id != row[1]:
                raise PermissionError("legacy natural engineering owner is invalid")
            existing = self._database.execute(
                "SELECT record_ciphertext FROM natural_engineering_proposals_secure "
                "WHERE proposal_id=?", (row[0],),
            ).fetchone()
            if existing is not None and self._decode(row[0], existing[0]) != proposal:
                raise RuntimeError("secure natural engineering migration conflicts")
            if existing is None:
                self._database.execute(
                    "INSERT INTO natural_engineering_proposals_secure VALUES "
                    "(?,?,?,?,?,?)",
                    (
                        row[0], row[1], row[7], row[8], row[9],
                        self._codec.encode(row[0], secure_payload(proposal)),
                    ),
                )
        if rows:
            self._database.execute("DELETE FROM natural_engineering_proposals")
