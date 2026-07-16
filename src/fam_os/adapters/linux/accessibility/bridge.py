"""Bounded AT-SPI observation and stale-safe action bridge."""

import hashlib
import json
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from fam_os.adapters.linux.accessibility.ports import AccessibilityProvider
from fam_os.applications import (
    AccessibilityActionEvidence, AccessibilityActionProposal,
    AccessibilitySnapshot, AccessibleAction, AccessibleNode, AccessibleObjectRef,
)


DEFAULT_ALLOWED_ACTIONS = (
    "activate", "click", "collapse", "expand", "press", "select", "show menu", "toggle",
)


def _utc_now():
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class AccessibilityBridgePolicy:
    maximum_nodes: int = 1024
    maximum_depth: int = 12
    maximum_text_characters: int = 4096
    maximum_actions_per_node: int = 16
    allowed_actions: tuple[str, ...] = DEFAULT_ALLOWED_ACTIONS

    def __post_init__(self) -> None:
        if min(
            self.maximum_nodes, self.maximum_depth,
            self.maximum_text_characters, self.maximum_actions_per_node,
        ) <= 0:
            raise ValueError("accessibility limits must be positive")
        normalized = tuple(item.strip().casefold() for item in self.allowed_actions)
        if any(not item for item in normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("allowed accessibility actions must be unique")
        object.__setattr__(self, "allowed_actions", normalized)


class LinuxAccessibilityBridge:
    def __init__(
        self, provider: AccessibilityProvider,
        policy=AccessibilityBridgePolicy(), clock: Callable[[], datetime] = _utc_now,
    ):
        self._provider = provider
        self._policy = policy
        self._clock = clock

    def observe(self, process_id: int, include_text=False):
        root = self._root(process_id)
        if root is None:
            return AccessibilitySnapshot(
                self._clock(), process_id, (), issue_code="accessibility.unavailable"
            )
        queue = deque(((root, (), None, 0),))
        nodes = []
        truncated = False
        while queue and len(nodes) < self._policy.maximum_nodes:
            handle, path, parent_id, depth = queue.popleft()
            node, provider_node = self._node(handle, process_id, path, parent_id, depth, include_text)
            if node is None:
                continue
            nodes.append(node)
            if provider_node.text_truncated:
                truncated = True
            if depth >= self._policy.maximum_depth:
                truncated |= provider_node.child_count > 0
                continue
            remaining = self._policy.maximum_nodes - len(nodes) - len(queue)
            child_limit = min(provider_node.child_count, max(0, remaining))
            truncated |= provider_node.child_count > child_limit
            for index in range(child_limit):
                child = self._provider.child(handle, index)
                if child is not None:
                    queue.append((child, path + (index,), node.reference.reference_id, depth + 1))
        truncated |= bool(queue)
        return AccessibilitySnapshot(
            self._clock(), process_id, tuple(nodes), truncated=truncated
        )

    def prepare_action(self, operation_id, reference, action_name):
        handle, provider_node = self._revalidate(reference)
        if provider_node.protected:
            raise PermissionError("protected accessibility objects cannot be acted on")
        normalized = action_name.strip().casefold()
        if normalized not in self._policy.allowed_actions:
            raise PermissionError("accessibility action is not allowlisted")
        action = next(
            (item for item in self._approved_actions(provider_node)
             if item.name.strip().casefold() == normalized),
            None,
        )
        if action is None:
            raise ValueError("accessibility action is no longer available")
        return AccessibilityActionProposal(
            operation_id, reference, action.name, action.index
        )

    def perform_action(self, proposal):
        handle, provider_node = self._revalidate(proposal.reference)
        if provider_node.protected:
            raise PermissionError("protected accessibility objects cannot be acted on")
        action = next(
            (item for item in self._approved_actions(provider_node)
             if item.index == proposal.action_index), None
        )
        if action is None or action.name != proposal.action_name:
            raise RuntimeError("accessibility action changed after approval")
        try:
            invoked = self._provider.perform_action(handle, proposal.action_index)
        except Exception:
            invoked = False
        after = self._safe_read(handle)
        after_fingerprint = _fingerprint(after) if after is not None else None
        return AccessibilityActionEvidence(
            proposal.operation_id, proposal.reference.reference_id,
            proposal.action_name, invoked, proposal.reference.fingerprint,
            after_fingerprint,
        )

    def _root(self, process_id):
        if process_id <= 0 or not self._provider.available():
            return None
        matches = []
        for handle in self._provider.roots():
            node = self._safe_read(handle)
            if node is not None and node.process_id == process_id:
                matches.append(handle)
        return matches[0] if len(matches) == 1 else None

    def _node(self, handle, process_id, path, parent_id, depth, include_text):
        provider_node = self._safe_read(handle, include_text)
        if provider_node is None:
            return None, None
        fingerprint = _fingerprint(provider_node)
        reference = AccessibleObjectRef(process_id, path, fingerprint)
        protected = provider_node.protected
        allowed = self._approved_actions(provider_node)
        actions = () if protected else tuple(
            AccessibleAction(item.name, item.description, item.key_binding)
            for item in allowed
        )
        node = AccessibleNode(
            reference, parent_id, depth, provider_node.role,
            None if protected else provider_node.name,
            None if protected else provider_node.description,
            provider_node.states, actions,
            provider_node.text if include_text and not protected else None,
            protected,
        )
        return node, provider_node

    def _revalidate(self, reference):
        handle = self._root(reference.process_id)
        if handle is None:
            raise RuntimeError("accessibility application is unavailable")
        for index in reference.child_path:
            handle = self._provider.child(handle, index)
            if handle is None:
                raise RuntimeError("accessibility object is stale")
        node = self._safe_read(handle)
        if node is None or _fingerprint(node) != reference.fingerprint:
            raise RuntimeError("accessibility object identity changed")
        return handle, node

    def _safe_read(self, handle, include_text=False):
        try:
            return self._provider.read(
                handle, self._policy.maximum_text_characters, include_text
            )
        except Exception:
            return None

    def _approved_actions(self, provider_node):
        allowed = (
            item for item in provider_node.actions
            if item.name.strip().casefold() in self._policy.allowed_actions
        )
        return tuple(allowed)[:self._policy.maximum_actions_per_node]


def _fingerprint(node):
    payload = {
        "process_id": node.process_id, "role": node.role,
        "name": node.name, "description": node.description,
        "actions": [(item.index, item.name) for item in node.actions],
        "protected": node.protected,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
