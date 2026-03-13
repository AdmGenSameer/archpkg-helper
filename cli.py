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
from archpkg.command_gen import generate_command
from archpkg.logging_config import get_logger, PackageHelperLogger

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

        # Source priority
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
    """Main entrypoint for CLI search + install flow."""

    logger.info("Starting archpkg-helper CLI")
    
    parser = argparse.ArgumentParser(description="Universal Package Helper CLI")
    parser.add_argument('query', type=str, nargs='*', help='Name of the software to search for')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging to console')
    parser.add_argument('--log-info', action='store_true', help='Show logging configuration and exit')
    parser.add_argument('--flatpak', action='store_true', help='Install package from Flatpak')
    parser.add_argument('--aur', action='store_true', help='Install package from AUR')
    parser.add_argument('--pacman', action='store_true', help='Install package from Pacman')
    args = parser.parse_args()
    
    # Debug & logging
    if args.debug:
        PackageHelperLogger.set_debug_mode(True)
        logger.info("Debug mode enabled via command line argument")
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

    if not args.query:
        console.print(Panel(
            "[red]No search query provided.[/red]\n\n"
            "[bold cyan]Usage:[/bold cyan]\n"
            "- [cyan]archpkg firefox[/cyan] - Search for Firefox\n"
            "- [cyan]archpkg visual studio code[/cyan] - Search for VS Code\n"
            "- [cyan]archpkg --debug firefox[/cyan] - Search with debug output\n"
            "- [cyan]archpkg --log-info[/cyan] - Show logging configuration\n"
            "- [cyan]archpkg --help[/cyan] - Show help information",
            title="Invalid Input",
            border_style="red"
        ))
        return

    query = ' '.join(args.query)
    logger.info(f"Search query: '{query}'")
    
    explicit_source = None
    if args.flatpak:
        explicit_source = "flatpak"
    elif args.aur:
        explicit_source = "aur"
    elif args.pacman:
        explicit_source = "pacman"

    detected = detect_distro()
    
    def suggest_best_source():
        if detected == "arch":
            return "pacman"
        elif detected == "debian":
            return "apt"
        elif detected == "fedora":
            return "dnf"
        else:
            return "flatpak"

    source_to_use = explicit_source or suggest_best_source()
    console.print(f"[bold cyan]Using package source:[/bold cyan] {source_to_use}")
    logger.info(f"Package source selected: {source_to_use}")

    console.print(f"\nSearching for '{query}' on [cyan]{detected}[/cyan] platform...\n")

    results = []
    search_errors = []

    try:
        if source_to_use == "aur":
            results = search_aur(query)
        elif source_to_use == "pacman":
            results = search_pacman(query)
        elif source_to_use == "flatpak":
            results = search_flatpak(query)
        elif source_to_use == "apt":
            results = search_apt(query)
        elif source_to_use == "dnf":
            results = search_dnf(query)
        elif source_to_use == "snap":
            results = search_snap(query)
        else:
            # fallback full search
            if detected == "arch":
                try:
                    results.extend(search_aur(query))
                except Exception as e:
                    handle_search_errors("aur", e)
                try:
                    results.extend(search_pacman(query))
                except Exception as e:
                    handle_search_errors("pacman", e)
            elif detected == "debian":
                try:
                    results.extend(search_apt(query))
                except Exception as e:
                    handle_search_errors("apt", e)
            elif detected == "fedora":
                try:
                    results.extend(search_dnf(query))
                except Exception as e:
                    handle_search_errors("dnf", e)
            
            # universal managers
            try:
                results.extend(search_flatpak(query))
            except Exception as e:
                handle_search_errors("flatpak", e)
            try:
                results.extend(search_snap(query))
            except Exception as e:
                handle_search_errors("snap", e)
    except Exception as e:
        handle_search_errors(source_to_use, e)

    # Show summary
    logger.info(f"Total search results: {len(results)}")
    if not results:
        github_fallback(query)
        return

    top_matches = get_top_matches(query, results, limit=5)
    if not top_matches:
        console.print(Panel(
            f"[yellow]Found {len(results)} packages, but none match '{query}' closely.[/yellow]\n\n"
            "[bold cyan]Suggestions:[/bold cyan]\n"
            "- Try a more specific search term\n"
            "- Check spelling of the package name\n"
            "- Use broader keywords\n"
            f"- Search GitHub: [cyan]https://github.com/search?q={query.replace(' ', '+')}[/cyan]",
            title="No Close Matches",
            border_style="yellow"
        ))
        return

    table = Table(title="Top Matching Packages")
    table.add_column("Index", style="cyan", no_wrap=True)
    table.add_column("Package Name", style="green")
    table.add_column("Source", style="blue")
    table.add_column("Description", style="magenta")

    for idx, (pkg, desc, source) in enumerate(top_matches, 1):
        table.add_row(str(idx), pkg, source, desc or "No description")
    console.print(table)

    # Interactive install
    try:
        choice = input("\nSelect a package to install [1-5 or press Enter to cancel]: ")
        if not choice.strip():
            console.print("[yellow]Installation cancelled by user.[/yellow]")
            return
        choice = int(choice)
        if not (1 <= choice <= len(top_matches)):
            console.print(Panel(f"[red]Choice {choice} out of range.[/red]", title="Invalid Choice", border_style="red"))
            return
        pkg, desc, source = top_matches[choice - 1]
        command = generate_command(pkg, source)
        if not command:
            console.print(Panel(f"[red]Cannot generate install command for {source} packages.[/red]", border_style="red"))
            return
        console.print(f"\n[bold green]Install Command:[/bold green] {command}")
        input("[bold yellow]Press Enter to install or Ctrl+C to cancel...[/bold yellow]")
        exit_code = os.system(command)
        if exit_code != 0:
            console.print(Panel(f"[red]Installation failed with exit code {exit_code}.[/red]", border_style="red"))
        else:
            console.print(Panel(f"[green]{pkg} installed successfully![/green]", border_style="green"))
    except KeyboardInterrupt:
        console.print("\n[yellow]Installation cancelled by user.[/yellow]")
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Installation failed", e)
        console.print(Panel(f"[red]Unexpected error during installation: {str(e)}[/red]", border_style="red"))

if __name__ == "__main__":
    main()
