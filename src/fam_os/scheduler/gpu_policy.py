"""Pure deterministic single-device split-offload placement policy."""

from dataclasses import dataclass

from fam_os.scheduler.admission_contracts import AdmissionStatus
from fam_os.scheduler.gpu_contracts import GpuPlacementDecision, GpuPlacementRequest
from fam_os.scheduler.live_contracts import ObservationStatus


@dataclass(frozen=True, slots=True)
class DeterministicGpuPlacementPolicy:
    def decide(self, decision_id: str, request: GpuPlacementRequest) -> GpuPlacementDecision:
        observation = request.observation
        device = next(
            (item for item in observation.accelerators if item.device_id == request.accelerator_device_id),
            None,
        )
        accelerator_available = 0 if device is None or device.available_for_new_bytes is None else device.available_for_new_bytes
        host_available = observation.memory.available_for_new_bytes
        accelerator_weight = _ceiling_fraction(
            request.weight.resident_weight_bytes,
            request.requested_accelerator_layers,
            request.model_layer_count,
        )
        host_compute = request.weight.resident_weight_bytes - accelerator_weight
        context = request.context.total_context_bytes
        host_safety = request.weight.resident_weight_bytes + context
        accelerator_reservation = accelerator_weight + context
        reasons = _reasons(request, device, host_safety, accelerator_reservation)
        admitted = not reasons
        return GpuPlacementDecision(
            decision_id, request.request_id,
            AdmissionStatus.ADMITTED if admitted else AdmissionStatus.REJECTED,
            host_compute, accelerator_weight, context, host_safety,
            accelerator_reservation, host_available, accelerator_available,
            accelerator_weight, request.requested_accelerator_layers,
            tuple(reasons) if reasons else (
                "vector_memory.admitted", "host_reservation.full_weight_conservative",
                "transfer_cost.offloaded_weight_bytes",
            ),
        )


def _reasons(request, device, host_required, accelerator_required):
    observation = request.observation
    if observation.status is ObservationStatus.DEGRADED:
        return ["resource_observation.degraded"]
    if not observation.memory.scope_authoritative:
        return ["host_memory.not_authoritative"]
    if device is None:
        return ["accelerator.not_observed"]
    if not device.placement_allowed or device.available_for_new_bytes is None:
        return ["accelerator.not_available"]
    reasons = []
    if host_required > observation.memory.available_for_new_bytes:
        reasons.append("host_memory.insufficient")
    if accelerator_required > device.available_for_new_bytes:
        reasons.append("accelerator_memory.insufficient")
    return reasons


def _ceiling_fraction(value: int, numerator: int, denominator: int) -> int:
    return (value * numerator + denominator - 1) // denominator
