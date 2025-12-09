#!/usr/bin/python
# cli.py
"""Universal Package Helper CLI - Main module with improved consistency."""

import sys
import os
import webbrowser
from typing import List, Tuple, Optional
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
from archpkg.config import JUNK_KEYWORDS, LOW_PRIORITY_KEYWORDS, BOOST_KEYWORDS, DISTRO_MAP
from archpkg.exceptions import PackageManagerNotFound, NetworkError, TimeoutError
from archpkg.search_aur import search_aur
from archpkg.search_pacman import search_pacman
from archpkg.search_flatpak import search_flatpak
from archpkg.search_snap import search_snap
from archpkg.search_apt import search_apt
from archpkg.search_dnf import search_dnf
from archpkg.search_zypper import search_zypper
from archpkg.command_gen import generate_command
from archpkg.logging_config import get_logger, PackageHelperLogger
from archpkg.github_install import install_from_github, validate_github_url
from archpkg.web import app as web_app
from archpkg.config_manager import get_user_config, set_config_option
from archpkg.update_manager import check_for_updates, trigger_update_check
from archpkg.download_manager import install_updates, start_background_update_service, stop_background_update_service
from archpkg.installed_apps import add_installed_package, get_all_installed_packages, get_packages_with_updates
from archpkg.suggest import suggest_apps, list_purposes
from archpkg.cache import get_cache_manager, CacheConfig

console = Console()
logger = get_logger(__name__)

# Constants
PANEL_PADDING = 4  # Padding for panel borders in terminal width calculations
MIN_PREFIX_LENGTH = 3  # Minimum length for meaningful prefix matching in scoring

def normalize_query(query: str) -> List[str]:
    """Generate query variations for better matching.
    
    Args:
        query: Original search query
        
    Returns:
        List of query variations to try
    """
    variations = [query]
    
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
    name="archpkg",
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
        "- Or reinstall the package: [cyan]pip install --upgrade archpkg-helper[/cyan]\n"
        "- If using pipx: [cyan]pipx reinstall archpkg-helper[/cyan]",
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
    
def is_valid_package(name: str, desc: Optional[str]) -> bool:
    """Check if a package is valid (not junk/meta package)."""
    desc = (desc or "").lower()
    is_junk = any(bad in desc for bad in JUNK_KEYWORDS)
    
    if is_junk:
        logger.debug(f"Package '{name}' filtered out as junk package")
    
    return not is_junk

def deduplicate_packages(packages: List[Tuple[str, str, str]], prefer_aur: bool = False) -> List[Tuple[str, str, str]]:
    """Remove duplicate packages, preferring Pacman over AUR by default.
    
    Args:
        packages: List of (name, description, source) tuples
        prefer_aur: If True, prefer AUR packages over Pacman when duplicates exist
        
    Returns:
        List[Tuple[str, str, str]]: Deduplicated packages with preferred sources
    """
    logger.debug(f"Deduplicating {len(packages)} packages, prefer_aur={prefer_aur}")
    
    
    package_groups = {}
    for name, desc, source in packages:
        if name not in package_groups:
            package_groups[name] = []
        package_groups[name].append((name, desc, source))
    
    deduplicated = []
    for name, group in package_groups.items():
        if len(group) == 1:
            deduplicated.append(group[0])
        else:
            sources = [source for _, _, source in group]
            
            if prefer_aur and 'aur' in sources:
                preferred = next((pkg for pkg in group if pkg[2] == 'aur'), group[0])
                logger.debug(f"Package '{name}' available in multiple sources, preferring AUR")
            elif 'pacman' in sources:
                preferred = next((pkg for pkg in group if pkg[2] == 'pacman'), group[0])
                logger.debug(f"Package '{name}' available in multiple sources, preferring Pacman")
            else:
                preferred = group[0]
                logger.debug(f"Package '{name}' available in multiple sources, using first: {preferred[2]}")
            
            deduplicated.append(preferred)
    
    logger.info(f"Deduplicated {len(packages)} packages to {len(deduplicated)} unique packages")
    return deduplicated

