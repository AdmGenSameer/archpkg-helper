#!/usr/bin/python
# cli.py
"""Universal Package Helper CLI - Main module with improved consistency."""

import sys
import os
import re
import subprocess
import webbrowser
import threading
import time
import shutil
from typing import List, Tuple, Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import logging

try:
    import typer
    from typer import Option, Argument
except ImportError:
    print("Typer is required. Install with: pip install typer[all]")
    sys.exit(1)

# Import modules
from arjax.config.base import JUNK_KEYWORDS, LOW_PRIORITY_KEYWORDS, BOOST_KEYWORDS, DISTRO_MAP
from arjax.core.exceptions import PackageManagerNotFound, NetworkError, TimeoutError, CommandGenerationError
from arjax.search.aur import search_aur
from arjax.search.pacman import search_pacman
from arjax.search.flatpak import search_flatpak
from arjax.search.snap import search_snap
from arjax.search.apt import search_apt
from arjax.search.dnf import search_dnf
from arjax.search.zypper import search_zypper
from arjax.search.rpm import search_rpm
from arjax.package_management.command_gen import generate_command
from arjax.config.logging import get_logger, PackageHelperLogger
from arjax.integrations.github import install_from_github, validate_github_url
from arjax.config.manager import get_user_config, set_config_option
from arjax.config.manager import save_user_config
from arjax.config.manager import UserConfig
from arjax.package_management.update import check_for_updates, trigger_update_check
from arjax.package_management.download import install_updates, start_background_update_service, stop_background_update_service
from arjax.package_management.installed import add_installed_package, get_all_installed_packages, get_packages_with_updates
from arjax.intelligence.suggest import suggest_apps, list_purposes
from arjax.integrations.cache import get_cache_manager, CacheConfig
from arjax.integrations.pkgs_org import PkgsOrgClient
from arjax.package_management.snapshot import (
    create_snapshot, 
    list_snapshots, 
    restore_snapshot, 
    delete_snapshot,
    detect_snapshot_tool
)
from arjax.installation import InstallationOrchestrator
from arjax.intelligence.advisor import apply_user_mode_defaults, get_arch_news, assess_aur_trust
from arjax.search.ranking import deduplicate_packages, get_top_matches, is_valid_package

console = Console()
logger = get_logger(__name__)

# Constants
PANEL_PADDING = 4  # Padding for panel borders in terminal width calculations
INSTALL_ROOT = Path.home() / ".local" / "share" / "archpkg-helper"
VENV_DIR = INSTALL_ROOT / "venv"
BIN_PATH = Path.home() / ".local" / "bin" / "archpkg"
DESKTOP_ENTRY = Path.home() / ".local" / "share" / "applications" / "archpkg-helper.desktop"
CONFIG_DIR = Path.home() / ".archpkg"
STARTUP_BLOCK = (
    "\n# archpkg-helper: make user-local commands available\n"
    "if [ -d \"$HOME/.local/bin\" ]; then\n"
    "    export PATH=\"$HOME/.local/bin:$PATH\"\n"
    "fi\n"
)

def normalize_query(query: str) -> List[str]:
    """Generate query variations for better matching.
    
    Args:
        query: Original search query
        
    Returns:
        List of query variations to try
    """
    variations = [query]

    # For RPM/DEB filenames: strip extension and version/arch to get base name
    # Example: gimp-3.0.4-8.fc43.x86_64.rpm -> gimp
    stripped_ext = re.sub(r"\.(rpm|deb)$", "", query)
    if stripped_ext != query:
        variations.append(stripped_ext)
        logger.debug(f"Added no-extension variation: '{stripped_ext}'")

    # If pattern looks like name-version-arch, strip version/arch segment
    match_name_only = re.match(r"^([A-Za-z0-9+_.-]+?)-\d", stripped_ext)
    if match_name_only:
        base_name = match_name_only.group(1)
        if base_name not in variations:
            variations.append(base_name)
            logger.debug(f"Added base-name variation: '{base_name}'")
    
    # Add hyphenated version: "jellyfin media player" -> "jellyfin-media-player"
    if ' ' in query:
        hyphenated = query.replace(' ', '-')
        variations.append(hyphenated)
        logger.debug(f"Added hyphenated variation: '{hyphenated}'")
    
    # Add concatenated version: "jellyfin media player" -> "jellyfinmediaplayer"
    if ' ' in query:
        concatenated = query.replace(' ', '')
        variations.append(concatenated)
        logger.debug(f"Added concatenated variation: '{concatenated}'")
    
    return variations

# Create Typer app
app = typer.Typer(
    name="arjax",
    help="Universal package manager helper for Linux distributions",
    add_completion=False
)

# Dependency check for `distro`
try:
    import distro
    logger.info("Successfully imported distro module")
except ModuleNotFoundError as e:
    logger.error(f"Required dependency 'distro' is not installed: {e}")
    console.print(Panel(
        "[red]Required dependency 'distro' is not installed.[/red]\n\n"
        "[bold yellow]To fix this issue:[/bold yellow]\n"
        "- Run: [cyan]pip install distro[/cyan]\n"
        "- Or reinstall the package: [cyan]pip install --upgrade arjax[/cyan]\n"
        "- If using pipx: [cyan]pipx reinstall arjax[/cyan]",
        title="Missing Dependency",
        border_style="red"
    ))
    sys.exit(1)

def detect_distro() -> str:
    """Detect the current Linux distribution with detailed error handling.
    
    Returns:
        str: Detected distribution family ('arch', 'debian', 'fedora', or 'unknown')
    """
    logger.info("Starting distribution detection")
    
    try:
        dist = distro.id().lower().strip()
        logger.debug(f"Raw distribution ID: '{dist}'")
        
        if not dist:
            logger.warning("Empty distribution ID detected")
            console.print(Panel(
                "[yellow]Unable to detect your Linux distribution.[/yellow]\n\n"
                "[bold cyan]Possible solutions:[/bold cyan]\n"
                "- Ensure you're running on a supported Linux distribution\n"
                "- Check if the /etc/os-release file exists\n"
                "- Try running: [cyan]cat /etc/os-release[/cyan]",
                title="Distribution Detection Warning",
                border_style="yellow"
            ))
            return "unknown"
        
        detected_family = DISTRO_MAP.get(dist, "unknown")
        logger.info(f"Detected distribution: '{dist}' -> family: '{detected_family}'")
        
        if detected_family == "unknown":
            logger.warning(f"Unsupported distribution detected: '{dist}'")
            console.print(Panel(
                f"[yellow]Unsupported distribution detected: '{dist}'[/yellow]\n\n"
                "[bold cyan]What you can do:[/bold cyan]\n"
                "- Only Flatpak and Snap searches will be available\n"
                "- Consider requesting support for your distribution\n"
                f"- Supported distributions: {', '.join(DISTRO_MAP.keys())}",
                title="Unsupported Distribution",
                border_style="yellow"
            ))
        
        return detected_family
        
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Failed to detect distribution", e)
        console.print(Panel(
            f"[red]Failed to detect your Linux distribution.[/red]\n\n"
            f"[bold]Error details:[/bold] {str(e)}\n\n"
            "[bold cyan]Troubleshooting steps:[/bold cyan]\n"
            "- Ensure you're running on a Linux system\n"
            "- Check if the 'distro' package is properly installed\n"
            "- Try reinstalling: [cyan]pip install --upgrade distro[/cyan]\n"
            "- Report this issue if the problem persists",
            title="Distribution Detection Failed",
            border_style="red"
        ))
        return "unknown"
    
# Search result deduplication and ranking functions are now in arjax.search_ranking

def show_opensuse_brave_guidance() -> None:
    """Show guidance for installing Brave browser on openSUSE."""
    logger.info("Showing Brave browser installation guidance for openSUSE")
    
    console.print(Panel(
        "[bold cyan]Brave Browser on openSUSE[/bold cyan]\n\n"
        "[yellow]Brave requires adding an external repository.[/yellow]\n\n"
        "[bold]Option 1: Add Brave Repository (Recommended)[/bold]\n"
        "1. Import the repository key:\n"
        "   [cyan]sudo rpm --import https://brave-browser-rpm-release.s3.brave.com/brave-core.asc[/cyan]\n\n"
        "2. Add the Brave repository:\n"
        "   [cyan]sudo zypper addrepo https://brave-browser-rpm-release.s3.brave.com/brave-browser.repo[/cyan]\n\n"
        "3. Install Brave:\n"
        "   [cyan]sudo zypper install brave-browser[/cyan]\n\n"
        "[bold]Option 2: Install via Flatpak[/bold]\n"
        "   [cyan]flatpak install flathub com.brave.Browser[/cyan]\n\n"
        "[dim]Note: After adding the repository, you can search for Brave again with arjax.[/dim]",
        title="🦁 Brave Browser Installation",
        border_style="blue"
    ))

def search_pkgs_org(query: str, detected_distro: str, limit: int = 10) -> List[dict]:
    """Search pkgs.org for packages across distributions.
    
    Args:
        query: Package search query
        detected_distro: Current detected distribution
        limit: Maximum number of results
        
    Returns:
        List of package dicts with install commands and metadata
    """
    try:
        logger.debug("Attempting pkgs.org search as supplementary source")
        client = PkgsOrgClient()
        
        # Search with distro hint
        results = client.search(query, distro=detected_distro, limit=limit)
        
        if not results:
            logger.debug("pkgs.org returned no results")
            return []
        
        logger.info(f"pkgs.org found {len(results)} cross-distro results")
        return results
        
    except Exception as e:
        logger.debug(f"pkgs.org search failed: {e}")
        return []

