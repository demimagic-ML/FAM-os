"""Public host-inventory and effective-budget contracts."""

from fam_os.scheduler.resources.budget import (
    EFFECTIVE_RESOURCE_BUDGET_CONTRACT_VERSION,
    AcceleratorResourceBudget,
    CpuResourceBudget,
    EffectiveResourceBudget,
    MemoryResourceBudget,
    StorageResourceBudget,
)
from fam_os.scheduler.resources.identity import (
    COMPAT_CPU_16GB_PROFILE_ID,
    FULL_REFERENCE_WORKSTATION_PROFILE_ID,
    ValidationProfilePurpose,
    ValidationProfileRef,
)
from fam_os.scheduler.resources.inventory import (
    HOST_INVENTORY_CONTRACT_VERSION,
    AcceleratorKind,
    HostAcceleratorInventory,
    HostCpuInventory,
    HostInventory,
    HostMemoryInventory,
    HostStorageInventory,
    StorageMedium,
)
from fam_os.scheduler.resources.pressure import PressureReading

__all__ = [
    "COMPAT_CPU_16GB_PROFILE_ID",
    "EFFECTIVE_RESOURCE_BUDGET_CONTRACT_VERSION",
    "FULL_REFERENCE_WORKSTATION_PROFILE_ID",
    "HOST_INVENTORY_CONTRACT_VERSION",
    "AcceleratorKind",
    "AcceleratorResourceBudget",
    "CpuResourceBudget",
    "EffectiveResourceBudget",
    "HostAcceleratorInventory",
    "HostCpuInventory",
    "HostInventory",
    "HostMemoryInventory",
    "HostStorageInventory",
    "MemoryResourceBudget",
    "PressureReading",
    "StorageMedium",
    "StorageResourceBudget",
    "ValidationProfilePurpose",
    "ValidationProfileRef",
]
