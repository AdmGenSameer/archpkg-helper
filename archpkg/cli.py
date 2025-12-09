#!/usr/bin/python
# cli.py
"""Universal Package Helper CLI - Main module with improved consistency."""

import argparse
import sys
import os
import webbrowser
from typing import List, Tuple, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import logging

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
from archpkg.suggest import suggest_apps, list_purposes
from archpkg.cache import get_cache_manager, CacheConfig
from archpkg.github_install import install_from_github, validate_github_url
from archpkg.config_manager import get_user_config, set_config_option
from archpkg.update_manager import check_for_updates, trigger_update_check
from archpkg.download_manager import install_updates, start_background_update_service, stop_background_update_service
from archpkg.installed_apps import track_package, get_all_installed_packages, get_packages_with_updates, InstalledPackage

console = Console()
logger = get_logger(__name__)

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

        if query == name_l:
            score += 150
            logger.debug(f"Exact match bonus for '{name}': +150")
        elif query in name_l:
            score += 80
            logger.debug(f"Substring match bonus for '{name}': +80")

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

def handle_install_command(args) -> None:
    """Handle the install command for one or more packages."""
    packages = args.packages
    logger.info(f"Install command for packages: {packages}")
    
    # Check if it's a GitHub installation
    if len(packages) == 1 and (packages[0].startswith('github:') or packages[0].startswith('https://github.com/')):
        github_url = validate_github_url(packages[0])
        if github_url:
            success = install_from_github(packages[0])
            if success:
                console.print("[bold green]✓ GitHub installation completed![/bold green]")
            else:
                console.print("[bold red]✗ GitHub installation failed.[/bold red]")
                sys.exit(1)
        else:
            console.print("[red]Invalid GitHub URL format[/red]")
            sys.exit(1)
        return
    
    # Determine tracking preference
    should_track = args.track and not args.no_track
    
    # Normal package installation
    detected = detect_distro()
    
    if len(packages) == 1:
        # Single package installation
        package_name = packages[0]
        logger.info(f"Installing single package: {package_name}")
        
        # Search for the package
        results = []
        if detected == "arch":
            try:
                results.extend(search_aur(package_name))
            except Exception:
                pass
            try:
                results.extend(search_pacman(package_name))
            except Exception:
                pass
        elif detected == "debian":
            try:
                results.extend(search_apt(package_name))
            except Exception:
                pass
        elif detected == "fedora":
            try:
                results.extend(search_dnf(package_name))
            except Exception:
                pass
        
        # Universal package managers
        try:
            results.extend(search_flatpak(package_name))
        except Exception:
            pass
        try:
            results.extend(search_snap(package_name))
        except Exception:
            pass
        
        if not results:
            console.print(f"[red]No packages found for '{package_name}'[/red]")
            sys.exit(1)
        
        top_matches = get_top_matches(package_name, results, limit=5)
        if not top_matches:
            console.print(f"[red]No suitable matches found for '{package_name}'[/red]")
            sys.exit(1)
        
        # Display options
        table = Table(title="Found Packages")
        table.add_column("Index", style="cyan", no_wrap=True)
        table.add_column("Package Name", style="green")
        table.add_column("Source", style="blue")
        table.add_column("Description", style="yellow")
        
        for idx, (pkg, desc, source) in enumerate(top_matches, 1):
            table.add_row(str(idx), pkg, source, desc or "No description")
        
        console.print(table)
        
        try:
            choice = input("\nSelect a package to install [1-5 or press Enter to cancel]: ")
            if not choice.strip():
                console.print("[yellow]Installation cancelled.[/yellow]")
                return
            
            choice = int(choice)
            if not (1 <= choice <= len(top_matches)):
                console.print("[red]Invalid choice.[/red]")
                return
            
            pkg, desc, source = top_matches[choice - 1]
            command = generate_command(pkg, source)
            
            if not command:
                console.print(f"[red]Cannot generate install command for {source}[/red]")
                return
            
            console.print(f"\n[bold green]Install Command:[/bold green] {command}")
            console.print("[bold yellow]Press Enter to install, or Ctrl+C to cancel...[/bold yellow]")
            input()
            
            console.print("[blue]Running install command...[/blue]")
            exit_code = os.system(command)
            
            if exit_code == 0:
                console.print(f"[bold green]✓ Successfully installed {pkg}![/bold green]")
                if should_track:
                    track_package(pkg, source, "latest")
                    console.print("[dim]Package tracked for updates[/dim]")
            else:
                console.print(f"[red]✗ Installation failed with exit code {exit_code}[/red]")
                sys.exit(1)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Installation cancelled.[/yellow]")
            return
        except ValueError:
            console.print("[red]Invalid input. Please enter a number.[/red]")
            return
    else:
        # Batch installation
        logger.info(f"Batch installation for packages: {packages}")
        batch_install_packages(packages, should_track)