def show_pkgs_org_availability(results: List[dict]) -> None:
    """Show where a package is available across distributions.
    
    Args:
        results: List of package dict results from pkgs.org
    """
    if not results:
        return
    
    try:
        # Group by distro
        distro_packages = {}
        for r in results:
            distro = r.get("distro", "Unknown")
            if distro not in distro_packages:
                distro_packages[distro] = []
            distro_packages[distro].append(r.get("name", ""))
        
        console.print("\n[bold cyan]📊 Cross-Distribution Availability:[/bold cyan]")
        for distro, packages in distro_packages.items():
            pkg_list = ", ".join(packages[:3])
            if len(packages) > 3:
                pkg_list += f" (+{len(packages)-3} more)"
            console.print(f"  • {distro}: {pkg_list}")
    except Exception as e:
        logger.debug(f"Failed to show availability: {e}")

def github_fallback(query: str, unavailable_sources: Optional[List[str]] = None) -> None:
    """Provide GitHub search fallback with clear messaging and alternative installation options.
    
    Args:
        query: The search query
        unavailable_sources: List of package managers that failed to search
    """
    logger.info(f"No packages found for query '{query}', providing GitHub fallback")

    # Determine distro-aware install commands
    detected_distro = detect_distro()
    install_snap_cmd = "Check your distro docs for snapd"
    install_flatpak_cmd = "Check your distro docs for flatpak"

    if detected_distro in {"ubuntu", "debian"}:
        install_snap_cmd = "sudo apt install snapd"
        install_flatpak_cmd = "sudo apt install flatpak"
    elif detected_distro == "fedora":
        install_snap_cmd = "sudo dnf install snapd"
        install_flatpak_cmd = "sudo dnf install flatpak"
    elif detected_distro == "suse":
        install_snap_cmd = "sudo zypper install snapd"
        install_flatpak_cmd = "sudo zypper install flatpak"
    elif detected_distro in {"arch", "manjaro"}:
        install_snap_cmd = "sudo pacman -S snapd"
        install_flatpak_cmd = "sudo pacman -S flatpak"

    # Build alternative options message
    alt_options = [
        "- Install from GitHub repository (source code)",
        "- Check if the package name is spelled correctly",
        "- Try searching with different keywords",
        "- Look for similar packages with: [cyan]arjax <similar-name>[/cyan]"
    ]
    
    # If Snap or Flatpak were unavailable, offer them as options
    if unavailable_sources:
        if "Snap" in unavailable_sources:
            alt_options.insert(0, f"- [yellow]Install Snap[/yellow]: [cyan]{install_snap_cmd}[/cyan] (then retry search)")
        if "Flatpak" in unavailable_sources:
            alt_options.insert(0, f"- [yellow]Install Flatpak[/yellow]: [cyan]{install_flatpak_cmd}[/cyan] (then retry search)")
    
    panel_content = f"[yellow]No packages found for '{query}' in available repositories.[/yellow]\n\n"
    panel_content += "[bold cyan]Alternative options:[/bold cyan]\n"
    panel_content += "\n".join(alt_options)
    
    console.print(Panel(
        panel_content,
        title="No Packages Found",
        border_style="yellow"
    ))
    
    try:
        url = f"https://github.com/search?q={query.replace(' ', '+')}&type=repositories"
        logger.info(f"Opening GitHub search URL: {url}")
        console.print(f"\n[blue]Opening GitHub search:[/blue] {url}")
        webbrowser.open(url)
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Failed to open web browser for GitHub search", e)
        console.print(Panel(
            f"[red]Failed to open web browser.[/red]\n\n"
            f"[bold]Error:[/bold] {str(e)}\n\n"
            "[bold cyan]Manual search:[/bold cyan]\n"
            f"- Visit: https://github.com/search?q={query.replace(' ', '+')}&type=repositories\n"
            "- Or search manually on GitHub",
            title="Browser Error", 
            border_style="red"
        ))

def handle_upgrade_command() -> None:
    """Handle the upgrade command to update arjax from GitHub."""
    logger.info("Starting arjax upgrade process")
    
    console.print(Panel(
        "[bold cyan]🔄 Upgrading arjax from GitHub...[/bold cyan]\n\n"
        "[dim]This will pull the latest code and reinstall arjax.[/dim]",
        title="Arjax Upgrade",
        border_style="cyan"
    ))
    
    console.print("[blue]📥 Pulling latest changes from repository...[/blue]")
    # Upgrade the active environment instead of a separate pipx install.
    upgrade_cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--force-reinstall",
        "git+https://github.com/AdmGenSameer/archpkg-helper.git",
    ]
    logger.info(f"Executing upgrade command: {' '.join(upgrade_cmd)}")
    
    try:
        console.print("[blue]📦 Reinstalling with latest code...[/blue]\n")
        result = subprocess.run(upgrade_cmd, check=False)
        exit_code = result.returncode
        
        if exit_code != 0:
            logger.error(f"Upgrade failed with exit code: {exit_code}")
            console.print(Panel(
                f"[red]❌ Upgrade failed with exit code {exit_code}.[/red]\n\n"
                "[bold cyan]Troubleshooting:[/bold cyan]\n"
                "- Check your internet connection\n"
                "- Ensure you can access GitHub (https://github.com)\n"
                "- Try again in a few moments\n"
                "- Confirm this command is running from the installed ArchPkg environment\n\n"
                "[bold yellow]Manual upgrade:[/bold yellow]\n"
                f"Run: [cyan]{' '.join(upgrade_cmd)}[/cyan]",
                title="Upgrade Failed",
                border_style="red"
            ))
        else:
            logger.info("Successfully upgraded arjax")
            console.print(Panel(
                "[bold green]✅ Successfully upgraded arjax! You now have the latest features![/bold green]\n\n"
                "[bold cyan]💡 Tip:[/bold cyan] Run [cyan]arjax --help[/cyan] to see what's new!",
                title="Upgrade Complete",
                border_style="green"
            ))
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Unexpected error during upgrade", e)
        console.print(Panel(
            f"[red]❌ An unexpected error occurred during upgrade.[/red]\n\n"
            f"[bold]Error details:[/bold] {str(e)}\n\n"
            "[bold cyan]What to do:[/bold cyan]\n"
            "- Check your internet connection\n"
            "- Make sure the current Python environment can access pip and GitHub\n"
            f"- Try running manually: [cyan]{' '.join(upgrade_cmd)}[/cyan]\n"
            "- Report this issue if it persists",
            title="Upgrade Error",
            border_style="red"
        ))

def install_gui_dependencies() -> None:
    """Install GUI dependencies into the current ArchPkg Python environment."""
    logger.info("Installing GUI dependencies into the current environment")

    console.print(Panel(
        "[bold cyan]Installing GUI support...[/bold cyan]\n\n"
        "This installs [cyan]PyQt5[/cyan] into the same Python environment that runs [cyan]arjax[/cyan].",
        title="GUI Setup",
        border_style="cyan"
    ))

    install_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "PyQt5"]

    try:
        result = subprocess.run(install_cmd, check=False)
        if result.returncode != 0:
            logger.error("GUI dependency installation failed with exit code %s", result.returncode)
            console.print(Panel(
                "[red]Failed to install GUI dependencies automatically.[/red]\n\n"
                f"Manual fallback:\n[cyan]{' '.join(install_cmd)}[/cyan]",
                title="GUI Install Failed",
                border_style="red"
            ))
            raise typer.Exit(1)

        console.print(Panel(
            "[bold green]GUI support installed successfully.[/bold green]\n\n"
            "You can now run: [cyan]arjax gui[/cyan]",
            title="GUI Ready",
            border_style="green"
        ))
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Unexpected error installing GUI dependencies", e)
        console.print(Panel(
            f"[red]Could not install GUI dependencies.[/red]\n\n"
            f"[bold]Error:[/bold] {str(e)}\n\n"
            f"Manual fallback:\n[cyan]{' '.join(install_cmd)}[/cyan]",
            title="GUI Install Error",
            border_style="red"
        ))
        raise typer.Exit(1)


def _remove_startup_path_block(shell_file: Path) -> bool:
    """Remove the launcher PATH block from a shell startup file."""
    if not shell_file.exists():
        return False

    try:
        content = shell_file.read_text(encoding="utf-8")
    except Exception:
        return False

    if STARTUP_BLOCK not in content:
        return False

    shell_file.write_text(content.replace(STARTUP_BLOCK, "\n"), encoding="utf-8")
    return True


