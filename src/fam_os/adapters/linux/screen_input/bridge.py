"""Exact-scene screen observation and confirmed input preparation."""

import hashlib
from collections.abc import Callable
from datetime import datetime, timezone

from fam_os.adapters.linux.screen_input.policy import ScreenInputPolicy
from fam_os.adapters.linux.screen_input.ports import ScreenInputProvider
from fam_os.adapters.linux.screen_input.types import ProviderInputAction
from fam_os.applications import (
    ScreenFrame, ScreenInputEvidence, ScreenInputInstruction, ScreenInputKind,
    ScreenInputProposal, ScreenObservation, ScreenTarget,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScreenInputBridge:
    def __init__(
        self, provider: ScreenInputProvider, policy=ScreenInputPolicy(),
        clock: Callable[[], datetime] = _utc_now,
    ):
        self._provider = provider
        self._policy = policy
        self._clock = clock

    def inspect(self, target: ScreenTarget):
        if not self._provider.capture_available():
            return None
        try:
            state = self._provider.inspect(target)
        except Exception:
            return None
        return state if state is not None and self._state_matches(target, state) else None

    def observe(self, target: ScreenTarget) -> ScreenObservation:
        captured_at = self._clock()
        if not self._provider.capture_available():
            return ScreenObservation(captured_at, target, issue_code="screen.unavailable")
        try:
            provider_frame = self._provider.capture(
                target, self._policy.maximum_source_pixels,
                self._policy.maximum_encoded_pixels,
                self._policy.maximum_encoded_bytes,
            )
            frame = self._frame(target, provider_frame, captured_at)
        except Exception:
            return ScreenObservation(captured_at, target, issue_code="screen.capture_failed")
        return ScreenObservation(captured_at, target, frame=frame)

    def prepare_action(
        self, operation_id: str, target: ScreenTarget, expected_scene_id: str,
        instruction: ScreenInputInstruction,
    ) -> ScreenInputProposal:
        self._validate_instruction(instruction)
        if not self._provider.input_available():
            raise RuntimeError("screen input is unavailable")
        observation = self.observe(target)
        if observation.frame is None:
            raise RuntimeError(observation.issue_code or "screen capture unavailable")
        if observation.frame.scene_id != expected_scene_id:
            raise RuntimeError("screen scene changed before input preparation")
        return ScreenInputProposal(
            operation_id, target, expected_scene_id, instruction, instruction.digest,
        )

    def perform_action(self, proposal: ScreenInputProposal) -> ScreenInputEvidence:
        if proposal.instruction_digest != proposal.instruction.digest:
            raise RuntimeError("screen input changed after approval")
        self._validate_instruction(proposal.instruction)
        if not self._provider.input_available():
            raise RuntimeError("screen input is unavailable")
        before = self.observe(proposal.target)
        if before.frame is None or before.frame.scene_id != proposal.expected_scene_id:
            raise RuntimeError("screen scene changed after approval")
        state = self.inspect(proposal.target)
        if state is None:
            raise RuntimeError("screen input target is unavailable")
        try:
            invoked = self._provider.inject(
                proposal.target, ProviderInputAction(state, proposal.instruction)
            )
        except Exception:
            invoked = False
        after = self.observe(proposal.target)
        return ScreenInputEvidence(
            proposal.operation_id, proposal.target, proposal.instruction_digest,
            invoked, before.frame.scene_id,
            after.frame.scene_id if after.frame is not None else None,
            after.issue_code,
        )

    def _frame(self, target, provider_frame, captured_at):
        state = provider_frame.state
        if not self._state_matches(target, state):
            raise RuntimeError("screen provider returned a different target")
        image = provider_frame.encoded_png
        if len(image) > self._policy.maximum_encoded_bytes:
            raise RuntimeError("screen provider exceeded byte bound")
        if state.width * state.height > self._policy.maximum_source_pixels:
            raise RuntimeError("screen provider exceeded source pixel bound")
        if provider_frame.encoded_width * provider_frame.encoded_height > self._policy.maximum_encoded_pixels:
            raise RuntimeError("screen provider exceeded pixel bound")
        return ScreenFrame(
            captured_at, target, state.width, state.height,
            provider_frame.encoded_width, provider_frame.encoded_height,
            "image/png", hashlib.sha256(image).hexdigest(), image,
        )

    def _state_matches(self, target, state):
        identity = state.window_id == target.window_id and state.process_id == target.process_id
        return identity and (state.focused or not self._policy.require_focused_window)

    def _validate_instruction(self, instruction):
        if instruction.kind not in self._policy.allowed_kinds:
            raise PermissionError("screen input kind is not allowlisted")
        if instruction.kind is ScreenInputKind.KEY_CHORD:
            if any(key not in self._policy.allowed_keys for key in instruction.keys):
                raise PermissionError("screen key is not allowlisted")
