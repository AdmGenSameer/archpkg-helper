"""
Unit tests for the provider system in arjax.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from arjax.installation.models import ProviderConfig, ProviderResult, Recipe
from arjax.installation.providers import (
    Provider,
    RepositoryProvider,
    VendorProvider,
    GithubReleaseProvider,
    FlatpakProvider,
    SnapProvider,
    AppImageProvider,
    ProviderManager,
    default_providers,
)

class TestProviderBase:
    """Tests for provider base class and priority ordering."""

    def test_provider_priority(self):
        """Test provider priority values and comparisons."""
        repo = RepositoryProvider()
        flatpak = FlatpakProvider()
        
        assert repo.priority == 10
        assert flatpak.priority == 40
        assert repo.priority < flatpak.priority


class TestProviderResult:
    """Tests for provider result representation."""

    def test_success_result(self):
        """Test successful installation result."""
        result = ProviderResult(
            provider_name="TestProvider",
            package="test-pkg",
            success=True,
            message="Success",
        )

        assert result.success
        assert not result.skipped
        assert result.provider_name == "TestProvider"
        assert result.package == "test-pkg"
        assert result.message == "Success"

    def test_failure_result(self):
        """Test failed installation result."""
        result = ProviderResult(
            provider_name="TestProvider",
            package="test-pkg",
            success=False,
            message="Failed",
            error="Connection timeout",
        )

        assert not result.success
        assert not result.skipped
        assert result.error == "Connection timeout"


class TestProviderManager:
    """Tests for ProviderManager orchestration."""

    @pytest.fixture
    def mock_providers(self):
        """Create mock providers."""
        provider1 = Mock(spec=Provider)
        provider1.name = "repository"
        provider1.priority = 10
        provider1.supports.return_value = True
        provider1.install.return_value = ProviderResult(
            provider_name="repository",
            package="test",
            success=False,
            skipped=True,
            message="Repository skip",
        )

        provider2 = Mock(spec=Provider)
        provider2.name = "flatpak"
        provider2.priority = 40
        provider2.supports.return_value = True
        provider2.install.return_value = ProviderResult(
            provider_name="flatpak",
            package="test",
            success=True,
            message="Flatpak success",
        )

        return [provider2, provider1]  # Return unsorted to test sorting

    def test_manager_initialization(self, mock_providers):
        """Test manager initialization and sorting."""
        manager = ProviderManager(providers=mock_providers)
        # Should sort by priority: repository (10) then flatpak (40)
        assert len(manager.providers) == 2
        assert manager.providers[0].name == "repository"
        assert manager.providers[1].name == "flatpak"

    def test_manager_list_providers(self, mock_providers):
        """Test listing provider names in order."""
        manager = ProviderManager(providers=mock_providers)
        assert manager.list_providers() == ["repository", "flatpak"]

    def test_manager_install_success(self, mock_providers):
        """Test installation succeeds when a provider returns success."""
        manager = ProviderManager(providers=mock_providers)
        result = manager.install("test")

        assert result.success
        assert result.provider_name == "flatpak"
        assert result.message == "Flatpak success"

    def test_manager_install_hint(self, mock_providers):
        """Test installation respects provider_hint."""
        # Find the repository provider from the fixture list
        repo_provider = next(p for p in mock_providers if p.name == "repository")
        repo_provider.install.return_value = ProviderResult(
            provider_name="repository",
            package="test",
            success=False,
            skipped=False,
            message="Repository fail",
        )

        manager = ProviderManager(providers=mock_providers)
        
        # When hinting repository, it should only check repository, which returns skip/failure
        result = manager.install("test", provider_hint="repository")
        assert not result.success
        assert result.provider_name == "repository"

    def test_manager_fallback(self):
        """Test installation falls back to next provider on skipped/failed attempts."""
        provider1 = Mock(spec=Provider)
        provider1.name = "repository"
        provider1.priority = 10
        provider1.supports.return_value = True
        provider1.install.return_value = ProviderResult(
            provider_name="repository",
            package="test",
            success=False,
            skipped=True,
            message="Skipped",
        )

        provider2 = Mock(spec=Provider)
        provider2.name = "flatpak"
        provider2.priority = 40
        provider2.supports.return_value = True
        provider2.install.return_value = ProviderResult(
            provider_name="flatpak",
            package="test",
            success=True,
            message="Success",
        )

        manager = ProviderManager(providers=[provider1, provider2])
        result = manager.install("test")

        assert result.success
        assert result.provider_name == "flatpak"
        assert result.message == "Success"