def uninstall_arjax(purge: bool = False, confirm: bool = True) -> None:
    """Remove the installed Arjax launcher, venv, and desktop entry."""
    console.print(Panel(
        "[bold yellow]Removing Arjax installation...[/bold yellow]\n\n"
        f"Install root: [cyan]{INSTALL_ROOT}[/cyan]\n"
        f"Launcher: [cyan]{BIN_PATH}[/cyan]\n"
        f"Desktop entry: [cyan]{DESKTOP_ENTRY}[/cyan]",
        title="Arjax Uninstall",
        border_style="yellow"
    ))

    if confirm and not typer.confirm("Continue with uninstall?", default=False):
        console.print("[cyan]Uninstall cancelled.[/cyan]")
        raise typer.Exit(0)

    removed_paths: List[str] = []

    for path in (DESKTOP_ENTRY, BIN_PATH):
        if path.exists():
            try:
                path.unlink()
                removed_paths.append(str(path))
            except Exception as e:
                console.print(f"[red]Failed to remove {path}: {e}[/red]")

    if INSTALL_ROOT.exists():
        try:
            shutil.rmtree(INSTALL_ROOT)
            removed_paths.append(str(INSTALL_ROOT))
        except Exception as e:
            console.print(f"[red]Failed to remove install directory {INSTALL_ROOT}: {e}[/red]")

    for shell_file in (Path.home() / ".profile", Path.home() / ".bashrc", Path.home() / ".zshrc"):
        if _remove_startup_path_block(shell_file):
            removed_paths.append(str(shell_file))

    if purge and CONFIG_DIR.exists():
        try:
            shutil.rmtree(CONFIG_DIR)
            removed_paths.append(str(CONFIG_DIR))
        except Exception as e:
            console.print(f"[red]Failed to remove config directory {CONFIG_DIR}: {e}[/red]")

    console.print(Panel(
        "[bold green]Arjax uninstall completed.[/bold green]\n\n"
        "If your desktop menu still shows the app, log out and back in or refresh the menu cache.",
        title="Uninstall Complete",
        border_style="green"
    ))

    if removed_paths:
        console.print("[dim]Removed:[/dim]")
        for item in removed_paths:
            console.print(f"  • {item}")

def handle_search_errors(source_name: str, error: Exception) -> None:
    """Centralized error handling for search operations."""
    PackageHelperLogger.log_exception(logger, f"{source_name} search failed", error)
    
    error_messages = {
        "aur": {
            "network": "Cannot connect to AUR servers. Check your internet connection.",
            "timeout": "AUR search timed out. Try again later.",
            "generic": "AUR search failed. The service might be temporarily unavailable."
        },
        "pacman": {
            "not_found": "pacman command not found. Install pacman or run on Arch-based system.",
            "permission": "Permission denied running pacman. Check your user permissions.",
            "generic": "pacman search failed. Ensure pacman is properly installed."
        },
        "flatpak": {
            "not_found": "flatpak command not found. Install flatpak first.",
            "no_remotes": "No Flatpak remotes configured. Run: flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo",
            "generic": "Flatpak search failed. Ensure Flatpak is properly configured."
        },
        "snap": {
            "not_found": "snap command not found. Install snapd first.",
            "not_running": "snapd service is not running. Run: sudo systemctl start snapd",
            "generic": "Snap search failed. Ensure snapd is installed and running."
        },
        "apt": {
            "not_found": "apt-cache command not found. Run on Debian/Ubuntu-based system.",
            "update_needed": "Package cache is outdated. Run: sudo apt update",
            "generic": "APT search failed. Update package cache or check APT configuration."
        },
        "dnf": {
            "not_found": "dnf command not found. Run on Fedora/RHEL-based system.",
            "cache_error": "DNF cache error. Try: sudo dnf clean all && sudo dnf makecache",
            "generic": "DNF search failed. Check DNF configuration or try clearing cache."
        },
        "zypper": {
            "not_found": "zypper command not found. Run on openSUSE-based system.",
            "cache_error": "Zypper cache error. Try: sudo zypper refresh",
            "generic": "Zypper search failed. Check Zypper configuration or try refreshing cache."
        }
    }
    
    # Determine specific error type
    if isinstance(error, (NetworkError, ConnectionError)):
        error_type = "network"
    elif isinstance(error, TimeoutError):
        error_type = "timeout"
    elif isinstance(error, PackageManagerNotFound):
        error_type = "not_found"
    elif isinstance(error, PermissionError):
        error_type = "permission"
    else:
        error_type = "generic"
    
    message = error_messages.get(source_name, {}).get(error_type, f"{source_name} search encountered an error.")
    console.print(f"[yellow]{source_name.upper()}: {message}[/yellow]")

def batch_install_packages(package_names: List[str]) -> None:
    """Install multiple packages in batch mode with progress tracking."""
    logger.info(f"Starting batch installation for packages: {package_names}")
    
    if not package_names:
        logger.warning("No packages specified for batch installation")
        console.print("[red]No packages specified for batch installation.[/red]")
        return
    
    detected = detect_distro()
    console.print(f"\n[bold cyan]Batch Installation Mode[/bold cyan]")
    console.print(f"Target platform: [cyan]{detected}[/cyan]")
    console.print(f"Packages to install: [yellow]{', '.join(package_names)}[/yellow]\n")
    
    # Validate all packages first
    console.print("[blue]Validating packages...[/blue]")
    validated_packages = []
    validation_errors = []
    
    for i, pkg_name in enumerate(package_names, 1):
        console.print(f"  [{i}/{len(package_names)}] Checking '{pkg_name}'...")
        
        results = []
        search_errors = []
        
        # Search based on detected distribution
        if detected == "arch":
            try:
                aur_results = search_aur(pkg_name)
                results.extend(aur_results)
            except Exception as e:
                search_errors.append("AUR")
                
            try:
                pacman_results = search_pacman(pkg_name) 
                results.extend(pacman_results)
            except Exception as e:
                search_errors.append("Pacman")
                
        elif detected == "debian":
            try:
                apt_results = search_apt(pkg_name)
                results.extend(apt_results)
            except Exception as e:
                search_errors.append("APT")
                
        elif detected == "fedora":
            try:
                dnf_results = search_dnf(pkg_name)
                results.extend(dnf_results)
            except Exception as e:
                search_errors.append("DNF")

        # Universal package managers
        try:
            flatpak_results = search_flatpak(pkg_name)
            results.extend(flatpak_results)
        except Exception:
            search_errors.append("Flatpak")

        try:
            snap_results = search_snap(pkg_name)
            results.extend(snap_results)
        except Exception:
            search_errors.append("Snap")

        if not results:
            validation_errors.append(f"'{pkg_name}': No packages found")
            console.print(f"    [red]✗[/red] No packages found")
            continue
            
        top_matches = get_top_matches(pkg_name, results, limit=1)  # Get only the best match
        if not top_matches:
            validation_errors.append(f"'{pkg_name}': No suitable matches found")
            console.print(f"    [red]✗[/red] No suitable matches found")
            continue
            
        pkg, desc, source = top_matches[0]
        command = generate_command(pkg, source)
        
        if not command:
            validation_errors.append(f"'{pkg_name}': Cannot generate install command for {source}")
            console.print(f"    [red]✗[/red] Cannot generate install command")
            continue
            
        validated_packages.append((pkg_name, pkg, desc, source, command))
        console.print(f"    [green]✓[/green] Found: {pkg} ({source})")
    
    if validation_errors:
        console.print(f"\n[red]Validation failed for {len(validation_errors)} package(s):[/red]")
        for error in validation_errors:
            console.print(f"  - {error}")
        console.print("\n[yellow]Batch installation cancelled due to validation errors.[/yellow]")
        return
    
    console.print(f"\n[green]✓ All {len(validated_packages)} packages validated successfully![/green]\n")
    
    # Proceed with installation
    console.print("[blue]Starting batch installation...[/blue]\n")
    
    successful_installs = []
    failed_installs = []
    
    for i, (original_name, pkg, desc, source, command) in enumerate(validated_packages, 1):
        console.print(f"[{i}/{len(validated_packages)}] Installing [bold cyan]{pkg}[/bold cyan] ({source})...")
        console.print(f"  Command: [dim]{command}[/dim]")
        
        logger.info(f"Installing package {i}/{len(validated_packages)}: {pkg} from {source}")
        exit_code = os.system(command)
        
        if exit_code == 0:
            console.print(f"  [green]✓[/green] Successfully installed {pkg}")
            successful_installs.append(pkg)
        else:
            console.print(f"  [red]✗[/red] Failed to install {pkg} (exit code: {exit_code})")
            failed_installs.append((pkg, exit_code))
    
    # Show summary
    console.print(f"\n[bold]Batch Installation Summary:[/bold]")
    console.print(f"Total packages: {len(validated_packages)}")
    console.print(f"[green]Successful: {len(successful_installs)}[/green]")
    
    if successful_installs:
        console.print(f"  - {', '.join(successful_installs)}")
    
    if failed_installs:
        console.print(f"[red]Failed: {len(failed_installs)}[/red]")
        for pkg, code in failed_installs:
            console.print(f"  - {pkg} (exit code: {code})")
    
    if failed_installs:
        console.print(f"\n[yellow]Note: {len(failed_installs)} package(s) failed to install. Check the errors above.[/yellow]")