def batch_install_packages(package_names: List[str], should_track: bool = True) -> None:
    """Install multiple packages in batch mode with progress tracking."""
    logger.info(f"Starting batch installation for packages: {package_names}")
    
    if not package_names:
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
        
        if detected == "arch":
            try:
                results.extend(search_aur(pkg_name))
            except Exception:
                pass
            try:
                results.extend(search_pacman(pkg_name))
            except Exception:
                pass
        elif detected == "debian":
            try:
                results.extend(search_apt(pkg_name))
            except Exception:
                pass
        elif detected == "fedora":
            try:
                results.extend(search_dnf(pkg_name))
            except Exception:
                pass
        
        try:
            results.extend(search_flatpak(pkg_name))
        except Exception:
            pass
        try:
            results.extend(search_snap(pkg_name))
        except Exception:
            pass
        
        if not results:
            validation_errors.append(f"'{pkg_name}': No packages found")
            console.print(f"    [red]✗[/red] No packages found")
            continue
        
        top_matches = get_top_matches(pkg_name, results, limit=1)
        if not top_matches:
            validation_errors.append(f"'{pkg_name}': No suitable matches found")
            console.print(f"    [red]✗[/red] No suitable matches found")
            continue
        
        pkg, desc, source = top_matches[0]
        command = generate_command(pkg, source)
        
        if not command:
            validation_errors.append(f"'{pkg_name}': Cannot generate install command")
            console.print(f"    [red]✗[/red] Cannot generate install command")
            continue
        
        validated_packages.append((pkg_name, pkg, desc, source, command))
        console.print(f"    [green]✓[/green] Found: {pkg} ({source})")
    
    if validation_errors:
        console.print(f"\n[red]Validation failed for {len(validation_errors)} package(s):[/red]")
        for error in validation_errors:
            console.print(f"  - {error}")
        console.print("\n[yellow]Batch installation cancelled.[/yellow]")
        return
    
    console.print(f"\n[green]✓ All {len(validated_packages)} packages validated![/green]\n")
    
    # Proceed with installation
    console.print("[blue]Starting batch installation...[/blue]\n")
    
    successful_installs = []
    failed_installs = []
    
    for i, (original_name, pkg, desc, source, command) in enumerate(validated_packages, 1):
        console.print(f"[{i}/{len(validated_packages)}] Installing [bold cyan]{pkg}[/bold cyan] ({source})...")
        console.print(f"  Command: [dim]{command}[/dim]")
        
        exit_code = os.system(command)
        
        if exit_code == 0:
            console.print(f"  [green]✓[/green] Successfully installed {pkg}")
            successful_installs.append(pkg)
            if should_track:
                try:
                    track_package(pkg, source, "latest")
                except Exception as e:
                    logger.warning(f"Failed to track package {pkg}: {e}")
        else:
            console.print(f"  [red]✗[/red] Failed to install {pkg}")
            failed_installs.append((pkg, exit_code))
    
    # Summary
    console.print(f"\n[bold]Batch Installation Summary:[/bold]")
    console.print(f"Total packages: {len(validated_packages)}")
    console.print(f"[green]Successful: {len(successful_installs)}[/green]")
    if successful_installs:
        console.print(f"  - {', '.join(successful_installs)}")
    if failed_installs:
        console.print(f"[red]Failed: {len(failed_installs)}[/red]")
        for pkg, code in failed_installs:
            console.print(f"  - {pkg} (exit code: {code})")

