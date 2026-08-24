"""Authoritative read-only Console projection over live product providers."""

from __future__ import annotations

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from fam_os.console.contracts import ConsoleItem, ConsoleSection, ConsoleSnapshot


class ProductConsoleProvider:
    """Build Console state from the same providers that execute product work."""

    def __init__(
        self, state_root: Path, release_id: str, *, storage,
        capacity=None, catalog=None, residency=None, repositories=None,
        document_indexes=None, session_memory=None, application_audit=None,
    ) -> None:
        self._state_root = state_root
        self._release_id = release_id
        self._storage = storage
        self._capacity = capacity
        self._catalog = catalog
        self._residency = residency
        self._repositories = repositories
        self._document_indexes = document_indexes
        self._session_memory = session_memory
        self._application_audit = application_audit

    def snapshot(self) -> ConsoleSnapshot:
        recovery = bool(self._storage.recovery_required)
        return ConsoleSnapshot(
            datetime.now(UTC), os.geteuid(), self._release_id,
            (
                self._safe("resources", "Resources", self._resources),
                self._safe("experts", "Experts", self._experts),
                self._safe("permissions", "Permissions", self._permissions),
                self._safe("memory", "Memory", self._memory),
                self._safe("audit", "Audit history", self._audit),
                self._recovery(),
            ),
            recovery,
        )

    def _resources(self) -> ConsoleSection:
        if self._capacity is None:
            raise RuntimeError("live capacity observer is unavailable")
        capacity = self._capacity.observe()
        disk = shutil.disk_usage(self._state_root)
        constrained = bool(capacity.reason_codes)
        items = (
            ConsoleItem(
                "cpu", "Logical CPUs", str(os.cpu_count() or 1), "healthy",
                "Live host inventory",
            ),
            ConsoleItem(
                "memory", "Schedulable memory",
                _bytes(capacity.schedulable_host_bytes),
                "attention" if constrained else "healthy",
                f"{_bytes(capacity.available_host_bytes)} available before reserve",
            ),
            ConsoleItem(
                "vram", "Schedulable VRAM",
                _bytes(capacity.schedulable_vram_bytes),
                "healthy" if capacity.available_vram_bytes else "inactive",
                f"{_bytes(capacity.available_vram_bytes)} observed",
            ),
            ConsoleItem(
                "storage", "Available storage", _bytes(disk.free), "healthy",
                "Live filesystem observation",
            ),
            ConsoleItem(
                "policy", "Maximum expert tier", capacity.maximum_expert_tier,
                "attention" if constrained else "healthy",
                ", ".join(capacity.reason_codes) or "No protective restriction active",
            ),
        )
        return ConsoleSection("resources", "Resources", items)

    def _experts(self) -> ConsoleSection:
        if self._catalog is None or self._residency is None:
            raise RuntimeError("live expert catalog or residency is unavailable")
        entries = self._catalog.entries()
        resident = self._residency.resident_models()
        signed = self._catalog.provenances()
        return ConsoleSection("experts", "Experts", (
            ConsoleItem(
                "enabled", "Enabled runtime experts", str(len(entries)), "healthy",
                ", ".join(item.model_ref for item in entries) or "No enabled models",
            ),
            ConsoleItem(
                "signed", "Signed expert bindings", str(len(signed)),
                "healthy" if signed else "attention",
                "Activated release catalog provenance",
            ),
            ConsoleItem(
                "resident", "Resident models", str(len(resident)),
                "healthy" if resident else "inactive",
                ", ".join(resident) or "No model currently resident",
            ),
        ))

    def _permissions(self) -> ConsoleSection:
        if self._repositories is None:
            raise RuntimeError("permission repository is unavailable")
        count = self._repositories.application_permissions.active_count(
            datetime.now(UTC),
        )
        return ConsoleSection("permissions", "Permissions", (
            ConsoleItem(
                "application-grants", "Active application grants", str(count),
                "healthy" if count else "inactive",
                "Current, unexpired grants from encrypted durable storage",
            ),
        ))

    def _memory(self) -> ConsoleSection:
        session_enabled = self._session_memory is not None
        indexes = (
            None if self._document_indexes is None
            else len(self._document_indexes.list())
        )
        return ConsoleSection("memory", "Memory", (
            ConsoleItem(
                "session", "Ephemeral session memory",
                "Enabled" if session_enabled else "Unavailable",
                "healthy" if session_enabled else "unavailable",
                "Process-local and non-persistent",
            ),
            ConsoleItem(
                "indexes", "Active document index grants",
                "Unavailable" if indexes is None else str(indexes),
                (
                    "unavailable" if indexes is None
                    else "healthy" if indexes else "inactive"
                ),
                "Current, unexpired grants from encrypted durable storage",
            ),
        ))

    def _audit(self) -> ConsoleSection:
        if self._repositories is None or self._application_audit is None:
            raise RuntimeError("authoritative audit providers are unavailable")
        verification = self._application_audit.verify()
        terminals = self._repositories.terminal_outcomes.result_count()
        return ConsoleSection("audit", "Audit history", (
            ConsoleItem(
                "terminal-results", "Durable terminal results", str(terminals),
                "healthy", "Encrypted terminal-outcome repository",
            ),
            ConsoleItem(
                "application-actions", "Verified application action records",
                str(verification.record_count),
                "healthy" if verification.passed else "attention",
                (
                    f"Chain head {verification.head_digest[:16]}"
                    if verification.passed
                    else f"Audit chain failed: {verification.reason_code}"
                ),
            ),
        ))

    def _recovery(self) -> ConsoleSection:
        enabled = bool(self._storage.recovery_required)
        return ConsoleSection("recovery", "Recovery", (
            ConsoleItem(
                "mode", "Recovery mode", "Enabled" if enabled else "Ready",
                "attention" if enabled else "healthy",
                self._storage.reason if enabled else "Secure storage is available",
            ),
        ))

    def _safe(self, section_id: str, title: str, source) -> ConsoleSection:
        try:
            return source()
        except Exception as error:
            return ConsoleSection(section_id, title, (
                ConsoleItem(
                    "state", "Live state", "Unavailable", "unavailable",
                    f"{type(error).__name__}: provider observation failed",
                ),
            ))


def _bytes(value: int) -> str:
    return f"{value / (1024 ** 3):.1f} GiB"