def show_custom_help() -> None:
    """Display comprehensive custom help text."""
    help_text = """
[bold cyan]🎯 ArchPkg Helper - Universal Package Manager for All Linux Distros[/bold cyan]

[bold yellow]📦 What does it do?[/bold yellow]
   Searches and installs packages across multiple sources:
   ✓ Official repos (pacman, apt, dnf, zypper)
   ✓ AUR (Arch User Repository)
   ✓ Flatpak & Snap (works on any distro)

[bold yellow]🔍 SEARCH FOR PACKAGES[/bold yellow]
   [cyan]arjax search <package-name>[/cyan]
   [cyan]arjax <package-name>[/cyan]             [dim](search is default)[/dim]
   
   Examples:
   [green]🔸 arjax firefox[/green]
   [green]🔸 arjax visual studio code[/green]
   [green]🔸 arjax search telegram[/green]
   
   Options:
   [cyan]--aur[/cyan]              Prefer AUR packages over official repos
   [cyan]--no-cache[/cyan]         Skip cache, search fresh results
   [cyan]--limit, -l[/cyan]        Maximum results to show (default: 5)

[bold yellow]📦 INSTALL SOFTWARE[/bold yellow]
    [cyan]arjax install <package-name>[/cyan]
    [cyan]arjax install <package-name> --provider <name>[/cyan]

    Providers:
    [green]repository[/green], [green]vendor[/green], [green]github[/green], [green]flatpak[/green], [green]snap[/green], [green]appimage[/green]

[bold yellow]💡 GET APP SUGGESTIONS BY PURPOSE[/bold yellow]
   [cyan]arjax suggest <purpose>[/cyan]
   
   Examples:
   [green]🔸 arjax suggest video editing[/green]
   [green]🔸 arjax suggest coding[/green]
   [green]🔸 arjax suggest gaming[/green]
   
   [cyan]--list[/cyan]             Show all available purposes

[bold yellow]🌐 WEB INTERFACE[/bold yellow]
   [cyan]arjax web[/cyan]                        Launch web UI
   [cyan]arjax web --port 8080[/cyan]            Use custom port

[bold yellow]📦 PACKAGE TRACKING & UPDATES[/bold yellow]
   [cyan]arjax list-installed[/cyan]             List tracked packages
   [cyan]arjax update[/cyan]                     Install updates
   [cyan]arjax update --check-only[/cyan]        Only check for updates

[bold yellow]⚙️  CONFIGURATION[/bold yellow]
   [cyan]arjax config --list[/cyan]              Show all settings
   [cyan]arjax config <key> <value>[/cyan]       Set a config value

[bold yellow]🔄 BACKGROUND SERVICE[/bold yellow]
   [cyan]arjax service start|stop|status[/cyan]

[bold yellow]🔄 UPGRADE ARJAX[/bold yellow]
   [cyan]arjax upgrade[/cyan]                    Get latest version from GitHub

[bold yellow]🧹 UNINSTALL ARJAX[/bold yellow]
    [cyan]arjax uninstall[/cyan]                  Remove launcher, desktop entry, and venv
    [cyan]arjax uninstall --purge[/cyan]          Also remove saved config

[bold yellow]🌍 SUPPORTED DISTRIBUTIONS[/bold yellow]
   [green]Arch, Manjaro, EndeavourOS, Ubuntu, Debian, Fedora,
   openSUSE, + any distro with Flatpak/Snap support[/green]

[bold yellow]📚 MORE INFORMATION[/bold yellow]
   Run [cyan]arjax <command> --help[/cyan] for detailed help on any command
   Visit: [blue]https://github.com/AdmGenSameer/arjax[/blue]
"""
    console.print(help_text)

def main() -> None:
    """
    Main entrypoint for CLI search + install flow.
    IMPROVED: Better type annotations and error handling.
    Handles custom help display and default search fallback.
    """
    # Check for help flag first
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h', 'help']:
        show_custom_help()
        return
    
    # Check if first argument is a known subcommand
    known_commands = ['search', 'install', 'suggest', 'upgrade', 'web', 'update', 'config', 'list-installed', 'service', 'cleanup', 'snapshot', 'setup', 'gui', 'uninstall']
    
    # If no arguments or first arg is not a known command, inject 'search' for backward compatibility
    if len(sys.argv) > 1 and sys.argv[1] not in known_commands and not sys.argv[1].startswith('-'):
        # First argument is not a known command, treat it as a search query
        logger.info(f"No known subcommand detected, injecting 'search' command")
        sys.argv.insert(1, 'search')
    
    app()

# Typer Commands

@app.callback()
def callback():
    """
    🎯 Arjax - Universal Package Manager for All Linux Distros

    📦 What does it do?
       Searches and installs packages across multiple sources:
       ✓ Official repos (pacman, apt, dnf, zypper)
       ✓ AUR (Arch User Repository)
       ✓ Flatpak & Snap (works on any distro)

    🔍 SEARCH FOR PACKAGES
       arjax search <package-name>
       arjax <package-name>             (search is default)
       
       Examples:
       🔸 arjax firefox
       🔸 arjax visual studio code
       🔸 arjax search telegram
       
       Options:
       --aur              Prefer AUR packages over official repos
       --no-cache         Skip cache, search fresh results
       --limit, -l        Maximum results to show (default: 5)

    💡 GET APP SUGGESTIONS BY PURPOSE
       arjax suggest <purpose>
       
       Examples:
       🔸 arjax suggest video editing
       🔸 arjax suggest coding
       🔸 arjax suggest gaming
       
       --list             Show all available purposes

    🌐 WEB INTERFACE
       arjax web                        Launch web UI
       arjax web --port 8080            Use custom port

    📦 PACKAGE TRACKING & UPDATES
       arjax list-installed             List tracked packages
       arjax update                     Install updates
       arjax update --check-only        Only check for updates

    ⚙️ CONFIGURATION
       arjax config --list              Show all settings
       arjax config <key> <value>       Set a config value

    🔄 BACKGROUND SERVICE
       arjax service start|stop|status

    🔄 UPGRADE ARJAX
       arjax upgrade                    Get latest version from GitHub

     🧹 UNINSTALL ARJAX
         arjax uninstall                  Remove launcher, desktop entry, and venv
         arjax uninstall --purge          Also remove saved config

    🌍 SUPPORTED DISTRIBUTIONS
       Arch, Manjaro, EndeavourOS, Ubuntu, Debian, Fedora,
       openSUSE, + any distro with Flatpak/Snap support
    """
    pass

