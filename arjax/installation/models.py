"""Data models for the installation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class ProviderConfig:
    """Declarative metadata for one provider entry inside a recipe."""

    package: Optional[str] = None
    package_manager: Optional[str] = None
    repo_url: Optional[str] = None
    key_url: Optional[str] = None
    github_repo: Optional[str] = None
    github_install_type: Optional[str] = None
    github_download_url: Optional[str] = None
    flatpak_id: Optional[str] = None
    snap_id: Optional[str] = None
    appimage_url: Optional[str] = None
    appimage_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Recipe:
    """Declarative software recipe used by the installation engine."""

    name: str
    display_name: Optional[str] = None
    description: str = ""
    aliases: List[str] = field(default_factory=list)
    providers: Dict[str, ProviderConfig] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_provider(self, provider_name: str) -> Optional[ProviderConfig]:
        return self.providers.get(provider_name.lower())

    def has_provider(self, provider_name: str) -> bool:
        return provider_name.lower() in self.providers


@dataclass(slots=True)
class ProviderResult:
    """Outcome from a single provider attempt."""

    provider_name: str
    package: str
    success: bool
    message: str = ""
    skipped: bool = False
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
