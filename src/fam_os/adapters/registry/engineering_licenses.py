"""Registry license-policy adapter for engineering dependency admission."""

from fam_os.registry.license_policy import require_allowed_license


class SpdxLicensePolicyAdapter:
    def require_allowed(self, expression: str, allowed: tuple[str, ...]) -> None:
        require_allowed_license(expression, allowed)