@app.command()
def install(
    package: str = Argument(..., help="Package or recipe name to install"),
    provider: Optional[str] = Option(None, "--provider", "-p", help="Force a specific provider: repository, vendor, github, flatpak, snap, appimage"),
    debug: bool = Option(False, "--debug", help="Enable debug logging")
) -> None:
    """
    Install software using the provider-based installation engine.

    The installation path is separate from search. Recipes can map a package
    name to repository, vendor, GitHub, Flatpak, Snap, or AppImage metadata.
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)

    orchestrator = InstallationOrchestrator()
    result = orchestrator.install(package, provider_hint=provider)

    if result.success:
        return

    raise typer.Exit(1)

@app.command()
def search(
    query: List[str] = Argument(..., help="Name of the software to search for"),
    debug: bool = Option(False, "--debug", help="Enable debug logging"),
    limit: int = Option(5, "--limit", "-l", help="Maximum number of results to show"),
    aur: bool = Option(False, "--aur", help="Prefer AUR packages over Pacman"),
    aur_sortby: str = Option(
        "votes",
        "--aur-sortby",
        help=(
            "Sort AUR results by one of: votes, popularity, id, baseid, "
            "name, base, submitted, modified"
        ),
    ),
    no_cache: bool = Option(False, "--no-cache", help="Bypass cache and perform fresh search")
) -> None:
    """
    Search for packages across all available package managers.
    
    Supports multi-word queries: arjax search visual studio code
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)

    # Join multi-word queries
    query_str = ' '.join(query)
    logger.info(f"Searching for: {query_str}")

    if not query_str.strip():
        console.print("[red]Error: Empty search query[/red]")
        raise typer.Exit(1)

    valid_aur_sort_fields = {
        'votes', 'popularity', 'id', 'baseid', 'name', 'base', 'submitted', 'modified'
    }
    aur_sortby = aur_sortby.strip().lower()
    if aur_sortby not in valid_aur_sort_fields:
        console.print(
            "[red]Invalid --aur-sortby value.[/red] "
            "Use one of: votes, popularity, id, baseid, name, base, submitted, modified"
        )
        raise typer.Exit(1)

    # Initialize cache manager
    cache_config = CacheConfig(enabled=not no_cache)
    cache_manager = get_cache_manager(cache_config)

    # Detect distribution and search
    detected = detect_distro()
    console.print(f"\nSearching for '{query_str}' on [cyan]{detected}[/cyan] platform...\n")

    # Generate query variations for better matching
    query_variations = normalize_query(query_str)
    logger.info(f"Searching with {len(query_variations)} query variations: {query_variations}")

    # Use the shortest variation for external sources (pkgs.org) to improve hit rate
    pkgs_org_query = min(query_variations, key=len)

    results = []
    search_errors = []
    use_cache = not no_cache
    
    # Start async pkgs.org search in background
    pkgs_org_results = []
    pkgs_org_thread = None
    
    def async_pkgs_org_search():
        nonlocal pkgs_org_results
        try:
            logger.debug("Background pkgs.org search started")
            pkgs_org_results = search_pkgs_org(pkgs_org_query, detected, limit=10)
            logger.debug(f"Background pkgs.org search completed: {len(pkgs_org_results)} results")
        except Exception as e:
            logger.debug(f"Background pkgs.org search failed: {e}")
    
    # Launch background search
    pkgs_org_thread = threading.Thread(target=async_pkgs_org_search, daemon=True)
    pkgs_org_thread.start()

    # Search with all query variations
    for query_variant in query_variations:
        logger.debug(f"Searching with query variant: '{query_variant}'")
        
        # Search based on detected distribution
        if detected == "arch":
            try:
                logger.debug("Starting AUR search")
                aur_results = search_aur(
                    query_variant,
                    cache_manager if use_cache else None,
                    sort_by=aur_sortby,
                )
                results.extend(aur_results)
            except Exception as e:
                logger.debug(f"AUR search failed: {e}")
                if query_variant == query_str:  # Only log errors for the original query
                    search_errors.append("AUR")

            try:
                logger.debug("Starting pacman search")
                pacman_results = search_pacman(query_variant, cache_manager if use_cache else None) 
                results.extend(pacman_results)
            except Exception as e:
                logger.debug(f"Pacman search failed: {e}")
                if query_variant == query_str:
                    search_errors.append("Pacman")

        elif detected == "debian":
            try:
                logger.debug("Starting APT search")
                apt_results = search_apt(query_variant, cache_manager if use_cache else None)
                results.extend(apt_results)
            except Exception as e:
                logger.debug(f"APT search failed: {e}")
                if query_variant == query_str:
                    search_errors.append("APT")

        elif detected == "fedora":
            try:
                logger.debug("Starting DNF search")
                dnf_results = search_dnf(query_variant, cache_manager if use_cache else None)
                results.extend(dnf_results)
            except Exception as e:
                logger.debug(f"DNF search failed: {e}")
                if query_variant == query_str:
                    search_errors.append("DNF")
            
            # Fallback to RPM if DNF fails
            try:
                logger.debug("Starting RPM search as fallback")
                rpm_results = search_rpm(query_variant, limit=limit)
                results.extend(rpm_results)
            except Exception as e:
                logger.debug(f"RPM search failed: {e}")
                
        elif detected == "suse":
            logger.info("Searching openSUSE-based repositories (Zypper)")
            
            try:
                logger.debug("Starting Zypper search")
                zypper_results = search_zypper(query_variant, cache_manager if use_cache else None)
                results.extend(zypper_results)
                logger.info(f"Zypper search returned {len(zypper_results)} results")
            except Exception as e:
                if query_variant == query_str:
                    handle_search_errors("zypper", e)
                    search_errors.append("Zypper")

        # Universal package managers
        try:
            logger.debug("Starting Flatpak search")
            flatpak_results = search_flatpak(query_variant, cache_manager if use_cache else None)
            results.extend(flatpak_results)
        except Exception as e:
            logger.debug(f"Flatpak search failed: {e}")
            if query_variant == query_str:
                search_errors.append("Flatpak")

        try:
            logger.debug("Starting Snap search")
            snap_results = search_snap(query_variant, cache_manager if use_cache else None)
            results.extend(snap_results)
        except Exception as e:
            logger.debug(f"Snap search failed: {e}")
            if query_variant == query_str:
                search_errors.append("Snap")
    
    # Remove duplicate error messages
    search_errors = list(set(search_errors))

    # Show available vs unavailable sources only in debug mode
    if search_errors:
        logger.debug(f"Note: Some sources unavailable: {', '.join(search_errors)}")
    
    # Wait for background pkgs.org search to complete (max 5 seconds)
    if pkgs_org_thread and pkgs_org_thread.is_alive():
        logger.debug("Waiting for background pkgs.org search...")
        pkgs_org_thread.join(timeout=5.0)
    
    if not results:
        logger.info("No results found in local package managers")
        
        if pkgs_org_results:
            # Show pkgs.org results
            console.print(Panel(
                f"[yellow]No packages found in your local repositories.[/yellow]\n\n"
                f"[bold cyan]However, '{query_str}' is available on other distributions:[/bold cyan]",
                title="📦 Cross-Distribution Search",
                border_style="cyan"
            ))
            
            # Display pkgs.org results in a table with install commands
            table = Table(title="Available on Other Distributions (via pkgs.org)", width=120, expand=False)
            table.add_column("Package Name", style="green")
            table.add_column("Distribution/Repo", style="blue")
            table.add_column("Description", style="magenta")
            table.add_column("Install Command", style="yellow")
            
            for pkg_dict in pkgs_org_results[:limit]:
                name = pkg_dict.get("name", "")
                desc = pkg_dict.get("summary", "") or pkg_dict.get("description", "No description")
                distro = pkg_dict.get("distro", "Unknown")
                repo = pkg_dict.get("repo", "")
                source_label = f"{distro}" + (f" ({repo})" if repo else "")
                
                # Extract install command if available
                install_cmd = pkg_dict.get("install_command", "")
                if not install_cmd and pkg_dict.get("url"):
                    install_cmd = f"Visit: {pkg_dict.get('url')}"
                
                table.add_row(name, source_label, desc or "No description", install_cmd or "Manual install")
            
            console.print(table)
            
            # Show cross-distro availability summary
            show_pkgs_org_availability(pkgs_org_results)
            
            console.print("\n[bold yellow]💡 Suggestions:[/bold yellow]")
            console.print("  • This package may be in a third-party repository")
            console.print("  • Check if you need to enable additional repos")
            console.print("  • Try installing via Snap or Flatpak (see below)")
            
            # Offer automatic installation if we have direct commands
            installable = [p for p in pkgs_org_results if p.get("install_command")]
            if installable:
                console.print(f"\n[bold green]✨ {len(installable)} package(s) have direct install commands available[/bold green]")
            console.print()
        
        # Show special guidance for Brave browser on openSUSE
        if detected == "suse" and "brave" in query_str.lower():
            show_opensuse_brave_guidance()
        
        # Always show the GitHub fallback and installation suggestions
        github_fallback(query_str, search_errors)
        return

    deduplicated_results = deduplicate_packages(results, prefer_aur=aur)
    logger.info(f"After deduplication: {len(deduplicated_results)} unique packages")
    
    # Show pkgs.org supplementary results if available (even when local results exist)
    if pkgs_org_results and len(pkgs_org_results) > 0:
        console.print("\n[dim]📦 Additional packages available on other distributions:[/dim]")
        pkgs_summary = []
        for pkg_dict in pkgs_org_results[:3]:
            name = pkg_dict.get("name", "")
            distro = pkg_dict.get("distro", "Unknown")
            pkgs_summary.append(f"{name} ({distro})")
        console.print(f"[dim]  {', '.join(pkgs_summary)}[/dim]")
        if len(pkgs_org_results) > 3:
            console.print(f"[dim]  +{len(pkgs_org_results)-3} more available via pkgs.org[/dim]\n")
        else:
            console.print()

    top_matches = get_top_matches(query_str, deduplicated_results, limit=limit)
    if not top_matches:
        console.print("[yellow]No close matches found.[/yellow]")
        raise typer.Exit(1)

    # Display results with terminal width constraints
    console_width = console.width if hasattr(console, 'width') else 120
    table = Table(title="Matching Packages", width=min(console_width, 120), expand=False)
    table.add_column("Index", style="cyan", no_wrap=True)
    table.add_column("Package Name", style="green")
    table.add_column("Source", style="blue")
    table.add_column("Trust", style="yellow", no_wrap=True)
    table.add_column("Description", style="magenta")

    for idx, (pkg, desc, source) in enumerate(top_matches, 1):
        # Calculate trust score for AUR packages
        trust_display = "-"
        if source == 'aur':
            try:
                trust_result = assess_aur_trust(pkg)
                score = trust_result.get('score', 0)
                if score >= 75:
                    trust_display = f"[green]{score}[/green]"
                elif score >= 50:
                    trust_display = f"[yellow]{score}[/yellow]"
                else:
                    trust_display = f"[red]{score}[/red]"
            except Exception:
                trust_display = "?"
        
        table.add_row(str(idx), pkg, source, trust_display, desc or "No description")

    console.print(table)
    console.print("\n[cyan]Search is now read-only. Install with: arjax install <package>[/cyan]")
    return


@app.command()
def suggest(
    purpose: Optional[List[str]] = Argument(None, help="Purpose or use case (e.g., 'video editing', 'office')"),
    list_all: bool = Option(False, "--list", help="List all available purposes"),
    debug: bool = Option(False, "--debug", help="Enable debug logging")
) -> None:
    """
    Get app suggestions based on purpose.
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)

    if list_all:
        logger.info("Listing all available purposes")
        list_purposes()
        return
    
    if not purpose:
        console.print(Panel(
            "[red]No purpose specified.[/red]\n\n"
            "[bold cyan]Usage:[/bold cyan]\n"
            "- [cyan]arjax suggest video editing[/cyan] - Get video editing apps\n"
            "- [cyan]arjax suggest office[/cyan] - Get office applications\n"
            "- [cyan]arjax suggest --list[/cyan] - List all available purposes\n"
            "- [cyan]arjax suggest --help[/cyan] - Show help information",
            title="No Purpose Specified",
            border_style="red"
        ))
        raise typer.Exit(1)
    
    purpose_str = ' '.join(purpose)
    logger.info(f"Purpose suggestion query: '{purpose_str}'")
    
    if not purpose_str.strip():
        logger.warning("Empty purpose query provided by user")
        console.print(Panel(
            "[red]Empty purpose query provided.[/red]\n\n"
            "[bold cyan]Usage:[/bold cyan]\n"
            "- [cyan]arjax suggest video editing[/cyan] - Get video editing apps\n"
            "- [cyan]arjax suggest office[/cyan] - Get office applications\n"
            "- [cyan]arjax suggest --list[/cyan] - List all available purposes",
            title="Invalid Input",
            border_style="red"
        ))
        raise typer.Exit(1)
    
    # Display suggestions
    suggest_apps(purpose_str)


@app.command()
def upgrade(
    debug: bool = Option(False, "--debug", help="Enable debug logging")
) -> None:
    """
    Upgrade arjax tool itself from GitHub.
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)
    
    logger.info("Starting arjax upgrade from GitHub")
    handle_upgrade_command()