def get_top_matches(query: str, all_packages: List[Tuple[str, str, str]], limit: int = 5) -> List[Tuple[str, str, str]]:
    """Get top matching packages with improved scoring algorithm for multi-word queries."""
    logger.debug(f"Scoring {len(all_packages)} packages for query: '{query}'")
    
    if not all_packages:
        logger.debug("No packages to score")
        return []
        
    query = query.lower()
    query_tokens = set(query.split())
    # Create hyphenated and concatenated versions for better matching
    query_hyphenated = query.replace(" ", "-")
    query_concat = query.replace(" ", "")
    scored_results = []

    for name, desc, source in all_packages:
        if not is_valid_package(name, desc):
            continue

        name_l = name.lower()
        desc_l = (desc or "").lower()
        name_tokens = set(name_l.replace("-", " ").split())
        desc_tokens = set(desc_l.split())

        score = 0

        # IMPROVED: Better handling of multi-word queries
        # Exact match (highest priority)
        if query == name_l:
            score += 150
            logger.debug(f"Exact match bonus for '{name}': +150")
        # Check hyphenated version: "jellyfin media player" matches "jellyfin-media-player"
        elif query_hyphenated == name_l:
            score += 140
            logger.debug(f"Hyphenated match bonus for '{name}': +140")
        # Check concatenated version: "jellyfin media player" matches "jellyfinmediaplayer"
        elif query_concat == name_l:
            score += 130
            logger.debug(f"Concatenated match bonus for '{name}': +130")
        # Substring match
        elif query in name_l:
            score += 80
            logger.debug(f"Substring match bonus for '{name}': +80")
        # Check if hyphenated query is in name
        elif query_hyphenated in name_l:
            score += 70
            logger.debug(f"Hyphenated substring match bonus for '{name}': +70")

        # IMPROVED: Token matching with better weight for multi-word queries
        matched_tokens = query_tokens & name_tokens
        if matched_tokens:
            # If most query tokens match, give significant bonus
            match_ratio = len(matched_tokens) / len(query_tokens)
            if match_ratio >= 0.8:  # 80% or more tokens match
                score += 60
                logger.debug(f"High token match ratio for '{name}': +60")
            elif match_ratio >= 0.5:  # 50% or more tokens match
                score += 30
                logger.debug(f"Medium token match ratio for '{name}': +30")
            else:
                score += len(matched_tokens) * 5
                logger.debug(f"Token matches for '{name}': +{len(matched_tokens) * 5}")

        # Prefix matching for query tokens
        for q in query_tokens:
            for token in name_tokens:
                if token.startswith(q) and len(q) >= MIN_PREFIX_LENGTH:  # Only count meaningful prefixes
                    score += 4
            for token in desc_tokens:
                if token.startswith(q) and len(q) >= MIN_PREFIX_LENGTH:
                    score += 1

        # Boost keywords
        for word in BOOST_KEYWORDS:
            if word in name_l or word in desc_l:
                score += 3

        # Penalize low priority
        for bad in LOW_PRIORITY_KEYWORDS:
            if bad in name_l or bad in desc_l:
                score -= 10

        if name_l.endswith("-bin"):
            score += 5

        # Source priority (IMPROVED: consistent scoring)
        source_priority = {
            "pacman": 40, "apt": 40, "dnf": 40, "zypper": 40,
            "aur": 20,
            "flatpak": 10,
            "snap": 5
        }
        score += source_priority.get(source.lower(), 0)

        scored_results.append(((name, desc, source), score))

    scored_results.sort(key=lambda x: x[1], reverse=True)
    top = [pkg for pkg, score in scored_results if score > 0][:limit]
    
    logger.info(f"Found {len(top)} top matches from {len(all_packages)} total packages")
    for i, (pkg_info, score) in enumerate(scored_results[:limit]):
        logger.debug(f"Top match #{i+1}: {pkg_info[0]} (score: {score})")
    
    return top

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
        "[dim]Note: After adding the repository, you can search for Brave again with archpkg.[/dim]",
        title="🦁 Brave Browser Installation",
        border_style="blue"
    ))

