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
from archpkg.suggest import suggest_apps, list_purposes
 master
from archpkg.completion import complete_packages

from archpkg.cache import get_cache_manager, CacheConfig
 main

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

def main() -> None:
    """
    Main entrypoint for CLI search + install flow.
    IMPROVED: Better type annotations and error handling.
    """

    logger.info("Starting archpkg-helper CLI")
    
    parser = argparse.ArgumentParser(description="Universal Package Helper CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Search command (default behavior)
    search_parser = subparsers.add_parser('search', help='Search for packages by name')
    search_parser.add_argument('query', type=str, nargs='*', help='Name of the software to search for')
    search_parser.add_argument('--aur', action='store_true', help='Prefer AUR packages over Pacman when both are available')
    search_parser.add_argument('--no-cache', action='store_true', help='Bypass cache and perform fresh search')
    
    # Suggest command
    suggest_parser = subparsers.add_parser('suggest', help='Get app suggestions based on purpose')
    suggest_parser.add_argument('purpose', type=str, nargs='*', help='Purpose or use case (e.g., "video editing", "office")')
    suggest_parser.add_argument('--list', action='store_true', help='List all available purposes')
    
    # Completion command (as a subcommand)
    completion_parser = subparsers.add_parser('complete', help='Generate completion suggestions (for shell integration)')
    completion_parser.add_argument('query', type=str, nargs='*', help='Query to complete')
    completion_parser.add_argument('--context', type=str, default='install', help='Completion context (install, remove, etc.)')
    completion_parser.add_argument('--limit', type=int, default=10, help='Maximum number of suggestions')
    
    # Global arguments
    parser.add_argument('--debug', action='store_true', help='Enable debug logging to console')
    parser.add_argument('--log-info', action='store_true', help='Show logging configuration and exit')
    parser.add_argument('--no-cache', action='store_true', help='Bypass cache and perform fresh search')
    parser.add_argument('--cache-stats', action='store_true', help='Show cache statistics and exit')
    parser.add_argument('--clear-cache', choices=['all', 'aur', 'pacman', 'apt', 'dnf', 'flatpak', 'snap'], 
                       help='Clear cache for specified source or all sources')
    
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
    elif args.command == 'complete':
        handle_completion_command(args)
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
            "- [cyan]archpkg suggest video editing[/cyan] - Get app suggestions by purpose\n"
            "- [cyan]archpkg suggest --list[/cyan] - List all available purposes\n"
            "- [cyan]archpkg --help[/cyan] - Show help information",
            title="Invalid Command",
            border_style="red"
        ))
        return


def handle_completion_command(args) -> None:
    """Handle the completion command for shell integration."""
    if not args.query:
        # Return empty completion if no query provided
        return
    
    query = ' '.join(args.query)
    logger.debug(f"Completion query: '{query}' with context: '{args.context}'")
    
    if not query.strip():
        return
    
    # Get completions and output them
    try:
        completions = complete_packages(query, args.context, args.limit)
        if completions:
            print(completions)
    except Exception as e:
        logger.error(f"Completion failed: {e}")
        # Don't output anything on error to avoid breaking shell completion


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
