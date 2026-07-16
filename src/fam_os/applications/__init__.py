"""Application capabilities, observations, actions, and connector coordination."""

from fam_os.applications.actions import (
    ActionConfirmation,
    ActionPreparationRequest,
    ActionProposal,
    ActionResult,
    ActionStatus,
    ConditionEvidence,
    ConditionRequirement,
    ConfirmationDecision,
)
from fam_os.applications.action_audit import (
    APPLICATION_ACTION_AUDIT_VERSION, ActionAuditStage,
    ApplicationActionAuditIntent, ApplicationActionAuditRecord,
    ApplicationActionAuditVerification, ApplicationAuditEmissionError,
    ApplicationAuditIntegrityError,
)
from fam_os.applications.action_audit_ports import ApplicationActionAuditSink
from fam_os.applications.accessibility import (
    AccessibilityActionEvidence, AccessibilityActionProposal,
    AccessibilitySnapshot, AccessibleAction, AccessibleNode, AccessibleObjectRef,
)
from fam_os.applications.capabilities import CapabilityDescriptor, CapabilityRegistryEntry
from fam_os.applications.connectors import (
    APPLICATION_CONTRACT_VERSION,
    CapabilityRegistry,
    ConnectorEvent,
    ConnectorEventKind,
    ConnectorRegistration,
    ConnectorTransport,
    ConnectorTransportKind,
)
from fam_os.applications.identity import ApplicationIdentity, ApplicationInstance
from fam_os.applications.discovery import (
    ApplicationDiscoveryIssue, ApplicationDiscoverySnapshot, ApplicationLaunchSpec,
    ApplicationProcess, ApplicationWindow, DiscoveredApplication, DiscoverySurface,
)
from fam_os.applications.failures import (
    APPLICATION_FAILURE_CONTRACT_VERSION,
    ApplicationFailure,
    ApplicationFailureCategory,
    ApplicationRetryDisposition,
)
from fam_os.applications.manifest import (
    CONNECTOR_MANIFEST_CONTRACT_VERSION,
    ConnectorManifest,
)
from fam_os.applications.observations import (
    ObservationRequest,
    ObservationResult,
    ObservationStatus,
)
from fam_os.applications.permissions import PermissionGrant, PermissionScope
from fam_os.applications.policy import (
    ApplicationAuthority,
    CapabilityKind,
    ConfirmationPolicy,
    Reversibility,
)
from fam_os.applications.registry import (
    ApplicationCapabilityRegistry,
    CapabilityRegistryEvent,
    CapabilityRegistrySnapshot,
    RegistryEventKind,
)
from fam_os.applications.screen_input import (
    RelativeScreenPoint, ScreenFrame, ScreenInputEvidence, ScreenInputInstruction,
    ScreenInputKind, ScreenInputProposal, ScreenObservation, ScreenTarget,
)

__all__ = [
    "APPLICATION_CONTRACT_VERSION",
    "APPLICATION_ACTION_AUDIT_VERSION",
    "APPLICATION_FAILURE_CONTRACT_VERSION",
    "ActionConfirmation",
    "ActionAuditStage",
    "ActionPreparationRequest",
    "ActionProposal",
    "ActionResult",
    "ActionStatus",
    "AccessibilityActionEvidence",
    "AccessibilityActionProposal",
    "AccessibilitySnapshot",
    "AccessibleAction",
    "AccessibleNode",
    "AccessibleObjectRef",
    "ApplicationAuthority",
    "ApplicationActionAuditIntent",
    "ApplicationActionAuditRecord",
    "ApplicationActionAuditSink",
    "ApplicationActionAuditVerification",
    "ApplicationAuditEmissionError",
    "ApplicationAuditIntegrityError",
    "ApplicationCapabilityRegistry",
    "ApplicationFailure",
    "ApplicationFailureCategory",
    "ApplicationDiscoveryIssue",
    "ApplicationDiscoverySnapshot",
    "ApplicationIdentity",
    "ApplicationInstance",
    "ApplicationLaunchSpec",
    "ApplicationProcess",
    "ApplicationRetryDisposition",
    "ApplicationWindow",
    "CapabilityDescriptor",
    "CapabilityKind",
    "CapabilityRegistry",
    "CapabilityRegistryEntry",
    "CapabilityRegistryEvent",
    "CapabilityRegistrySnapshot",
    "ConditionEvidence",
    "ConditionRequirement",
    "ConfirmationDecision",
    "ConfirmationPolicy",
    "CONNECTOR_MANIFEST_CONTRACT_VERSION",
    "ConnectorEvent",
    "ConnectorEventKind",
    "ConnectorRegistration",
    "ConnectorManifest",
    "ConnectorTransport",
    "ConnectorTransportKind",
    "DiscoveredApplication",
    "DiscoverySurface",
    "ObservationRequest",
    "ObservationResult",
    "ObservationStatus",
    "PermissionGrant",
    "PermissionScope",
    "Reversibility",
    "RelativeScreenPoint",
    "RegistryEventKind",
    "ScreenFrame",
    "ScreenInputEvidence",
    "ScreenInputInstruction",
    "ScreenInputKind",
    "ScreenInputProposal",
    "ScreenObservation",
    "ScreenTarget",
]