def github_fallback(query: str) -> None:
    """Provide GitHub search fallback with clear messaging."""
    logger.info(f"No packages found for query '{query}', providing GitHub fallback")
    
    console.print(Panel(
        f"[yellow]No packages found for '{query}' in available repositories.[/yellow]\n\n"
        "[bold cyan]Alternative options:[/bold cyan]\n"
        "- Search GitHub for source code or releases\n"
        "- Check if the package name is spelled correctly\n" 
        "- Try searching with different keywords\n"
        "- Look for similar packages with: [cyan]archpkg <similar-name>[/cyan]",
        title="No Packages Found",
        border_style="yellow"
    ))
    
    try:
        url = f"https://github.com/search?q={query.replace(' ', '+')}&type=repositories"
        logger.info(f"Opening GitHub search URL: {url}")
        console.print(f"[blue]Opening GitHub search:[/blue] {url}")
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
    """Handle the upgrade command to update archpkg from GitHub."""
    logger.info("Starting archpkg upgrade process")
    
    console.print(Panel(
        "[bold cyan]🔄 Upgrading archpkg from GitHub...[/bold cyan]\n\n"
        "[dim]This will pull the latest code and reinstall archpkg.[/dim]",
        title="Archpkg Upgrade",
        border_style="cyan"
    ))
    
    # Check if pipx is available
    import shutil
    if not shutil.which("pipx"):
        logger.error("pipx command not found")
        console.print(Panel(
            "[red]❌ pipx is not installed or not in PATH.[/red]\n\n"
            "[bold cyan]To install pipx:[/bold cyan]\n"
            "- Arch Linux: [cyan]sudo pacman -S pipx && pipx ensurepath[/cyan]\n"
            "- Debian/Ubuntu: [cyan]sudo apt install pipx && pipx ensurepath[/cyan]\n"
            "- Fedora: [cyan]sudo dnf install pipx && pipx ensurepath[/cyan]\n\n"
            "[bold yellow]Note:[/bold yellow] After installing pipx, restart your terminal.",
            title="pipx Not Found",
            border_style="red"
        ))
        return
    
    console.print("[blue]📥 Pulling latest changes from repository...[/blue]")
    
    # Run the upgrade command
    upgrade_cmd = "pipx install --force git+https://github.com/AdmGenSameer/archpkg-helper.git"
    logger.info(f"Executing upgrade command: {upgrade_cmd}")
    
    try:
        console.print("[blue]📦 Reinstalling with latest code...[/blue]\n")
        exit_code = os.system(upgrade_cmd)
        
        if exit_code != 0:
            logger.error(f"Upgrade failed with exit code: {exit_code}")
            console.print(Panel(
                f"[red]❌ Upgrade failed with exit code {exit_code}.[/red]\n\n"
                "[bold cyan]Troubleshooting:[/bold cyan]\n"
                "- Check your internet connection\n"
                "- Ensure you can access GitHub (https://github.com)\n"
                "- Try again in a few moments\n"
                "- Check if pipx is working: [cyan]pipx list[/cyan]\n\n"
                "[bold yellow]Manual upgrade:[/bold yellow]\n"
                f"Run: [cyan]{upgrade_cmd}[/cyan]",
                title="Upgrade Failed",
                border_style="red"
            ))
        else:
            logger.info("Successfully upgraded archpkg")
            console.print(Panel(
                "[bold green]✅ Successfully upgraded archpkg! You now have the latest features![/bold green]\n\n"
                "[bold cyan]💡 Tip:[/bold cyan] Run [cyan]archpkg --help[/cyan] to see what's new!",
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
            "- Ensure pipx is properly installed\n"
            "- Try running manually: [cyan]pipx install --force git+https://github.com/AdmGenSameer/archpkg-helper.git[/cyan]\n"
            "- Report this issue if it persists",
            title="Upgrade Error",
            border_style="red"
        ))

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
   [cyan]archpkg search <package-name>[/cyan]
   [cyan]archpkg <package-name>[/cyan]             [dim](search is default)[/dim]
   
   Examples:
   [green]🔸 archpkg firefox[/green]
   [green]🔸 archpkg visual studio code[/green]
   [green]🔸 archpkg search telegram[/green]
   
   Options:
   [cyan]--aur[/cyan]              Prefer AUR packages over official repos
   [cyan]--no-cache[/cyan]         Skip cache, search fresh results
   [cyan]--limit, -l[/cyan]        Maximum results to show (default: 5)