def handle_update_command(args) -> None:
    """Handle the update command."""
    packages = args.packages if args.packages else None
    check_only = args.check_only
    
    if check_only:
        console.print("[blue]Checking for updates...[/blue]")
        result = trigger_update_check()
        
        if result["status"] == "success":
            updates_found = result.get("updates_found", 0)
            if updates_found > 0:
                console.print(f"[green]Found {updates_found} update(s) available![/green]")
                console.print("Run 'archpkg update' to install them.")
            else:
                console.print("[green]All packages are up to date![/green]")
        else:
            console.print(f"[red]Update check failed: {result.get('message', 'Unknown error')}[/red]")
    else:
        console.print("[blue]Installing updates...[/blue]")
        result = install_updates(packages)
        
        if result["status"] == "success":
            installed = result.get("installed", 0)
            failed = result.get("failed", 0)
            
            if installed > 0:
                console.print(f"[green]Successfully installed {installed} update(s)[/green]")
            
            if failed > 0:
                console.print(f"[red]Failed to install {failed} update(s)[/red]")
                for item in result.get("results", []):
                    if item.get("status") == "failed":
                        console.print(f"  - {item['package']}: {item.get('error', 'Unknown error')}")
            
            if installed == 0 and failed == 0:
                console.print("[green]No updates available[/green]")
        else:
            console.print("[red]Update installation failed[/red]")

def handle_config_command(args) -> None:
    """Handle the config command."""
    if args.list:
        config = get_user_config()
        console.print("[bold]Current Configuration:[/bold]")
        for key, value in config.__dict__.items():
            if not key.startswith('_'):
                console.print(f"  {key}: {value}")
        return
    
    if not args.key:
        console.print("[red]Error: Specify a configuration key or use --list[/red]")
        return
    
    if args.value is None:
        # Get value
        config = get_user_config()
        if hasattr(config, args.key):
            console.print(f"{args.key}: {getattr(config, args.key)}")
        else:
            console.print(f"[red]Unknown configuration key: {args.key}[/red]")
    else:
        # Set value
        try:
            value = args.value
            # Convert to appropriate type
            if value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)
            elif value.replace('.', '').isdigit():
                value = float(value)
            
            set_config_option(args.key, value)
            console.print(f"[green]Updated {args.key} = {value}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to update configuration: {e}[/red]")

def handle_list_installed_command(args) -> None:
    """Handle the list-installed command."""
    packages = get_all_installed_packages()
    
    if not packages:
        console.print("[yellow]No packages are currently being tracked for updates.[/yellow]")
        console.print("Use 'archpkg install --track <package>' to track packages.")
        return
    
    table = Table(title="Tracked Installed Packages")
    table.add_column("Package Name", style="green")
    table.add_column("Source", style="blue")
    table.add_column("Installed Version", style="cyan")
    table.add_column("Update Available", style="yellow")
    table.add_column("Last Updated", style="magenta")
    
    for pkg in packages:
        update_status = "[green]No[/green]" if not pkg.update_available else "[red]Yes[/red]"
        last_updated = pkg.install_date or "Never"
        table.add_row(
            pkg.name,
            pkg.source,
            pkg.version or "Unknown",
            update_status,
            last_updated
        )
    
    console.print(table)

def handle_service_command(args) -> None:
    """Handle the service command."""
    action = args.action
    
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

def handle_web_command(args) -> None:
    """Handle the web command."""
    try:
        from archpkg.web import app as web_app
        console.print(Panel(
            f"[bold cyan]🌐 Starting Web Interface[/bold cyan]\n\n"
            f"Host: [yellow]{args.host}[/yellow]\n"
            f"Port: [yellow]{args.port}[/yellow]\n\n"
            f"Access the interface at:\n"
            f"[cyan]http://{args.host}:{args.port}/[/cyan]\n\n"
            f"Press [bold]Ctrl+C[/bold] to stop the server.",
            title="Web Interface",
            border_style="cyan"
        ))
        web_app.run(host=args.host, port=args.port, debug=False)
    except KeyboardInterrupt:
        console.print("\n[yellow]Web server stopped.[/yellow]")
    except Exception as e:
        console.print(f"[red]Failed to start web server: {e}[/red]")

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

