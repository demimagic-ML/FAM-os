"""Visible owner-selectable engineering delegation profiles."""

from enum import StrEnum

from fam_os.core.engineering.authority import EngineeringAuthority


class EngineeringDelegationMode(StrEnum):
    SAFE_DEFAULT = "safe_default"
    WORKSPACE_OPERATOR = "workspace_operator"
    ENGINEERING_ADMINISTRATOR = "engineering_administrator"
    CUSTOM = "custom"
    FULL_OWNER = "full_owner"


_SAFE_DEFAULT = (
    EngineeringAuthority.OBSERVE,
    EngineeringAuthority.PROPOSE,
)
_WORKSPACE_OPERATOR = (
    *_SAFE_DEFAULT,
    EngineeringAuthority.MODIFY,
    EngineeringAuthority.EXECUTE,
)
_ENGINEERING_ADMINISTRATOR = (
    *_WORKSPACE_OPERATOR,
    EngineeringAuthority.NETWORK,
    EngineeringAuthority.PUBLISH,
    EngineeringAuthority.RAW_SHELL,
    EngineeringAuthority.HOST_ADMIN,
    EngineeringAuthority.SECRET_USE,
    EngineeringAuthority.GLOBAL_INSTALL,
)


def expand_delegation(
    mode: EngineeringDelegationMode,
    custom_authorities: tuple[EngineeringAuthority, ...] = (),
) -> tuple[EngineeringAuthority, ...]:
    """Expand a visible profile into exact individual authority names."""

    if len(set(custom_authorities)) != len(custom_authorities):
        raise ValueError("custom authorities must not contain duplicates")
    if mode is EngineeringDelegationMode.CUSTOM:
        if not custom_authorities:
            raise ValueError("custom delegation requires explicit authorities")
        selected = set(custom_authorities)
        return tuple(item for item in EngineeringAuthority if item in selected)
    if custom_authorities:
        raise ValueError("preset delegation modes do not accept hidden overrides")
    if mode is EngineeringDelegationMode.SAFE_DEFAULT:
        return _SAFE_DEFAULT
    if mode is EngineeringDelegationMode.WORKSPACE_OPERATOR:
        return _WORKSPACE_OPERATOR
    if mode is EngineeringDelegationMode.ENGINEERING_ADMINISTRATOR:
        return _ENGINEERING_ADMINISTRATOR
    if mode is EngineeringDelegationMode.FULL_OWNER:
        return tuple(EngineeringAuthority)
    raise ValueError("engineering delegation mode is unsupported")