[bold yellow]💡 GET APP SUGGESTIONS BY PURPOSE[/bold yellow]
   [cyan]archpkg suggest <purpose>[/cyan]
   
   Examples:
   [green]🔸 archpkg suggest video editing[/green]
   [green]🔸 archpkg suggest coding[/green]
   [green]🔸 archpkg suggest gaming[/green]
   
   [cyan]--list[/cyan]             Show all available purposes

[bold yellow]🌐 WEB INTERFACE[/bold yellow]
   [cyan]archpkg web[/cyan]                        Launch web UI
   [cyan]archpkg web --port 8080[/cyan]            Use custom port

[bold yellow]📦 PACKAGE TRACKING & UPDATES[/bold yellow]
   [cyan]archpkg list-installed[/cyan]             List tracked packages
   [cyan]archpkg update[/cyan]                     Install updates
   [cyan]archpkg update --check-only[/cyan]        Only check for updates

[bold yellow]⚙️  CONFIGURATION[/bold yellow]
   [cyan]archpkg config --list[/cyan]              Show all settings
   [cyan]archpkg config <key> <value>[/cyan]       Set a config value

[bold yellow]🔄 BACKGROUND SERVICE[/bold yellow]
   [cyan]archpkg service start|stop|status[/cyan]

[bold yellow]🔄 UPGRADE ARCHPKG[/bold yellow]
   [cyan]archpkg upgrade[/cyan]                    Get latest version from GitHub

[bold yellow]🌍 SUPPORTED DISTRIBUTIONS[/bold yellow]
   [green]Arch, Manjaro, EndeavourOS, Ubuntu, Debian, Fedora,
   openSUSE, + any distro with Flatpak/Snap support[/green]

