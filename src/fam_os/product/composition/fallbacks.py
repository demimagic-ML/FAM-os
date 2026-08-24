"""Installed lifecycle for explicit accessibility and screen/input fallbacks."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fam_os.adapters.linux.accessibility import (
    AccessibilityBridgePolicy, GiAtspiProvider, LinuxAccessibilityBridge,
    build_accessibility_registration,
)
from fam_os.adapters.linux.screen_input.bridge import ScreenInputBridge
from fam_os.adapters.linux.screen_input.catalog import build_screen_input_registration
from fam_os.adapters.linux.screen_input.policy import ScreenInputPolicy
from fam_os.adapters.linux.screen_input.x11_inspector import X11InspectorSettings
from fam_os.adapters.linux.screen_input.x11_provider import X11ScreenInputProvider
from fam_os.product.composition.fallback_policy import (
    ProductFallbackPolicy, parse_fallback_policy,
)
from fam_os.product.composition.fallback_transports import (
    AccessibilityFallbackTransport, ScreenInputFallbackTransport,
)


class ProductFallbacks:
    def __init__(
        self, registry, policy=ProductFallbackPolicy(),
        accessibility_provider_factory=GiAtspiProvider,
        screen_provider_factory=None,
    ) -> None:
        self._registry = registry
        self._policy = policy
        self._accessibility_factory = accessibility_provider_factory
        self._screen_factory = screen_provider_factory or _x11_provider
        self._transports: dict[str, Any] = {}
        self._issues: dict[str, str | None] = {
            "accessibility": "not_started" if policy.accessibility.enabled else "disabled",
            "screen_input": "not_started" if policy.screen_input.enabled else "disabled",
        }
        self._started = False

    @classmethod
    def from_file(
        cls, registry, path: Path, accessibility_provider_factory=GiAtspiProvider,
        screen_provider_factory=None,
    ) -> "ProductFallbacks":
        if not path.exists():
            return cls(
                registry, accessibility_provider_factory=accessibility_provider_factory,
                screen_provider_factory=screen_provider_factory,
            )
        _require_private(path)
        policy = parse_fallback_policy(json.loads(path.read_text(encoding="utf-8")))
        return cls(
            registry, policy, accessibility_provider_factory, screen_provider_factory,
        )

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        try:
            self._start_accessibility()
            self._start_screen()
        except BaseException:
            self.close()
            raise

    def transport(self, connector_id: str):
        return self._transports.get(connector_id)

    def status(self) -> list[dict]:
        return [self._accessibility_status(), self._screen_status()]

    def close(self) -> None:
        for connector_id in tuple(self._transports):
            self._registry.unregister(connector_id)
        self._transports.clear()
        self._started = False
        for mechanism, enabled in (
            ("accessibility", self._policy.accessibility.enabled),
            ("screen_input", self._policy.screen_input.enabled),
        ):
            self._issues[mechanism] = "not_started" if enabled else "disabled"

    def _start_accessibility(self) -> None:
        policy = self._policy.accessibility
        if not policy.enabled:
            return
        try:
            provider = self._accessibility_factory()
            if not provider.available():
                self._issues["accessibility"] = "backend_unavailable"
                return
        except Exception:
            self._issues["accessibility"] = "backend_unavailable"
            return
        bridge = LinuxAccessibilityBridge(provider, AccessibilityBridgePolicy(
            allowed_actions=policy.allowed_actions,
        ))
        for target in policy.targets:
            registration = build_accessibility_registration(
                target.connector_id, target.instance_id, target.process_id, _now(),
            )
            if not policy.actions_enabled:
                registration = _without_action(
                    registration, "linux.accessibility.invoke_action",
                )
            transport = AccessibilityFallbackTransport(
                registration, bridge, target.process_id, policy.include_text,
            )
            self._register(transport)
        self._issues["accessibility"] = None

    def _start_screen(self) -> None:
        policy = self._policy.screen_input
        if not policy.enabled:
            return
        try:
            provider = self._screen_factory()
            if not provider.capture_available():
                self._issues["screen_input"] = "backend_unavailable"
                return
            actions_active = policy.actions_enabled and provider.input_available()
        except Exception:
            self._issues["screen_input"] = "backend_unavailable"
            return
        bridge = ScreenInputBridge(provider, ScreenInputPolicy(
            allowed_kinds=policy.allowed_kinds, allowed_keys=policy.allowed_keys,
        ))
        for item in policy.targets:
            target = item.target
            registration = build_screen_input_registration(
                item.connector_id, item.instance_id, target.application_id,
                target.process_id, target.window_id, _now(),
            )
            if not actions_active:
                registration = _without_action(
                    registration, "linux.input.control_active_window",
                )
            self._register(ScreenInputFallbackTransport(registration, bridge, target))
        self._issues["screen_input"] = (
            None if actions_active or not policy.actions_enabled else "input_unavailable"
        )

    def _register(self, transport) -> None:
        self._registry.register(transport.registration)
        self._transports[transport.registration.connector_id] = transport

    def _accessibility_status(self) -> dict:
        policy = self._policy.accessibility
        active = _active_capabilities(self._transports, "accessibility")
        return {
            "mechanism": "accessibility", "configured": policy.enabled,
            "active": bool(active), "privacy_acknowledged": policy.privacy_acknowledged,
            "privacy_impact": "bounded semantic tree and optional visible text",
            "include_text": policy.include_text,
            "observation_capability": "linux.accessibility.observe_tree",
            "actions_requested": policy.actions_enabled,
            "actions_active": "linux.accessibility.invoke_action" in active,
            "action_primitives": list(policy.allowed_actions) if policy.actions_enabled else [],
            "confirmation": "always" if policy.actions_enabled else "not_required",
            "resource_scopes": [f"process:{item.process_id}" for item in policy.targets],
            "issue_code": self._status_issue("accessibility"),
        }

    def _screen_status(self) -> dict:
        policy = self._policy.screen_input
        active = _active_capabilities(self._transports, "screen_input")
        return {
            "mechanism": "screen_input", "configured": policy.enabled,
            "active": bool(active), "privacy_acknowledged": policy.privacy_acknowledged,
            "privacy_impact": "bounded pixels and controlled input for exact active windows",
            "include_text": False,
            "observation_capability": "linux.screen.observe_active_window",
            "actions_requested": policy.actions_enabled,
            "actions_active": "linux.input.control_active_window" in active,
            "action_primitives": [item.value for item in policy.allowed_kinds]
            if policy.actions_enabled else [],
            "confirmation": "always" if policy.actions_enabled else "not_required",
            "resource_scopes": [
                scope for item in policy.targets for scope in item.target.scope
            ],
            "issue_code": self._status_issue("screen_input"),
        }

    def _status_issue(self, mechanism: str):
        return self._issues[mechanism]


def _active_capabilities(transports: dict[str, Any], mechanism: str) -> set[str]:
    kind = "accessibility" if mechanism == "accessibility" else "screen_input"
    return {
        entry.capability_id
        for transport in transports.values()
        if transport.registration.transport_kind.value == kind
        for entry in transport.registration.capabilities
    }


def _without_action(registration, capability_id: str):
    return replace(
        registration,
        capabilities=tuple(
            item for item in registration.capabilities
            if item.capability_id != capability_id
        ),
    )


def _x11_provider():
    return X11ScreenInputProvider(X11InspectorSettings(
        os.environ.get("XDG_SESSION_TYPE", "unknown"), os.environ.get("DISPLAY", ""),
    ))


def _require_private(path: Path) -> None:
    details = path.stat()
    if path.is_symlink() or not path.is_file() or details.st_uid != os.geteuid():
        raise PermissionError("fallback configuration must be owner controlled")
    if details.st_mode & 0o077:
        raise PermissionError("fallback configuration must be mode 0600")


def _now() -> datetime:
    return datetime.now(timezone.utc)