def main() -> None:
    """
    Main entrypoint for CLI search + install flow.
    IMPROVED: Better type annotations and error handling.
    """

    logger.info("Starting archpkg-helper CLI")
    
    # Custom help message with emojis and comprehensive information
    description = """🎯 ArchPkg Helper - Universal Package Manager for All Linux Distros

📦 What does it do?
   Searches and installs packages across multiple sources:
   ✓ Official repos (pacman, apt, dnf, zypper)
   ✓ AUR (Arch User Repository)
   ✓ Flatpak & Snap (works on any distro)"""

    epilog = """
🔍 SEARCH FOR PACKAGES
   archpkg search <package-name>
   archpkg <package-name>             (search is default)
   
   Examples:
   🔸 archpkg firefox
   🔸 archpkg visual studio code
   🔸 archpkg search telegram
   
   Flags:
   --aur              Prefer AUR packages over official repos (Arch only)
   --no-cache         Skip cache, search fresh results

💡 GET APP SUGGESTIONS BY PURPOSE
   archpkg suggest <purpose>
   
   Examples:
   🔸 archpkg suggest video editing
   🔸 archpkg suggest office
   🔸 archpkg suggest programming
   
   --list             Show all available purposes

⚙️ CACHE MANAGEMENT
   --cache-stats      Show cache statistics
   --clear-cache all  Clear all cached results
   --clear-cache aur  Clear only AUR cache

🔧 ADVANCED OPTIONS
   --debug            Show detailed debug information
   --log-info         Show logging configuration

🔄 UPGRADE ARCHPKG
   archpkg upgrade    Upgrade archpkg tool from GitHub to get latest features

🌍 Supports: Arch, Manjaro, EndeavourOS, Ubuntu, Debian, Fedora, openSUSE, and more!
"""
    
    # Handle backward compatibility: if first non-flag argument is not a known command, treat as search
    # This allows "archpkg firefox" to work the same as "archpkg search firefox"
    if len(sys.argv) > 1:
        first_arg_idx = 1
        # Skip over flags to find first positional argument
        while first_arg_idx < len(sys.argv):
            arg = sys.argv[first_arg_idx]
            if arg.startswith('-'):
                first_arg_idx += 1
                # Skip flag value if it's an option that takes a value
                if first_arg_idx < len(sys.argv) and arg in ['--clear-cache'] and not sys.argv[first_arg_idx].startswith('-'):
                    first_arg_idx += 1
            else:
                # Found a positional argument
                break
        
        # If we found a positional arg and it's not a known command, inject 'search'
        if first_arg_idx < len(sys.argv) and sys.argv[first_arg_idx] not in ['search', 'suggest', 'upgrade', '-h', '--help']:
            sys.argv.insert(first_arg_idx, 'search')
    
    parser = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False  # We'll add custom help
    )
    
    # Add custom help argument
    parser.add_argument('-h', '--help', action='store_true', help='Show this help message')
    
    # Global arguments (must come before subparsers)
    parser.add_argument('--debug', action='store_true', help='Enable debug logging to console')
    parser.add_argument('--log-info', action='store_true', help='Show logging configuration and exit')
    parser.add_argument('--no-cache', action='store_true', help='Bypass cache and perform fresh search')
    parser.add_argument('--cache-stats', action='store_true', help='Show cache statistics and exit')
    parser.add_argument('--clear-cache', choices=['all', 'aur', 'pacman', 'apt', 'dnf', 'zypper', 'flatpak', 'snap'], 
                       help='Clear cache for specified source or all sources')
    parser.add_argument('--aur', action='store_true', help='Prefer AUR packages over Pacman when both are available')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Search command (default behavior)
    search_parser = subparsers.add_parser(
        'search', 
        help='Search for packages by name',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    search_parser.add_argument('query', type=str, nargs='*', help='Name of the software to search for')
    search_parser.add_argument('--aur', action='store_true', help='Prefer AUR packages over Pacman when both are available')
    search_parser.add_argument('--no-cache', action='store_true', help='Bypass cache and perform fresh search')
    
    # Suggest command
    suggest_parser = subparsers.add_parser(
        'suggest', 
        help='Get app suggestions based on purpose',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    suggest_parser.add_argument('purpose', type=str, nargs='*', help='Purpose or use case (e.g., "video editing", "office")')
    suggest_parser.add_argument('--list', action='store_true', help='List all available purposes')
    
    # Upgrade command
    upgrade_parser = subparsers.add_parser(
        'upgrade',
        help='Upgrade archpkg tool itself from GitHub',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Install command
    install_parser = subparsers.add_parser(
        'install',
        help='Install one or more packages',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    install_parser.add_argument('packages', type=str, nargs='+', help='Package name(s) to install')
    install_parser.add_argument('--source', '-s', type=str, help='Package source (auto-detected if not specified)')
    install_parser.add_argument('--track', action='store_true', default=True, help='Track installation for updates (default: enabled)')
    install_parser.add_argument('--no-track', action='store_true', help='Do not track installation for updates')
    
    # Update command
    update_parser = subparsers.add_parser(
        'update',
        help='Check for and install package updates',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    update_parser.add_argument('packages', type=str, nargs='*', help='Specific packages to update (all if not specified)')
    update_parser.add_argument('--check-only', '-c', action='store_true', help='Only check for updates, do not install')
    
    # Config command
    config_parser = subparsers.add_parser(
        'config',
        help='Manage archpkg configuration settings',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    config_parser.add_argument('key', type=str, nargs='?', help='Configuration key to get/set')
    config_parser.add_argument('value', type=str, nargs='?', help='Value to set (if setting)')
    config_parser.add_argument('--list', '-l', action='store_true', help='List all configuration settings')
    
    # List-installed command
    list_installed_parser = subparsers.add_parser(
        'list-installed',
        help='List all installed packages being tracked for updates',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Service command
    service_parser = subparsers.add_parser(
        'service',
        help='Manage the background update service',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    service_parser.add_argument('action', type=str, choices=['start', 'stop', 'status'], help='Action to perform')
    
    # Web command
    web_parser = subparsers.add_parser(
        'web',
        help='Start the web interface',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    web_parser.add_argument('--port', '-p', type=int, default=5000, help='Port to run the web server on (default: 5000)')
    web_parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    
    # GitHub install command (as a special format of install)
    # This will be handled in the install command by checking for github: prefix
    
    # Handle help manually to show custom format
    if '--help' in sys.argv or '-h' in sys.argv:
        parser.print_help()
        sys.exit(0)
    
    args = parser.parse_args()
    
    # Initialize cache manager
    cache_config = CacheConfig(enabled=not args.no_cache)
    cache_manager = get_cache_manager(cache_config)
    
    # Enable debug mode if requested
    if args.debug:
        PackageHelperLogger.set_debug_mode(True)
        logger.info("Debug mode enabled via command line argument")
    
    # Handle cache-related commands
    if args.cache_stats:
        stats = cache_manager.get_stats()
        console.print(Panel(
            f"[bold cyan]Cache Statistics:[/bold cyan]\n"
            f"Enabled: {'[green]Yes[/green]' if stats.get('enabled') else '[red]No[/red]'}\n"
            f"Total entries: [yellow]{stats.get('total_entries', 0)}[/yellow]\n"
            f"Valid entries: [green]{stats.get('valid_entries', 0)}[/green]\n"
            f"Total accesses: [blue]{stats.get('total_accesses', 0)}[/blue]\n"
            f"Average access count: [magenta]{stats.get('avg_access_count', 0)}[/magenta]\n"
            f"Database path: [cyan]{stats.get('db_path', 'N/A')}[/cyan]\n"
            f"TTL: [yellow]{stats.get('config', {}).get('ttl_seconds', 0)}s[/yellow]\n"
            f"Max entries: [yellow]{stats.get('config', {}).get('max_entries', 0)}[/yellow]\n\n"
            f"[bold]Source breakdown:[/bold]\n" + 
            '\n'.join([f"  {source}: {count}" for source, count in stats.get('source_breakdown', {}).items()]),
            title="Cache Statistics",
            border_style="blue"
        ))
        return
    
    if args.clear_cache:
        source = None if args.clear_cache == 'all' else args.clear_cache
        cleared_count = cache_manager.clear(source)
        target = args.clear_cache if args.clear_cache != 'all' else 'all sources'
        console.print(Panel(
            f"[green]Successfully cleared {cleared_count} cache entries for {target}.[/green]",
            title="Cache Cleared",
            border_style="green"
        ))
        return
    
    # Show logging info if requested
    if args.log_info:
        from archpkg.logging_config import get_log_info
        log_info = get_log_info()
        console.print(Panel(
            f"[bold cyan]Logging Configuration:[/bold cyan]\n"
            f"File logging: {'[green]Enabled[/green]' if log_info['file_logging_enabled'] else '[red]Disabled[/red]'}\n"
            f"Log file: [cyan]{log_info['log_file'] or 'None'}[/cyan]\n"
            f"Log level: [yellow]{logging.getLevelName(log_info['log_level'])}[/yellow]\n"
            f"Active handlers: [blue]{log_info['handler_count']}[/blue]",
            title="Logging Information",
            border_style="blue"
        ))
        return
    
    # Handle different commands
    if args.command == 'suggest':
        handle_suggest_command(args)
        return
    elif args.command == 'upgrade':
        handle_upgrade_command()
        return
    elif args.command == 'install':
        handle_install_command(args)
        return
    elif args.command == 'update':
        handle_update_command(args)
        return
    elif args.command == 'config':
        handle_config_command(args)
        return
    elif args.command == 'list-installed':
        handle_list_installed_command(args)
        return
    elif args.command == 'service':
        handle_service_command(args)
        return
    elif args.command == 'web':
        handle_web_command(args)
        return
    elif args.command == 'search' or args.command is None:
        # Default to search behavior for backward compatibility
        handle_search_command(args, cache_manager)
        return
    else:
        console.print(Panel(
            "[red]Unknown command.[/red]\n\n"
            "[bold cyan]Available commands:[/bold cyan]\n"
            "- [cyan]archpkg search firefox[/cyan] - Search for packages by name\n"
            "- [cyan]archpkg install firefox[/cyan] - Install one or more packages\n"
            "- [cyan]archpkg update[/cyan] - Check for and install package updates\n"
            "- [cyan]archpkg suggest video editing[/cyan] - Get app suggestions by purpose\n"
            "- [cyan]archpkg config --list[/cyan] - View configuration settings\n"
            "- [cyan]archpkg list-installed[/cyan] - List tracked installed packages\n"
            "- [cyan]archpkg service start[/cyan] - Start background update service\n"
            "- [cyan]archpkg web[/cyan] - Start web interface\n"
            "- [cyan]archpkg upgrade[/cyan] - Upgrade archpkg tool from GitHub\n"
            "- [cyan]archpkg --help[/cyan] - Show help information",
            title="Invalid Command",
            border_style="red"
        ))
        return


def handle_suggest_command(args) -> None:
    """Handle the suggest command."""
    if args.list:
        logger.info("Listing all available purposes")
        list_purposes()
        return
    
    if not args.purpose:
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
        return
    
    purpose = ' '.join(args.purpose)
    logger.info(f"Purpose suggestion query: '{purpose}'")
    
    if not purpose.strip():
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
        return
    
    # Display suggestions
    suggest_apps(purpose)


def handle_search_command(args, cache_manager) -> None:
    """Handle the search command (original functionality)."""
    if not args.query:
        console.print(Panel(
            "[red]No search query provided.[/red]\n\n"
            "[bold cyan]Usage:[/bold cyan]\n"
            "- [cyan]archpkg search firefox[/cyan] - Search for Firefox\n"
            "- [cyan]archpkg search visual studio code[/cyan] - Search for VS Code\n"
            "- [cyan]archpkg search --aur firefox[/cyan] - Prefer AUR packages over Pacman\n"
            "- [cyan]archpkg suggest video editing[/cyan] - Get app suggestions by purpose\n"
            "- [cyan]archpkg --help[/cyan] - Show help information",
            title="Invalid Input",
            border_style="red"
        ))
        return
    
    query = ' '.join(args.query)
    logger.info(f"Search query: '{query}'")

    if not query.strip():
        logger.warning("Empty search query provided by user")
        console.print(Panel(
            "[red]Empty search query provided.[/red]\n\n"
            "[bold cyan]Usage:[/bold cyan]\n"
            "- [cyan]archpkg search firefox[/cyan] - Search for Firefox\n"
            "- [cyan]archpkg search visual studio code[/cyan] - Search for VS Code\n"
            "- [cyan]archpkg search --aur firefox[/cyan] - Prefer AUR packages over Pacman\n"
            "- [cyan]archpkg suggest video editing[/cyan] - Get app suggestions by purpose",
            title="Invalid Input",
            border_style="red"
        ))
        return

    detected = detect_distro()
    console.print(f"\nSearching for '{query}' on [cyan]{detected}[/cyan] platform...\n")

    results = []
    search_errors = []
    use_cache = not args.no_cache

    # Search based on detected distribution
    if detected == "arch":
        logger.info("Searching Arch-based repositories (AUR + pacman)")
        
        try:
            logger.debug("Starting AUR search")
            aur_results = search_aur(query, cache_manager if use_cache else None)
            results.extend(aur_results)
            logger.info(f"AUR search returned {len(aur_results)} results")
        except Exception as e:
            handle_search_errors("aur", e)
            search_errors.append("AUR")
            
        try:
            logger.debug("Starting pacman search")
            pacman_results = search_pacman(query, cache_manager if use_cache else None) 
            results.extend(pacman_results)
            logger.info(f"Pacman search returned {len(pacman_results)} results")
        except Exception as e:
            handle_search_errors("pacman", e)
            search_errors.append("Pacman")
            
    elif detected == "debian":
        logger.info("Searching Debian-based repositories (APT)")
        
        try:
            logger.debug("Starting APT search")
            apt_results = search_apt(query, cache_manager if use_cache else None)
            results.extend(apt_results)
            logger.info(f"APT search returned {len(apt_results)} results")
        except Exception as e:
            handle_search_errors("apt", e)
            search_errors.append("APT")
            
    elif detected == "fedora":
        logger.info("Searching Fedora-based repositories (DNF)")
        
        try:
            logger.debug("Starting DNF search")
            dnf_results = search_dnf(query, cache_manager if use_cache else None)
            results.extend(dnf_results)
            logger.info(f"DNF search returned {len(dnf_results)} results")
        except Exception as e:
            handle_search_errors("dnf", e)
            search_errors.append("DNF")
            
    elif detected == "suse":
        logger.info("Searching openSUSE-based repositories (Zypper)")
        
        try:
            logger.debug("Starting Zypper search")
            zypper_results = search_zypper(query, cache_manager if use_cache else None)
            results.extend(zypper_results)
            logger.info(f"Zypper search returned {len(zypper_results)} results")
        except Exception as e:
            handle_search_errors("zypper", e)
            search_errors.append("Zypper")

    # Universal package managers
    logger.info("Searching universal package managers (Flatpak + Snap)")
    
    try:
        logger.debug("Starting Flatpak search")
        flatpak_results = search_flatpak(query, cache_manager if use_cache else None)
        results.extend(flatpak_results)
        logger.info(f"Flatpak search returned {len(flatpak_results)} results")
    except Exception as e:
        handle_search_errors("flatpak", e)
        search_errors.append("Flatpak")

    try:
        logger.debug("Starting Snap search")
        snap_results = search_snap(query, cache_manager if use_cache else None)
        results.extend(snap_results)
        logger.info(f"Snap search returned {len(snap_results)} results")
    except Exception as e:
        handle_search_errors("snap", e)
        search_errors.append("Snap")

    # Show search summary
    if search_errors:
        logger.warning(f"Some search sources failed: {search_errors}")
        console.print(f"[dim]Note: Some sources unavailable: {', '.join(search_errors)}[/dim]\n")

    logger.info(f"Total search results: {len(results)}")

    if not results:
        logger.info("No results found, providing GitHub fallback")
        # Show special guidance for Brave browser on openSUSE
        if detected == "suse" and "brave" in query.lower():
            show_opensuse_brave_guidance()
        github_fallback(query)
        return

    deduplicated_results = deduplicate_packages(results, prefer_aur=args.aur)
    logger.info(f"After deduplication: {len(deduplicated_results)} unique packages")

    top_matches = get_top_matches(query, deduplicated_results, limit=5)
    if not top_matches:
        logger.warning("No close matches found after scoring")
        console.print(Panel(
            f"[yellow]Found {len(results)} packages, but none match '{query}' closely.[/yellow]\n\n"
            "[bold cyan]Suggestions:[/bold cyan]\n"
            "- Try a more specific search term\n"
            "- Check spelling of the package name\n"
            "- Use broader keywords (e.g., 'editor' instead of 'vim')\n"
            f"- Search GitHub: [cyan]https://github.com/search?q={query.replace(' ', '+')}[/cyan]",
            title="No Close Matches",
            border_style="yellow"
        ))
        return

    # Display results
    table = Table(title="Top Matching Packages")
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
                border_style="red"
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
                border_style="red"
            ))
            return
            
        selected_pkg = top_matches[choice - 1]
        pkg, desc, source = selected_pkg
        logger.info(f"User selected package: '{pkg}' from source '{source}'")
        
        command = generate_command(pkg, source)
        
        if not command:
            logger.error(f"Failed to generate install command for {source} package: {pkg}")
            console.print(Panel(
                f"[red]Cannot generate install command for {source} packages.[/red]\n\n"
                "[bold cyan]Possible solutions:[/bold cyan]\n"
                f"- Install {source.lower()} package manager first\n"
                "- Check if the package manager is in your PATH\n"
                f"- Manually install: check {source.lower()} documentation",
                title="Command Generation Failed",
                border_style="red"
            ))
            return
            
        logger.info(f"Generated install command: {command}")
        console.print(f"\n[bold green]Install Command:[/bold green] {command}")
        console.print("[bold yellow]Press Enter to install, or Ctrl+C to cancel...[/bold yellow]")
        
        try:
            input()
            logger.info("User confirmed installation, executing command")
            console.print("[blue]Running install command...[/blue]")
            exit_code = os.system(command)
            
            if exit_code != 0:
                logger.error(f"Installation failed with exit code: {exit_code}")
                console.print(Panel(
                    f"[red]Installation failed with exit code {exit_code}.[/red]\n\n"
                    "[bold cyan]Troubleshooting:[/bold cyan]\n"
                    "- Check if you have sufficient permissions\n"
                    "- Ensure package manager is properly configured\n"
                    "- Try running the command manually\n"
                    f"- Command: [cyan]{command}[/cyan]",
                    title="Installation Failed",
                    border_style="red"
                ))
            else:
                logger.info(f"Successfully installed package: {pkg}")
                console.print(f"[bold green]Successfully installed {pkg}![/bold green]")
                
        except KeyboardInterrupt:
            logger.info("Installation cancelled by user (Ctrl+C)")
            console.print("\n[yellow]Installation cancelled by user.[/yellow]")
            
    except KeyboardInterrupt:
        logger.info("Package selection cancelled by user (Ctrl+C)")
        console.print("\n[yellow]Selection cancelled by user.[/yellow]")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Application terminated by user (Ctrl+C)")
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Unexpected error in main application", e)
        console.print(Panel(
            f"[red]An unexpected error occurred.[/red]\n\n"
            f"[bold]Error details:[/bold] {str(e)}\n\n"
            "[bold cyan]What to do:[/bold cyan]\n"
            "- Try running the command again\n"
            "- Check if all dependencies are installed\n"
            "- Report this issue if it persists\n"
            "- Include this error message in your report",
            title="Unexpected Error",
            border_style="red"
        ))
        sys.exit(1) 
def app():
    main()
