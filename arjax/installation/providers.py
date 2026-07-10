"""Provider implementations for the installation engine."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from urllib.request import urlopen

import distro

from arjax.config.base import DISTRO_MAP
from arjax.config.logging import get_logger
from arjax.core.exceptions import CommandGenerationError, PackageManagerNotFound, ValidationError
from arjax.installation.models import ProviderConfig, ProviderResult, Recipe
from arjax.installation.recipes import RecipeStore
from arjax.integrations.github import install_from_github
from arjax.package_management.command_gen import generate_command

logger = get_logger(__name__)


_PROVIDER_ORDER = {
    "repository": 10,
    "vendor": 20,
    "github": 30,
    "flatpak": 40,
    "snap": 50,
    "appimage": 60,
}


def detect_distro_family() -> str:
    """Return a coarse distro family key using existing distro detection data."""
    detected = distro.id().lower().strip()
    return DISTRO_MAP.get(detected, detected)


def default_package_manager() -> str:
    """Return the default native package manager name for the current distro."""
    family = detect_distro_family()
    if family == "arch":
        return "pacman"
    if family == "debian":
        return "apt"
    if family == "fedora":
        return "dnf"
    if family == "suse":
        return "zypper"
    return "pacman"


def is_verbose() -> bool:
    """Return True if console logging level is at DEBUG (verbose mode)."""
    import logging
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            return handler.level == logging.DEBUG
    return False


class Provider(ABC):
    """Base class for all installation providers."""

    name: str

    @property
    def priority(self) -> int:
        return _PROVIDER_ORDER.get(self.name, 100)

    @abstractmethod
    def supports(self, package: str, recipe: Optional[Recipe]) -> bool:
        """Return True when this provider should be considered."""

    @abstractmethod
    def install(self, package: str, recipe: Optional[Recipe]) -> ProviderResult:
        """Attempt an installation and return a structured result."""

    def _skip(self, package: str, message: str) -> ProviderResult:
        return ProviderResult(
            provider_name=self.name,
            package=package,
            success=False,
            skipped=True,
            message=message,
        )


class RepositoryProvider(Provider):
    """Install directly from the native repository using the current distro PM."""

    name = "repository"

    def supports(self, package: str, recipe: Optional[Recipe]) -> bool:
        return True

    def install(self, package: str, recipe: Optional[Recipe]) -> ProviderResult:
        provider_config = recipe.get_provider(self.name) if recipe else None
        package_name = (provider_config.package if provider_config and provider_config.package else package).strip()
        package_manager = (provider_config.package_manager if provider_config and provider_config.package_manager else default_package_manager()).strip()

        try:
            command = generate_command(package_name, package_manager)
            if not command:
                return self._skip(package, f"No install command could be generated for {package_name}")

            if is_verbose():
                from rich.console import Console
                Console().print(f"[bold dim]$ {command}[/bold dim]")

            result = subprocess.run(shlex.split(command), capture_output=True, text=True)
            if result.returncode == 0:
                return ProviderResult(
                    provider_name=self.name,
                    package=package,
                    success=True,
                    message=f"Installed {package_name} via {package_manager}",
                    details={"command": command, "stdout": result.stdout.strip()},
                )

            return ProviderResult(
                provider_name=self.name,
                package=package,
                success=False,
                message=f"Repository install failed for {package_name}",
                error=(result.stderr or result.stdout or "Unknown error").strip(),
                details={"command": command, "returncode": result.returncode},
            )
        except (PackageManagerNotFound, ValidationError, CommandGenerationError) as exc:
            return self._skip(package, str(exc))
        except Exception as exc:
            return ProviderResult(
                provider_name=self.name,
                package=package,
                success=False,
                message=f"Repository provider failed for {package_name}",
                error=str(exc),
            )


class VendorProvider(Provider):
    """Install from a vendor-maintained package mapping stored in a recipe."""

    name = "vendor"

    def supports(self, package: str, recipe: Optional[Recipe]) -> bool:
        return bool(recipe and recipe.has_provider(self.name))

    def install(self, package: str, recipe: Optional[Recipe]) -> ProviderResult:
        if not recipe:
            return self._skip(package, "No recipe available for vendor install")

        provider_config = recipe.get_provider(self.name)
        if not provider_config:
            return self._skip(package, "Recipe does not define a vendor provider")

        package_name = (provider_config.package or package).strip()
        package_manager = (provider_config.package_manager or default_package_manager()).strip()

        try:
            command = generate_command(package_name, package_manager)
            if not command:
                return self._skip(package, f"No install command could be generated for {package_name}")

            if is_verbose():
                from rich.console import Console
                Console().print(f"[bold dim]$ {command}[/bold dim]")

            result = subprocess.run(shlex.split(command), capture_output=True, text=True)
            if result.returncode == 0:
                return ProviderResult(
                    provider_name=self.name,
                    package=package,
                    success=True,
                    message=f"Installed {package_name} from vendor mapping via {package_manager}",
                    details={"command": command},
                )

            return ProviderResult(
                provider_name=self.name,
                package=package,
                success=False,
                message=f"Vendor install failed for {package_name}",
                error=(result.stderr or result.stdout or "Unknown error").strip(),
                details={"command": command, "returncode": result.returncode},
            )
        except (PackageManagerNotFound, ValidationError, CommandGenerationError) as exc:
            return self._skip(package, str(exc))
        except Exception as exc:
            return ProviderResult(
                provider_name=self.name,
                package=package,
                success=False,
                message=f"Vendor provider failed for {package_name}",
                error=str(exc),
            )


class GithubReleaseProvider(Provider):
    """Install from explicitly declared GitHub release metadata."""

    name = "github"

    def supports(self, package: str, recipe: Optional[Recipe]) -> bool:
        return bool(recipe and recipe.has_provider(self.name))

    def install(self, package: str, recipe: Optional[Recipe]) -> ProviderResult:
        if not recipe:
            return self._skip(package, "No recipe available for GitHub installation")

        provider_config = recipe.get_provider(self.name)
        if not provider_config:
            return self._skip(package, "Recipe does not define a GitHub provider")

        if provider_config.github_install_type == "source" and provider_config.github_repo:
            ok = install_from_github(provider_config.github_repo)
            if ok:
                return ProviderResult(
                    provider_name=self.name,
                    package=package,
                    success=True,
                    message=f"Installed {package} from GitHub source recipe",
                    details={"repo": provider_config.github_repo},
                )
            return ProviderResult(
                provider_name=self.name,
                package=package,
                success=False,
                message=f"GitHub source install failed for {package}",
                details={"repo": provider_config.github_repo},
            )

        download_url = provider_config.github_download_url
        if not download_url:
            return self._skip(package, "GitHub provider requires an explicit download_url or source repo")

        return self._install_downloaded_binary(package, provider_config, download_url)

    def _install_downloaded_binary(self, package: str, provider_config: ProviderConfig, download_url: str) -> ProviderResult:
        suffix = Path(download_url).name
        temp_dir = Path(tempfile.mkdtemp(prefix="arjax-github-"))
        try:
            archive_path = temp_dir / suffix

            if is_verbose():
                from rich.console import Console
                Console().print(f"[bold dim]$ (downloading {download_url})[/bold dim]")

            with urlopen(download_url) as response:
                content_length = response.info().get('Content-Length')
                total_size = int(content_length) if content_length else None

                if total_size:
                    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, DownloadColumn
                    from rich.console import Console

                    with Progress(
                        TextColumn("[bold blue]{task.description}"),
                        BarColumn(),
                        DownloadColumn(),
                        TimeRemainingColumn(),
                        console=Console()
                    ) as progress:
                        task = progress.add_task("Downloading...", total=total_size)
                        with open(archive_path, 'wb') as f:
                            while True:
                                chunk = response.read(16384)
                                if not chunk:
                                    break
                                f.write(chunk)
                                progress.update(task, advance=len(chunk))
                else:
                    archive_path.write_bytes(response.read())

            if archive_path.name.endswith(".AppImage"):
                return self._install_appimage(archive_path, provider_config, package)

            return ProviderResult(
                provider_name=self.name,
                package=package,
                success=False,
                message="GitHub binary installs currently support AppImage assets only",
                details={"download_url": download_url},
            )
        except Exception as exc:
            return ProviderResult(
                provider_name=self.name,
                package=package,
                success=False,
                message=f"GitHub release download failed for {package}",
                error=str(exc),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _install_appimage(self, archive_path: Path, provider_config: ProviderConfig, package: str) -> ProviderResult:
        target_name = provider_config.appimage_name or archive_path.stem
        target_dir = Path.home() / ".local" / "bin"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / target_name
        shutil.copy2(archive_path, target_path)
        target_path.chmod(target_path.stat().st_mode | 0o111)
        return ProviderResult(
            provider_name=self.name,
            package=package,
            success=True,
            message=f"Installed AppImage from GitHub release to {target_path}",
            details={"path": str(target_path)},
        )


class FlatpakProvider(Provider):
    """Install via Flatpak when the recipe declares a Flatpak app ID."""

    name = "flatpak"

    def supports(self, package: str, recipe: Optional[Recipe]) -> bool:
        return bool(recipe and recipe.has_provider(self.name))

    def install(self, package: str, recipe: Optional[Recipe]) -> ProviderResult:
        if not recipe:
            return self._skip(package, "No recipe available for Flatpak install")

        provider_config = recipe.get_provider(self.name)
        if not provider_config:
            return self._skip(package, "Recipe does not define a Flatpak provider")

        flatpak_id = (provider_config.flatpak_id or provider_config.package or package).strip()
        try:
            command = generate_command(flatpak_id, "flatpak")
            if not command:
                return self._skip(package, f"No Flatpak command could be generated for {flatpak_id}")

            if is_verbose():
                from rich.console import Console
                Console().print(f"[bold dim]$ {command}[/bold dim]")

            result = subprocess.run(shlex.split(command), capture_output=True, text=True)
            if result.returncode == 0:
                return ProviderResult(
                    provider_name=self.name,
                    package=package,
                    success=True,
                    message=f"Installed {flatpak_id} via Flatpak",
                    details={"command": command},
                )

            return ProviderResult(
                provider_name=self.name,
                package=package,
                success=False,
                message=f"Flatpak install failed for {flatpak_id}",
                error=(result.stderr or result.stdout or "Unknown error").strip(),
                details={"command": command, "returncode": result.returncode},
            )
        except (PackageManagerNotFound, ValidationError, CommandGenerationError) as exc:
            return self._skip(package, str(exc))
        except Exception as exc:
            return ProviderResult(
                provider_name=self.name,
                package=package,
                success=False,
                message=f"Flatpak provider failed for {flatpak_id}",
                error=str(exc),
            )


class SnapProvider(Provider):
    """Install via Snap when the recipe declares a snap name."""

    name = "snap"

    def supports(self, package: str, recipe: Optional[Recipe]) -> bool:
        return bool(recipe and recipe.has_provider(self.name))

    def install(self, package: str, recipe: Optional[Recipe]) -> ProviderResult:
        if not recipe:
            return self._skip(package, "No recipe available for Snap install")

        provider_config = recipe.get_provider(self.name)
        if not provider_config:
            return self._skip(package, "Recipe does not define a Snap provider")

        snap_name = (provider_config.snap_id or provider_config.package or package).strip()
        try:
            command = generate_command(snap_name, "snap")
            if not command:
                return self._skip(package, f"No Snap command could be generated for {snap_name}")

            if is_verbose():
                from rich.console import Console
                Console().print(f"[bold dim]$ {command}[/bold dim]")

            result = subprocess.run(shlex.split(command), capture_output=True, text=True)
            if result.returncode == 0:
                return ProviderResult(
                    provider_name=self.name,
                    package=package,
                    success=True,
                    message=f"Installed {snap_name} via Snap",
                    details={"command": command},
                )

            return ProviderResult(
                provider_name=self.name,
                package=package,
                success=False,
                message=f"Snap install failed for {snap_name}",
                error=(result.stderr or result.stdout or "Unknown error").strip(),
                details={"command": command, "returncode": result.returncode},
            )
        except (PackageManagerNotFound, ValidationError, CommandGenerationError) as exc:
            return self._skip(package, str(exc))
        except Exception as exc:
            return ProviderResult(
                provider_name=self.name,
                package=package,
                success=False,
                message=f"Snap provider failed for {snap_name}",
                error=str(exc),
            )


class AppImageProvider(Provider):
    """Install AppImage assets only when the recipe explicitly provides one."""

    name = "appimage"

    def supports(self, package: str, recipe: Optional[Recipe]) -> bool:
        return bool(recipe and recipe.has_provider(self.name))

    def install(self, package: str, recipe: Optional[Recipe]) -> ProviderResult:
        if not recipe:
            return self._skip(package, "No recipe available for AppImage install")

        provider_config = recipe.get_provider(self.name)
        if not provider_config or not provider_config.appimage_url:
            return self._skip(package, "Recipe does not define an AppImage asset")

        return GithubReleaseProvider()._install_downloaded_binary(
            package,
            provider_config,
            provider_config.appimage_url,
        )


def default_providers() -> list[Provider]:
    """Return providers in the requested priority order."""
    return [
        RepositoryProvider(),
        VendorProvider(),
        GithubReleaseProvider(),
        FlatpakProvider(),
        SnapProvider(),
        AppImageProvider(),
    ]


class ProviderManager:
    """Tiny provider loop that delegates to the first provider that works."""

    def __init__(self, providers: Optional[list[Provider]] = None, recipes: Optional[RecipeStore] = None):
        self.providers = sorted(providers or default_providers(), key=lambda provider: provider.priority)
        self.recipes = recipes or RecipeStore()

    def list_providers(self) -> list[str]:
        return [provider.name for provider in self.providers]

    def install(self, package: str, provider_hint: Optional[str] = None) -> ProviderResult:
        recipe = self.recipes.find(package)

        for provider in self.providers:
            if provider_hint and provider.name != provider_hint.lower().strip():
                continue

            if not provider.supports(package, recipe):
                continue

            result = provider.install(package, recipe)
            if result.success:
                return result

            if not result.skipped:
                return result

        return ProviderResult(
            provider_name="manager",
            package=package,
            success=False,
            message=f"No provider could install {package}",
            details={"providers": self.list_providers(), "recipe_found": bool(recipe)},
        )
