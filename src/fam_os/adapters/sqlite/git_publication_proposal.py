"""Encrypted restart-safe Git publication proposals and approval intents."""

import sqlite3
from pathlib import Path
from threading import RLock

from fam_os.core.engineering.git_delivery import GitPublicationReceipt
from fam_os.core.engineering.git_publication_proposal import GitPublicationProposal


class SQLiteGitPublicationProposalStore:
    def __init__(self, path: Path, proposal_codec, receipt_codec) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path, check_same_thread=False)
        self._database.execute("PRAGMA journal_mode=WAL")
        self._database.execute("PRAGMA synchronous=FULL")
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS git_publication_proposals ("
            "proposal_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, "
            "status TEXT NOT NULL CHECK(status IN "
            "('prepared','approval_intent','published','declined','recovery_required')), "
            "proposal_ciphertext TEXT NOT NULL, receipt_ciphertext TEXT)"
        )
        self._database.execute(
            "UPDATE git_publication_proposals SET status='recovery_required' "
            "WHERE status='approval_intent'"
        )
        self._database.commit()
        self._proposal_codec = proposal_codec
        self._receipt_codec = receipt_codec
        self._lock = RLock()

    def put(self, proposal: GitPublicationProposal) -> None:
        encoded = self._proposal_codec.encode(proposal.proposal_id, proposal)
        with self._lock, self._database:
            task_row = self._database.execute(
                "SELECT proposal_id FROM git_publication_proposals WHERE task_id=?",
                (proposal.task_id,),
            ).fetchone()
            if task_row is not None and task_row[0] != proposal.proposal_id:
                raise RuntimeError("Git publication task already has a proposal")
            row = self._database.execute(
                "SELECT proposal_ciphertext FROM git_publication_proposals "
                "WHERE proposal_id=?", (proposal.proposal_id,),
            ).fetchone()
            if row is not None:
                if self._proposal_codec.decode(proposal.proposal_id, row[0]) != proposal:
                    raise RuntimeError("Git publication proposal already differs")
                return
            self._database.execute(
                "INSERT INTO git_publication_proposals VALUES (?,?,?,?,NULL)",
                (proposal.proposal_id, proposal.task_id, "prepared", encoded),
            )

    def for_task(self, task_id: str) -> GitPublicationProposal | None:
        with self._lock:
            rows = self._database.execute(
                "SELECT proposal_id,proposal_ciphertext "
                "FROM git_publication_proposals WHERE task_id=?", (task_id,),
            ).fetchall()
        if len(rows) > 1:
            raise RuntimeError("Git publication task proposal identity is ambiguous")
        return (
            None if not rows
            else self._proposal_codec.decode(rows[0][0], rows[0][1])
        )

    def get(self, proposal_id: str) -> GitPublicationProposal | None:
        with self._lock:
            row = self._database.execute(
                "SELECT proposal_ciphertext FROM git_publication_proposals "
                "WHERE proposal_id=?", (proposal_id,),
            ).fetchone()
        return (
            None if row is None
            else self._proposal_codec.decode(proposal_id, row[0])
        )

    def status(self, proposal_id: str) -> str | None:
        with self._lock:
            row = self._database.execute(
                "SELECT status FROM git_publication_proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
        return None if row is None else row[0]

    def begin_approval(self, proposal_id: str) -> bool:
        with self._lock, self._database:
            changed = self._database.execute(
                "UPDATE git_publication_proposals SET status='approval_intent' "
                "WHERE proposal_id=? AND status='prepared'", (proposal_id,),
            ).rowcount
        return changed == 1

    def decline(self, proposal_id: str) -> bool:
        with self._lock, self._database:
            changed = self._database.execute(
                "UPDATE git_publication_proposals SET status='declined' "
                "WHERE proposal_id=? AND status='prepared'", (proposal_id,),
            ).rowcount
        return changed == 1

    def mark_published(
        self, proposal_id: str, receipt: GitPublicationReceipt,
    ) -> None:
        encoded = self._receipt_codec.encode(proposal_id, receipt)
        with self._lock, self._database:
            changed = self._database.execute(
                "UPDATE git_publication_proposals SET status='published',"
                "receipt_ciphertext=? WHERE proposal_id=? "
                "AND status='approval_intent'", (encoded, proposal_id),
            ).rowcount
        if changed != 1:
            raise RuntimeError("Git publication proposal state changed")

    def mark_recovery_required(self, proposal_id: str) -> None:
        with self._lock, self._database:
            changed = self._database.execute(
                "UPDATE git_publication_proposals SET status='recovery_required' "
                "WHERE proposal_id=? AND status='approval_intent'", (proposal_id,),
            ).rowcount
        if changed != 1:
            raise RuntimeError("Git publication proposal state changed")

    def receipt(self, proposal_id: str) -> GitPublicationReceipt | None:
        with self._lock:
            row = self._database.execute(
                "SELECT receipt_ciphertext FROM git_publication_proposals "
                "WHERE proposal_id=? AND status='published'", (proposal_id,),
            ).fetchone()
        return (
            None if row is None or row[0] is None
            else self._receipt_codec.decode(proposal_id, row[0])
        )

    def close(self) -> None:
        with self._lock:
            self._database.close()
