"""Compose proposal discovery with fail-safe specialist regression rollback."""

from __future__ import annotations


class ProductFactoryFailureObserver:
    def __init__(self, discovery, lifecycle=None) -> None:
        self._discovery = discovery
        self._lifecycle = lifecycle

    def verification_failed(self, record, decision) -> None:
        self._discovery.verification_failed(record, decision)
        if self._lifecycle is not None:
            self._lifecycle.observe_production_regression(record, decision)
