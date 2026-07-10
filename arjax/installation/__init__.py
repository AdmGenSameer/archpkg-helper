"""Installation engine for arjax."""

from arjax.installation.models import ProviderConfig, ProviderResult, Recipe
from arjax.installation.orchestrator import InstallationOrchestrator
from arjax.installation.providers import (
    AppImageProvider,
    FlatpakProvider,
    GithubReleaseProvider,
    Provider,
    ProviderManager,
    RepositoryProvider,
    SnapProvider,
    VendorProvider,
)
from arjax.installation.recipes import RecipeStore

__all__ = [
    "ProviderConfig",
    "ProviderResult",
    "Recipe",
    "RecipeStore",
    "Provider",
    "ProviderManager",
    "InstallationOrchestrator",
    "RepositoryProvider",
    "VendorProvider",
    "GithubReleaseProvider",
    "FlatpakProvider",
    "SnapProvider",
    "AppImageProvider",
]