@app.command()
def gui(
    debug_mode: bool = Option(False, "--debug", help="Enable debug mode")
) -> None:
    """
    Launch the native desktop GUI for package management.
    
    The GUI provides a professional interface for:
    - Searching and installing packages across all sources
    - Managing installed packages
    - System maintenance (updates, cleanup, snapshots)
    - Configuring settings and user profiles
    
    Supports all distributions (Arch, Debian, Fedora, openSUSE, etc.)
    """
    try:
        from arjax.interfaces.gui import launch_gui
        
        if debug_mode:
            PackageHelperLogger.set_debug_mode(True)
        
        console.print("[cyan]Launching desktop GUI...[/cyan]")
        launch_gui()
        
    except ImportError as e:
        console.print("[red]GUI dependencies not installed.[/red]")
        console.print("Run: arjax add gui")
        console.print(f"Error: {str(e)}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to launch GUI: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def uninstall(
    purge: bool = Option(False, "--purge", help="Also remove saved Arjax configuration"),
    yes: bool = Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    debug: bool = Option(False, "--debug", help="Enable debug logging")
) -> None:
    """Uninstall Arjax and remove its launcher files."""
    if debug:
        PackageHelperLogger.set_debug_mode(True)

    uninstall_arjax(purge=purge, confirm=not yes)


@app.command()
def add(
    component: str = Argument(..., help="Optional component to add, for example: gui"),
    debug: bool = Option(False, "--debug", help="Enable debug logging")
) -> None:
    """Install optional Arjax components such as the desktop GUI."""
    if debug:
        PackageHelperLogger.set_debug_mode(True)

    selected_component = component.strip().lower()

    if selected_component == "gui":
        install_gui_dependencies()
        return

    console.print(Panel(
        f"[red]Unknown optional component: {component}[/red]\n\n"
        "[bold cyan]Supported components:[/bold cyan]\n"
        "- gui",
        title="Unsupported Component",
        border_style="red"
    ))
    raise typer.Exit(1)


@app.command()
def setup(
    mode: Optional[str] = Option(None, "--mode", help="Choose profile: normal (recommended) or advanced"),
    debug: bool = Option(False, "--debug", help="Enable debug logging")
) -> None:
    """Interactive onboarding for normal vs advanced user profiles."""
    if debug:
        PackageHelperLogger.set_debug_mode(True)

    selected_mode = mode
    if not selected_mode:
        console.print("[bold cyan]Choose your profile:[/bold cyan]")
        console.print("  1) normal (recommended) - arjax handles updates/news/trust checks automatically")
        console.print("  2) advanced - full manual control")
        choice = typer.prompt("Enter choice", default="1").strip()
        selected_mode = 'advanced' if choice == '2' else 'normal'

    selected_mode = selected_mode.strip().lower()
    if selected_mode not in ('normal', 'advanced'):
        console.print("[red]Invalid mode. Use: normal or advanced[/red]")
        raise typer.Exit(1)

    defaults = apply_user_mode_defaults(selected_mode)
    cfg = get_user_config()
    for key, value in defaults.items():
        setattr(cfg, key, value)
    save_user_config(cfg)

    if selected_mode == 'normal':
        console.print("[green]Normal profile enabled.[/green]")
        console.print("- Auto-update and advice enabled")
        console.print("- Arch news checked before updates")
        console.print("- AUR trust checks enabled")
        console.print("- Snapshot before updates enabled")
        
        # On Arch, offer to install background monitoring service
        import distro
        detected_distro = distro.id().lower()
        distro_family = DISTRO_MAP.get(detected_distro, detected_distro)
        
        if distro_family == 'arch':
            console.print("\n[cyan]Background monitoring service available for normal mode:[/cyan]")
            console.print("  - Checks for Arch news, updates, and low-trust packages every 6 hours")
            console.print("  - Sends desktop notifications when action is recommended")
            
            if typer.confirm("Would you like to enable background monitoring?", default=True):
                try:
                    import subprocess
                    from pathlib import Path
                    
                    # Find systemd directory
                    project_root = Path(__file__).parent.parent
                    systemd_dir = project_root / 'systemd'
                    service_manager = systemd_dir / 'service-manager.sh'
                    
                    if service_manager.exists():
                        console.print("[cyan]Installing monitoring service...[/cyan]")
                        
                        # Install service
                        result = subprocess.run(
                            [str(service_manager), 'install'],
                            capture_output=True,
                            text=True
                        )
                        
                        if result.returncode == 0:
                            # Enable and start timer
                            result = subprocess.run(
                                [str(service_manager), 'enable'],
                                capture_output=True,
                                text=True
                            )
                            
                            if result.returncode == 0:
                                console.print("[green]✓ Background monitoring service enabled![/green]")
                                console.print("[dim]  Run 'systemctl --user status arjax-monitor.timer' to check status[/dim]")
                            else:
                                console.print("[yellow]Service installed but failed to enable. You can enable it manually with:[/yellow]")
                                console.print(f"[dim]  {service_manager} enable[/dim]")
                        else:
                            console.print("[yellow]Failed to install service automatically.[/yellow]")
                            console.print(f"[dim]You can install it manually: {service_manager} install[/dim]")
                    else:
                        console.print("[yellow]Service files not found. Skipping service installation.[/yellow]")
                        console.print("[dim]If you installed via pip, service files may not be available.[/dim]")
                        
                except Exception as e:
                    console.print(f"[yellow]Could not install monitoring service: {str(e)}[/yellow]")
                    console.print("[dim]You can install it manually later using systemd/service-manager.sh[/dim]")
            else:
                console.print("[dim]You can enable it later with: systemd/service-manager.sh install && systemd/service-manager.sh enable[/dim]")
    else:
        console.print("[green]Advanced profile enabled.[/green]")
        console.print("- Manual control preserved")


@app.command()
def update(
    packages: Optional[List[str]] = Argument(None, help="Specific packages to update (all if not specified)"),
    check_only: bool = Option(False, "--check-only", "-c", help="Only check for updates, don't install"),
    snapshot: bool = Option(False, "--snapshot", help="Create a system snapshot before updating (Arch only)"),
    news_only: bool = Option(False, "--news-only", help="Show Arch news via paru without installing updates"),
    debug: bool = Option(False, "--debug", help="Enable debug logging")
) -> None:
    """
    Check for and install package updates.
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)

    import distro
    import subprocess
    detected_distro = distro.id().lower()
    distro_family = DISTRO_MAP.get(detected_distro, detected_distro)

    config = get_user_config()

    if news_only:
        if distro_family != 'arch':
            console.print("[red]--news-only is currently supported only on Arch-based distributions.[/red]")
            raise typer.Exit(1)
        try:
            result = subprocess.run(['paru', '-Pw'], check=False)
            if result.returncode != 0:
                console.print("[red]Failed to fetch Arch news with paru.[/red]")
                raise typer.Exit(1)
            return
        except FileNotFoundError:
            console.print("[red]paru is required for --news-only.[/red]")
            raise typer.Exit(1)

    # In normal profile, auto-enable snapshot for full system updates on Arch
    effective_snapshot = snapshot or (
        distro_family == 'arch' and
        config.user_mode == 'normal' and
        config.auto_snapshot_before_update and
        not check_only and
        not packages
    )

    if effective_snapshot:
        if distro_family != 'arch':
            console.print("[yellow]Snapshot option is currently tuned for Arch workflows; continuing without snapshot.[/yellow]")
        else:
            console.print("[blue]Creating pre-update snapshot...[/blue]")
            try:
                if create_snapshot(comment="Pre-update snapshot"):
                    console.print("[green]Snapshot created successfully.[/green]")
                else:
                    console.print("[red]Snapshot creation failed.[/red]")
                    raise typer.Exit(1)
            except Exception as e:
                console.print(f"[red]Snapshot creation failed: {str(e)}[/red]")
                raise typer.Exit(1)

    if distro_family == 'arch' and not check_only and not packages:
        if config.proactive_system_advice:
            console.print("[bold cyan]System advice:[/bold cyan] Keep mirrors fresh, ensure enough disk space, and avoid interrupting updates.")

        if config.auto_handle_arch_news:
            news = get_arch_news()
            if news.get('available') and news.get('has_news'):
                console.print("[yellow]Unread Arch news detected. Reviewing news before update...[/yellow]")
                if news.get('output'):
                    console.print(news['output'])

        # Prefer paru for full system updates (official repos + AUR + Arch news flow)
        try:
            console.print("[blue]Running full system update with paru...[/blue]")
            result = subprocess.run(['paru', '-Syu'])
            if result.returncode == 0:
                console.print("[green]System update completed successfully.[/green]")
                return
            console.print("[red]paru update failed.[/red]")
            raise typer.Exit(1)
        except FileNotFoundError:
            console.print("[yellow]paru not found; falling back to default update flow.[/yellow]")

    if check_only:
        console.print("[blue]Checking for updates...[/blue]")
        result = trigger_update_check()

        if result["status"] == "success":
            checked = result["checked"]
            updates_found = result["updates_found"]

            if updates_found > 0:
                console.print(f"[green]Found {updates_found} update(s) available![/green]")
                console.print("Run 'arjax update' to install them.")
            else:
                console.print("[green]All packages are up to date![/green]")
        else:
            console.print(f"[red]Update check failed: {result.get('message', 'Unknown error')}[/red]")
            raise typer.Exit(1)
    else:
        console.print("[blue]Installing updates...[/blue]")
        result = install_updates(packages)

        if result["status"] == "success":
            installed = result["installed"]
            failed = result["failed"]

            if installed > 0:
                console.print(f"[green]Successfully installed {installed} update(s)[/green]")

            if failed > 0:
                console.print(f"[red]Failed to install {failed} update(s)[/red]")
                for item in result["results"]:
                    if item["status"] == "failed":
                        console.print(f"  - {item['package']}: {item.get('error', 'Unknown error')}")

            if installed == 0 and failed == 0:
                console.print("[green]No updates available[/green]")
        else:
            console.print("[red]Update installation failed[/red]")
            raise typer.Exit(1)

@app.command()
def config(
    key: Optional[str] = Argument(None, help="Configuration key to get/set"),
    value: Optional[str] = Argument(None, help="Value to set (if setting)"),
    list_all: bool = Option(False, "--list", "-l", help="List all configuration settings"),
    debug: bool = Option(False, "--debug", help="Enable debug logging")
) -> None:
    """
    Manage arjax configuration settings.
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)

    config = get_user_config()

    if list_all:
        console.print("[bold]Current Configuration:[/bold]")
        for k, v in config.__dict__.items():
            if not k.startswith('_'):
                console.print(f"  {k}: {v}")
        return

    if key is None:
        console.print("[red]Error: Specify a configuration key or use --list[/red]")
        raise typer.Exit(1)

    if value is None:
        # Get configuration value
        if hasattr(config, key):
            console.print(f"{key}: {getattr(config, key)}")
        else:
            console.print(f"[red]Unknown configuration key: {key}[/red]")
            raise typer.Exit(1)
    else:
        # Set configuration value
        try:
            # Convert value to appropriate type
            from typing import Any
            converted_value: Any = value
            if value.lower() in ('true', 'false'):
                converted_value = value.lower() == 'true'
            elif value.isdigit():
                converted_value = int(value)
            elif value.replace('.', '').isdigit():
                converted_value = float(value)

            set_config_option(key, converted_value)
            console.print(f"[green]Updated {key} = {converted_value}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to update configuration: {e}[/red]")
            raise typer.Exit(1)