[bold yellow]📚 MORE INFORMATION[/bold yellow]
   Run [cyan]archpkg <command> --help[/cyan] for detailed help on any command
   Visit: [blue]https://github.com/AdmGenSameer/archpkg-helper[/blue]
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
    known_commands = ['search', 'suggest', 'upgrade', 'web', 'update', 'config', 'list-installed', 'service']
    
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
    🎯 ArchPkg Helper - Universal Package Manager for All Linux Distros

    📦 What does it do?
       Searches and installs packages across multiple sources:
       ✓ Official repos (pacman, apt, dnf, zypper)
       ✓ AUR (Arch User Repository)
       ✓ Flatpak & Snap (works on any distro)

    🔍 SEARCH FOR PACKAGES
       archpkg search <package-name>
       archpkg <package-name>             (search is default)
       
       Examples:
       🔸 archpkg firefox
       🔸 archpkg visual studio code
       🔸 archpkg search telegram
       
       Options:
       --aur              Prefer AUR packages over official repos
       --no-cache         Skip cache, search fresh results
       --limit, -l        Maximum results to show (default: 5)

    💡 GET APP SUGGESTIONS BY PURPOSE
       archpkg suggest <purpose>
       
       Examples:
       🔸 archpkg suggest video editing
       🔸 archpkg suggest coding
       🔸 archpkg suggest gaming
       
       --list             Show all available purposes

    🌐 WEB INTERFACE
       archpkg web                        Launch web UI
       archpkg web --port 8080            Use custom port

    📦 PACKAGE TRACKING & UPDATES
       archpkg list-installed             List tracked packages
       archpkg update                     Install updates
       archpkg update --check-only        Only check for updates

    ⚙️ CONFIGURATION
       archpkg config --list              Show all settings
       archpkg config <key> <value>       Set a config value

    🔄 BACKGROUND SERVICE
       archpkg service start|stop|status

    🔄 UPGRADE ARCHPKG
       archpkg upgrade                    Get latest version from GitHub

    🌍 SUPPORTED DISTRIBUTIONS
       Arch, Manjaro, EndeavourOS, Ubuntu, Debian, Fedora,
       openSUSE, + any distro with Flatpak/Snap support
    """
    pass

@app.command()
def search(
    query: List[str] = Argument(..., help="Name of the software to search for"),
    debug: bool = Option(False, "--debug", help="Enable debug logging"),
    limit: int = Option(5, "--limit", "-l", help="Maximum number of results to show"),
    aur: bool = Option(False, "--aur", help="Prefer AUR packages over Pacman"),
    no_cache: bool = Option(False, "--no-cache", help="Bypass cache and perform fresh search")
) -> None:
    """
    Search for packages across all available package managers.
    
    Supports multi-word queries: archpkg search visual studio code
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)

    # Join multi-word queries
    query_str = ' '.join(query)
    logger.info(f"Searching for: {query_str}")

    if not query_str.strip():
        console.print("[red]Error: Empty search query[/red]")
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

    results = []
    search_errors = []
    use_cache = not no_cache

    # Search with all query variations
    for query_variant in query_variations:
        logger.debug(f"Searching with query variant: '{query_variant}'")
        
        # Search based on detected distribution
        if detected == "arch":
            try:
                logger.debug("Starting AUR search")
                aur_results = search_aur(query_variant, cache_manager if use_cache else None)
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

    if search_errors:
        console.print(f"[dim]Note: Some sources unavailable: {', '.join(search_errors)}[/dim]\n")

    if not results:
        logger.info("No results found, providing GitHub fallback")
        # Show special guidance for Brave browser on openSUSE
        if detected == "suse" and "brave" in query_str.lower():
            show_opensuse_brave_guidance()
        github_fallback(query_str)
        return

    deduplicated_results = deduplicate_packages(results, prefer_aur=aur)
    logger.info(f"After deduplication: {len(deduplicated_results)} unique packages")

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
    table.add_column("Description", style="magenta")

    for idx, (pkg, desc, source) in enumerate(top_matches, 1):
        table.add_row(str(idx), pkg, source, desc or "No description")

    console.print(table)
    
    try:
        logger.info("Starting interactive installation flow")
        choice = input("\nSelect a package to install [1-5 or press Enter to cancel]: ")
        
        if not choice.strip():
            logger.info("Installation cancelled by user (empty input)")
            console.print("[yellow]Installation cancelled by user.[/yellow]")
            return
            
        try:
            choice = int(choice)
            logger.debug(f"User selected choice: {choice}")
        except ValueError:
            logger.warning(f"Invalid user input: '{choice}'")
            console.print(Panel(
                "[red]Invalid input. Please enter a number.[/red]\n\n"
                "[bold cyan]Valid options:[/bold cyan]\n"
                "- Enter 1-5 to select a package\n"
                "- Press Enter to cancel\n"
                "- Use Ctrl+C to exit",
                title="Invalid Input",
                border_style="red",
                width=min(console_width - PANEL_PADDING, 100)
            ))
            return
            
        if not (1 <= choice <= len(top_matches)):
            logger.warning(f"Choice {choice} out of range (1-{len(top_matches)})")
            console.print(Panel(
                f"[red]Choice {choice} is out of range.[/red]\n\n"
                f"[bold cyan]Available options:[/bold cyan] 1-{len(top_matches)}\n"
                "- Try again with a valid number\n"
                "- Press Enter to cancel",
                title="Invalid Choice",
                border_style="red",
                width=min(console_width - PANEL_PADDING, 100)
            ))
            return
            
        selected_pkg = top_matches[choice - 1]
        pkg, desc, source = selected_pkg
        logger.info(f"User selected package: '{pkg}' from source '{source}'")
        
        command = generate_command(pkg, source)
        
        if not command:
            console.print(f"[red]Cannot generate install command for {pkg}[/red]")
            raise typer.Exit(1)

        console.print(f"[bold green]Install Command:[/bold green] {command}")
        console.print("[bold yellow]Press Enter to install, or Ctrl+C to cancel...[/bold yellow]")

        try:
            input()
            console.print("[blue]Running install command...[/blue]")
            exit_code = os.system(command)

            if exit_code != 0:
                console.print(f"[red]Installation failed with exit code {exit_code}[/red]")
                raise typer.Exit(1)
            else:
                console.print(f"[bold green]Successfully installed {pkg}![/bold green]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Installation cancelled.[/yellow]")
            raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Installation cancelled.[/yellow]")
        raise typer.Exit(1)


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
            "- [cyan]archpkg suggest video editing[/cyan] - Get video editing apps\n"
            "- [cyan]archpkg suggest office[/cyan] - Get office applications\n"
            "- [cyan]archpkg suggest --list[/cyan] - List all available purposes\n"
            "- [cyan]archpkg suggest --help[/cyan] - Show help information",
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
            "- [cyan]archpkg suggest video editing[/cyan] - Get video editing apps\n"
            "- [cyan]archpkg suggest office[/cyan] - Get office applications\n"
            "- [cyan]archpkg suggest --list[/cyan] - List all available purposes",
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
    Upgrade archpkg tool itself from GitHub.
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)
    
    logger.info("Starting archpkg upgrade from GitHub")
    handle_upgrade_command()


