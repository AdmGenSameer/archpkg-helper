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
from archpkg.command_gen import generate_command
from archpkg.logging_config import get_logger, PackageHelperLogger
from archpkg.github_install import install_from_github, validate_github_url
from archpkg.web import app as web_app
from archpkg.config_manager import get_user_config, set_config_option
from archpkg.update_manager import check_for_updates, trigger_update_check
from archpkg.download_manager import install_updates, start_background_update_service, stop_background_update_service
from archpkg.installed_apps import add_installed_package, get_all_installed_packages, get_packages_with_updates

console = Console()
logger = get_logger(__name__)

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

def get_top_matches(query: str, all_packages: List[Tuple[str, str, str]], limit: int = 5) -> List[Tuple[str, str, str]]:
    """Get top matching packages with improved scoring algorithm."""
    logger.debug(f"Scoring {len(all_packages)} packages for query: '{query}'")
    
    if not all_packages:
        logger.debug("No packages to score")
        return []
        
    query = query.lower()
    query_tokens = set(query.split())
    scored_results = []

    for name, desc, source in all_packages:
        if not is_valid_package(name, desc):
            continue

        name_l = name.lower()
        desc_l = (desc or "").lower()
        name_tokens = set(name_l.replace("-", " ").split())
        desc_tokens = set(desc_l.split())

        score = 0

        # Exact match scoring
        if query == name_l:
            score += 150
            logger.debug(f"Exact match bonus for '{name}': +150")
        elif query in name_l:
            score += 80
            logger.debug(f"Substring match bonus for '{name}': +80")

        # Fuzzy token matching
        for q in query_tokens:
            for token in name_tokens:
                if token.startswith(q):
                    score += 4
            for token in desc_tokens:
                if token.startswith(q):
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
            "pacman": 40, "apt": 40, "dnf": 40,
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

def main() -> None:
    """
    Main entrypoint for CLI search + install flow.
    IMPROVED: Better type annotations and error handling.
    """
    # Legacy main function - now handled by Typer commands
    app()

# Typer Commands

@app.callback()
def callback():
    """
    Universal package manager helper for Linux distributions.

    Search and install packages across multiple package managers:
    pacman, AUR, apt, dnf, flatpak, snap
    """
    pass

@app.command()
def search(
    query: str = Argument(..., help="Name of the software to search for"),
    debug: bool = Option(False, "--debug", help="Enable debug logging"),
    limit: int = Option(5, "--limit", "-l", help="Maximum number of results to show")
) -> None:
    """
    Search for packages across all available package managers.
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)

    logger.info(f"Searching for: {query}")

    if not query.strip():
        console.print("[red]Error: Empty search query[/red]")
        raise typer.Exit(1)

    detected = detect_distro()
    console.print(f"\nSearching for '{query}' on [cyan]{detected}[/cyan] platform...\n")

    results = []
    search_errors = []

    # Search based on detected distribution
    if detected == "arch":
        try:
            aur_results = search_aur(query)
            results.extend(aur_results)
        except Exception as e:
            search_errors.append("AUR")

        try:
            pacman_results = search_pacman(query)
            results.extend(pacman_results)
        except Exception as e:
            search_errors.append("Pacman")

    elif detected == "debian":
        try:
            apt_results = search_apt(query)
            results.extend(apt_results)
        except Exception as e:
            search_errors.append("APT")

    elif detected == "fedora":
        try:
            dnf_results = search_dnf(query)
            results.extend(dnf_results)
        except Exception as e:
            search_errors.append("DNF")

    # Universal package managers
    try:
        flatpak_results = search_flatpak(query)
        results.extend(flatpak_results)
    except Exception:
        search_errors.append("Flatpak")

    try:
        snap_results = search_snap(query)
        results.extend(snap_results)
    except Exception:
        search_errors.append("Snap")

    if search_errors:
        console.print(f"[dim]Note: Some sources unavailable: {', '.join(search_errors)}[/dim]\n")

    if not results:
        console.print("[red]No packages found.[/red]")
        raise typer.Exit(1)

    top_matches = get_top_matches(query, results, limit=limit)
    if not top_matches:
        console.print("[yellow]No close matches found.[/yellow]")
        raise typer.Exit(1)

    # Display results
    table = Table(title="Matching Packages")
    table.add_column("Index", style="cyan", no_wrap=True)
    table.add_column("Package Name", style="green")
    table.add_column("Source", style="blue")
    table.add_column("Description", style="magenta")

    for idx, (pkg, desc, source) in enumerate(top_matches, 1):
        table.add_row(str(idx), pkg, source, desc or "No description")

    console.print(table)

@app.command()
def install(
    packages: List[str] = Argument(..., help="Name(s) of the package(s) to install"),
    source: Optional[str] = Option(None, "--source", "-s", help="Package source (auto-detected if not specified)"),
    debug: bool = Option(False, "--debug", help="Enable debug logging"),
    track: bool = Option(True, "--track/--no-track", help="Track this installation for updates")
) -> None:
    """
    Install one or more packages and optionally track them for updates.

    Examples:
        archpkg install firefox
        archpkg install firefox vscode git
        archpkg install firefox --source aur
    """
    if debug:
        PackageHelperLogger.set_debug_mode(True)

    if len(packages) == 1:
        # Single package installation (interactive mode)
        package_name = packages[0]
        logger.info(f"Installing single package: {package_name}")

        # Generate install command
        command = generate_command(package_name, source)

        if not command:
            console.print(f"[red]Cannot generate install command for {package_name}[/red]")
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
                console.print(f"[bold green]Successfully installed {package_name}![/bold green]")

                # Track the installation if requested
                if track:
                    detected = detect_distro()
                    package_source = source or detected
                    add_installed_package(package_name, package_source, "latest")
                    console.print(f"[dim]Package tracked for updates[/dim]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Installation cancelled.[/yellow]")
            raise typer.Exit(1)
    else:
        # Multiple packages - use batch installation
        logger.info(f"Installing multiple packages: {packages}")

        # For batch installation, we don't support custom source specification
        # as it would be complex to handle different sources for different packages
        if source:
            console.print("[yellow]Warning: --source flag ignored for batch installation. Using auto-detection.[/yellow]")

        # Use the existing batch installation function
        batch_install_packages(packages)

        # Track all successfully installed packages if requested
        if track:
            detected = detect_distro()
            for package_name in packages:
                try:
                    add_installed_package(package_name, detected, "latest")
                except Exception as e:
                    logger.warning(f"Failed to track package {package_name}: {e}")
            console.print(f"[dim]Successfully installed packages tracked for updates[/dim]")

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

    table = Table(title="Tracked Installed Packages")
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