@app.command()
def list_installed(
    debug: bool = Option(False, "--debug", help="Enable debug logging")
) -> None:
    """
    List all installed packages being tracked for updates.
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)

    packages = get_all_installed_packages()

    if not packages:
        console.print("[yellow]No packages are currently being tracked for updates.[/yellow]")
        console.print("Use 'arjax install --track' to track packages for updates.")
        return

    # Apply terminal width constraints
    console_width = console.width if hasattr(console, 'width') else 120
    table = Table(title="Tracked Installed Packages", width=min(console_width, 120), expand=False)
    table.add_column("Package Name", style="green")
    table.add_column("Source", style="blue")
    table.add_column("Installed Version", style="cyan")
    table.add_column("Update Available", style="yellow")
    table.add_column("Last Updated", style="magenta")

    for pkg in packages:
        update_status = "[green]No[/green]" if not pkg.update_available else "[red]Yes[/red]"
        last_updated = pkg.last_update_check or pkg.install_date or "Never"
        table.add_row(
            pkg.name,
            pkg.source,
            pkg.version or "Unknown",
            update_status,
            last_updated
        )

    console.print(table)

@app.command()
def service(
    action: str = Argument(..., help="Action to perform: start, stop, status"),
    debug: bool = Option(False, "--debug", help="Enable debug logging")
) -> None:
    """
    Manage the background update service.
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)

    if action == "start":
        start_background_update_service()
        console.print("[green]Background update service started[/green]")
    elif action == "stop":
        stop_background_update_service()
        console.print("[green]Background update service stopped[/green]")
    elif action == "status":
        config = get_user_config()
        if config.auto_update_enabled:
            console.print("[green]Background update service is enabled[/green]")
            console.print(f"Check interval: {config.update_check_interval_hours} hours")
            console.print(f"Auto-update mode: {config.auto_update_mode}")
        else:
            console.print("[yellow]Background update service is disabled[/yellow]")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available actions: start, stop, status")
        raise typer.Exit(1)