@app.command()
def web(
    port: int = Option(5000, "--port", "-p", help="Port to run the web server on"),
    host: str = Option("127.0.0.1", "--host", help="Host to bind the web server to"),
    debug_mode: bool = Option(False, "--debug", help="Enable debug mode")
) -> None:
    """
    Launch the web interface for package management.
    """
    console.print(f"[blue]Starting web interface at http://{host}:{port}[/blue]")
    console.print("[yellow]Press Ctrl+C to stop the server[/yellow]")
    try:
        web_app.run(host=host, port=port, debug=debug_mode)
    except KeyboardInterrupt:
        console.print("\n[yellow]Web server stopped.[/yellow]")


@app.command()
def update(
    packages: Optional[List[str]] = Argument(None, help="Specific packages to update (all if not specified)"),
    check_only: bool = Option(False, "--check-only", "-c", help="Only check for updates, don't install"),
    debug: bool = Option(False, "--debug", help="Enable debug logging")
) -> None:
    """
    Check for and install package updates.
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)

    if check_only:
        console.print("[blue]Checking for updates...[/blue]")
        result = trigger_update_check()

        if result["status"] == "success":
            checked = result["checked"]
            updates_found = result["updates_found"]

            if updates_found > 0:
                console.print(f"[green]Found {updates_found} update(s) available![/green]")
                console.print("Run 'archpkg update' to install them.")
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
    Manage archpkg configuration settings.
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
            if value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)
            elif value.replace('.', '').isdigit():
                value = float(value)

            set_config_option(key, value)
            console.print(f"[green]Updated {key} = {value}[/green]")
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
        console.print("Use 'archpkg install --track' to track packages for updates.")
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
        last_updated = pkg.last_updated or "Never"
        table.add_row(
            pkg.name,
            pkg.source,
            pkg.installed_version or "Unknown",
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
            console.print(f"Auto-install: {'Enabled' if config.auto_install_updates else 'Disabled'}")
        else:
            console.print("[yellow]Background update service is disabled[/yellow]")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available actions: start, stop, status")
        raise typer.Exit(1)

if __name__ == '__main__':
    app()
