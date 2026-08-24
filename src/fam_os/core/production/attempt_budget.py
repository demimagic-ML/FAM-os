"""Single durable resource budget for local and remote production attempts."""

from fam_os.core.lifecycle import GlobalAttemptBudget


def production_attempt_budget(instance_id: str) -> GlobalAttemptBudget:
    return GlobalAttemptBudget(
        instance_id,
        maximum_tokens=4096,
        maximum_wall_milliseconds=720_000,
        maximum_repairs=1,
        maximum_escalations=2,
    )
