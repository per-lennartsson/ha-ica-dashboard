"""Check that the required ha-ica-todo integration is installed and loaded."""

from dataclasses import dataclass
from enum import StrEnum

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import IntegrationNotFound, async_get_integration

from .const import DOMAIN, ICA_DOMAIN, MIN_ICA_VERSION
from .domain import is_version_at_least

ISSUE_ID = "ica_dependency"


class IcaProblem(StrEnum):
    """Why the ICA integration cannot be used. The value is a translation key suffix."""

    MISSING = "missing"
    TOO_OLD = "too_old"
    NOT_CONFIGURED = "not_configured"
    NOT_LOADED = "not_loaded"


@dataclass(frozen=True)
class IcaStatus:
    """Result of the dependency check; `problem` is None when all is well."""

    problem: IcaProblem | None
    version: str | None = None

    @property
    def translation_key(self) -> str | None:
        """Translation key for abort reasons and repair issues."""
        return f"ica_{self.problem}" if self.problem else None

    @property
    def placeholders(self) -> dict[str, str]:
        """Placeholders used by the translated messages."""
        return {"version": self.version or "?", "minimum": MIN_ICA_VERSION}


async def async_check_ica(hass: HomeAssistant) -> IcaStatus:
    """Check that ha-ica-todo is installed, recent enough, set up and loaded."""
    try:
        integration = await async_get_integration(hass, ICA_DOMAIN)
    except IntegrationNotFound:
        return IcaStatus(IcaProblem.MISSING)

    version = integration.manifest.get("version")
    if not is_version_at_least(version, MIN_ICA_VERSION):
        return IcaStatus(IcaProblem.TOO_OLD, version)

    entries = hass.config_entries.async_entries(ICA_DOMAIN)
    if not entries:
        return IcaStatus(IcaProblem.NOT_CONFIGURED, version)
    if not any(entry.state is ConfigEntryState.LOADED for entry in entries):
        return IcaStatus(IcaProblem.NOT_LOADED, version)
    return IcaStatus(None, version)


def create_dependency_issue(hass: HomeAssistant, status: IcaStatus) -> None:
    """Show (or update) a repair issue describing the dependency problem."""
    if status.translation_key is None:
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_ID,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=status.translation_key,
        translation_placeholders=status.placeholders,
    )


def delete_dependency_issue(hass: HomeAssistant) -> None:
    """Remove the repair issue, if present."""
    ir.async_delete_issue(hass, DOMAIN, ISSUE_ID)