@app.command()
def cleanup(
    target: str = Argument(..., help="What to clean: orphans, cache"),
    dry_run: bool = Option(False, "--dry-run", help="Show what would be removed without removing"),
    all_cache: bool = Option(False, "--all", help="Remove all cached packages (for cache cleanup)"),
    debug: bool = Option(False, "--debug", help="Enable debug logging")
) -> None:
    """
    Clean up orphaned packages or package cache (Arch Linux only).
    
    Examples:
        arjax cleanup orphans --dry-run
        arjax cleanup cache
        arjax cleanup cache --all
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)
    
    import distro
    detected_distro = distro.id().lower()
    distro_family = DISTRO_MAP.get(detected_distro, detected_distro)
    
    if distro_family != 'arch':
        console.print("[red]Cleanup commands are currently only supported on Arch-based distributions.[/red]")
        raise typer.Exit(1)
    
    # Check for paru
    import subprocess
    try:
        subprocess.run(['which', 'paru'], capture_output=True, check=True)
    except:
        console.print("[red]paru is required for cleanup operations.[/red]")
        console.print("Install paru: https://github.com/morganamilo/paru")
        raise typer.Exit(1)
    
    if target == "orphans":
        console.print("[cyan]Checking for orphaned packages...[/cyan]")
        
        # Find orphaned packages
        try:
            result = subprocess.run(
                ['paru', '-Qdtq'],
                capture_output=True,
                text=True,
                check=False
            )
            
            orphans = [pkg.strip() for pkg in result.stdout.split('\n') if pkg.strip()]
            
            if not orphans:
                console.print("[green]No orphaned packages found.[/green]")
                return
            
            console.print(f"[yellow]Found {len(orphans)} orphaned package(s):[/yellow]")
            for pkg in orphans:
                console.print(f"  - {pkg}")
            
            if dry_run:
                console.print("\n[cyan]Dry run mode - no packages will be removed.[/cyan]")
                console.print(f"[cyan]To remove these packages, run: arjax cleanup orphans[/cyan]")
                return
            
            # Confirm removal
            if typer.confirm("\nDo you want to remove these orphaned packages?"):
                console.print("[cyan]Removing orphaned packages...[/cyan]")
                remove_cmd = ['paru', '-Rns'] + orphans
                result = subprocess.run(remove_cmd)
                
                if result.returncode == 0:
                    console.print("[green]Orphaned packages removed successfully![/green]")
                else:
                    console.print("[red]Failed to remove orphaned packages.[/red]")
                    raise typer.Exit(1)
            else:
                console.print("[yellow]Cleanup cancelled.[/yellow]")
        
        except Exception as e:
            console.print(f"[red]Error finding orphaned packages: {str(e)}[/red]")
            raise typer.Exit(1)
    
    elif target == "cache":
        console.print("[cyan]Cleaning package cache...[/cyan]")
        
        if all_cache:
            console.print("[yellow]Warning: This will remove ALL cached packages.[/yellow]")
            if not typer.confirm("Are you sure you want to remove all cached packages?"):
                console.print("[yellow]Cache cleanup cancelled.[/yellow]")
                return
            cmd = ['paru', '-Scc']
        else:
            console.print("[yellow]This will remove uninstalled cached packages.[/yellow]")
            cmd = ['paru', '-Sc']
        
        try:
            result = subprocess.run(cmd)
            if result.returncode == 0:
                console.print("[green]Package cache cleaned successfully![/green]")
            else:
                console.print("[red]Failed to clean package cache.[/red]")
                raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error cleaning cache: {str(e)}[/red]")
            raise typer.Exit(1)
    
    else:
        console.print(f"[red]Unknown cleanup target: {target}[/red]")
        console.print("Available targets: orphans, cache")
        raise typer.Exit(1)


@app.command()
def audit(
    verbose: bool = Option(False, "--verbose", "-v", help="Show detailed information for all packages"),
    show_all: bool = Option(False, "--all", "-a", help="Show all packages, not just low-trust ones"),
    threshold: int = Option(40, "--threshold", "-t", help="Trust score threshold for warnings (default: 40)"),
    debug: bool = Option(False, "--debug", help="Enable debug logging")
) -> None:
    """
    Audit trust scores of installed AUR packages (Arch Linux only).
    
    Checks all AUR packages installed on your system and reports any with low trust scores
    based on votes, popularity, maintainer status, and whether they're out of date.
    
    Examples:
        arjax audit                    # Show warnings for low-trust packages
        arjax audit --verbose          # Show detailed info for all packages
        arjax audit --all              # Show trust scores for all AUR packages
        arjax audit --threshold 60     # Custom threshold for warnings
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)
    
    import distro
    import subprocess
    
    detected_distro = distro.id().lower()
    distro_family = DISTRO_MAP.get(detected_distro, detected_distro)
    
    if distro_family != 'arch':
        console.print("[red]Trust audit is only available on Arch-based distributions.[/red]")
        raise typer.Exit(1)
    
    # Check for paru or yay
    aur_helper = None
    for helper in ['paru', 'yay']:
        try:
            subprocess.run(['which', helper], capture_output=True, check=True)
            aur_helper = helper
            break
        except:
            continue
    
    if not aur_helper:
        console.print("[red]paru or yay is required for trust auditing.[/red]")
        console.print("Install paru: https://github.com/morganamilo/paru")
        raise typer.Exit(1)
    
    console.print(f"[cyan]Auditing installed AUR packages using {aur_helper}...[/cyan]\n")
    
    # Get list of installed AUR packages
    try:
        result = subprocess.run(
            [aur_helper, '-Qm'],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse package names from output (format: "pkgname version")
        installed_aur = []
        for line in result.stdout.split('\n'):
            if line.strip():
                parts = line.strip().split()
                if parts:
                    installed_aur.append(parts[0])
        
        if not installed_aur:
            console.print("[green]No AUR packages installed.[/green]")
            return
        
        console.print(f"[cyan]Found {len(installed_aur)} AUR package(s) to audit.[/cyan]\n")
        
    except subprocess.CalledProcessError:
        console.print("[red]Failed to get list of installed AUR packages.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)
    
    # Audit each package
    low_trust_packages = []
    medium_trust_packages = []
    high_trust_packages = []
    failed_checks = []
    
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("Auditing packages...", total=len(installed_aur))
        
        for pkg_name in installed_aur:
            progress.update(task, description=f"Checking {pkg_name}...")
            
            try:
                trust_result = assess_aur_trust(pkg_name)
                score = trust_result.get('score', 0)
                confidence = trust_result.get('confidence', 'unknown')
                reason = trust_result.get('reason', 'No details')
                
                pkg_data = {
                    'name': pkg_name,
                    'score': score,
                    'confidence': confidence,
                    'reason': reason
                }
                
                if score < threshold:
                    low_trust_packages.append(pkg_data)
                elif score < 70:
                    medium_trust_packages.append(pkg_data)
                else:
                    high_trust_packages.append(pkg_data)
                    
            except Exception as e:
                failed_checks.append({'name': pkg_name, 'error': str(e)})
            
            progress.update(task, advance=1)
    
    # Display results
    console.print()
    
    if low_trust_packages:
        console.print(f"[bold red]⚠ WARNING: {len(low_trust_packages)} low-trust package(s) found (score < {threshold}):[/bold red]\n")
        for pkg in sorted(low_trust_packages, key=lambda x: x['score']):
            console.print(f"  [red]✗[/red] [cyan]{pkg['name']}[/cyan] - Score: [red]{pkg['score']}/100[/red] ({pkg['confidence']})")
            if verbose:
                console.print(f"    [dim]{pkg['reason']}[/dim]")
        console.print()
    
    if show_all or verbose:
        if medium_trust_packages:
            console.print(f"[bold yellow]⚡ {len(medium_trust_packages)} medium-trust package(s) (score {threshold}-69):[/bold yellow]\n")
            for pkg in sorted(medium_trust_packages, key=lambda x: x['score'], reverse=True):
                console.print(f"  [yellow]◆[/yellow] [cyan]{pkg['name']}[/cyan] - Score: [yellow]{pkg['score']}/100[/yellow] ({pkg['confidence']})")
                if verbose:
                    console.print(f"    [dim]{pkg['reason']}[/dim]")
            console.print()
        
        if high_trust_packages:
            console.print(f"[bold green]✓ {len(high_trust_packages)} high-trust package(s) (score ≥ 70):[/bold green]\n")
            for pkg in sorted(high_trust_packages, key=lambda x: x['score'], reverse=True):
                console.print(f"  [green]✓[/green] [cyan]{pkg['name']}[/cyan] - Score: [green]{pkg['score']}/100[/green] ({pkg['confidence']})")
                if verbose:
                    console.print(f"    [dim]{pkg['reason']}[/dim]")
            console.print()
    
    if failed_checks:
        console.print(f"[bold red]⚠ Failed to check {len(failed_checks)} package(s):[/bold red]\n")
        for pkg in failed_checks:
            console.print(f"  [red]?[/red] [cyan]{pkg['name']}[/cyan] - Error: {pkg['error']}")
        console.print()
    
    # Summary
    if not low_trust_packages and not failed_checks:
        console.print(f"[bold green]✨ All {len(installed_aur)} AUR packages passed the trust audit![/bold green]")
    elif not low_trust_packages:
        console.print(f"[bold green]✨ No low-trust packages found![/bold green]")
    else:
        console.print(f"[bold yellow]💡 Recommendation:[/bold yellow] Review low-trust packages and consider:")
        console.print("   - Checking if they're still maintained")
        console.print("   - Looking for alternatives with higher trust scores")
        console.print("   - Removing packages you no longer need")


@app.command()
def snapshot(
    action: str = Argument(..., help="Action: create, list, restore, delete"),
    snapshot_id: Optional[str] = Argument(None, help="Snapshot ID for restore/delete operations"),
    comment: Optional[str] = Option(None, "--comment", "-c", help="Comment for snapshot creation"),
    tool: Optional[str] = Option(None, "--tool", "-t", help="Force specific tool: timeshift, snapper"),
    debug: bool = Option(False, "--debug", help="Enable debug logging")
) -> None:
    """
    Manage system snapshots for backup and restore.
    
    Supports: Timeshift, snapper
    
    Examples:
        arjax snapshot create --comment "Before major update"
        arjax snapshot list
        arjax snapshot restore 123
        arjax snapshot delete 123
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)
    
    try:
        if action == "create":
            console.print("[cyan]Creating system snapshot...[/cyan]")
            detected_tool, _ = detect_snapshot_tool()
            if detected_tool == 'none':
                console.print("[red]No snapshot tool detected![/red]")
                console.print("Install one of:")
                console.print("  - Timeshift: sudo pacman -S timeshift")
                console.print("  - snapper: sudo pacman -S snapper")
                raise typer.Exit(1)
            
            success = create_snapshot(comment=comment, tool=tool)
            if success:
                console.print(f"[green]Snapshot created successfully using {detected_tool}![/green]")
            else:
                console.print("[red]Failed to create snapshot.[/red]")
                raise typer.Exit(1)
        
        elif action == "list":
            console.print("[cyan]Listing available snapshots...[/cyan]")
            snapshots = list_snapshots(tool=tool, limit=20)
            
            if not snapshots:
                console.print("[yellow]No snapshots found.[/yellow]")
                return
            
            table = Table(title="Available Snapshots")
            table.add_column("ID", style="cyan")
            table.add_column("Date", style="green")
            table.add_column("Description", style="yellow")
            table.add_column("Tool", style="blue")
            
            for snap in snapshots:
                table.add_row(
                    snap.get('id', 'N/A'),
                    snap.get('date', 'N/A'),
                    snap.get('description', ''),
                    snap.get('tool', 'unknown')
                )
            
            console.print(table)
        
        elif action == "restore":
            if not snapshot_id:
                console.print("[red]Snapshot ID is required for restore operation.[/red]")
                console.print("Usage: arjax snapshot restore <snapshot_id>")
                raise typer.Exit(1)
            
            console.print(f"[yellow]Warning: This will restore your system to snapshot {snapshot_id}.[/yellow]")
            console.print("[yellow]A reboot will be required.[/yellow]")
            
            if not typer.confirm("Are you sure you want to restore this snapshot?"):
                console.print("[yellow]Restore cancelled.[/yellow]")
                return
            
            console.print("[cyan]Restoring snapshot...[/cyan]")
            success = restore_snapshot(snapshot_id, tool=tool)
            if success:
                console.print("[green]Snapshot restore initiated successfully![/green]")
                console.print("[yellow]Please reboot your system to complete the restore.[/yellow]")
            else:
                console.print("[red]Failed to restore snapshot.[/red]")
                raise typer.Exit(1)
        
        elif action == "delete":
            if not snapshot_id:
                console.print("[red]Snapshot ID is required for delete operation.[/red]")
                console.print("Usage: arjax snapshot delete <snapshot_id>")
                raise typer.Exit(1)
            
            if not typer.confirm(f"Are you sure you want to delete snapshot {snapshot_id}?"):
                console.print("[yellow]Delete cancelled.[/yellow]")
                return
            
            console.print("[cyan]Deleting snapshot...[/cyan]")
            success = delete_snapshot(snapshot_id, tool=tool)
            if success:
                console.print("[green]Snapshot deleted successfully![/green]")
            else:
                console.print("[red]Failed to delete snapshot.[/red]")
                raise typer.Exit(1)
        
        else:
            console.print(f"[red]Unknown action: {action}[/red]")
            console.print("Available actions: create, list, restore, delete")
            raise typer.Exit(1)
    
    except (PackageManagerNotFound, CommandGenerationError) as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {str(e)}[/red]")
        if debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


if __name__ == '__main__':
    app()
