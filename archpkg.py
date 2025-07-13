# archpkg.py

import argparse
import sys
import os
from rich.console import Console
from rich.table import Table
from search_aur import search_aur
from search_pacman import search_pacman
from search_flatpak import search_flatpak
from command_gen import generate_command

console = Console()

JUNK_KEYWORDS = ["icon", "dummy", "meta", "symlink", "wrap", "material", "launcher", "unionfs"]
LOW_PRIORITY_KEYWORDS = ["extension", "plugin", "helper", "daemon", "patch", "theme"]

def is_valid_package(name, desc):
    """
    Check if a package is valid by filtering out packages with junk keywords.
    
    Args:
        name (str): The package name
        desc (str): The package description (can be None)
    
    Returns:
        bool: True if the package is valid (no junk keywords in description), False otherwise
    """
    desc = (desc or "").lower()
    return not any(bad in desc for bad in JUNK_KEYWORDS)

def get_top_matches(query, all_packages, limit=5):
    """
    Score and rank packages based on search query relevance.
    
    Uses a scoring algorithm that considers exact name matches, substring matches,
    token prefix matches, and applies boosts/penalties based on keywords.
    
    Args:
        query (str): The search query string
        all_packages (list): List of tuples (name, description, source) representing packages
        limit (int, optional): Maximum number of results to return. Defaults to 5.
    
    Returns:
        list: List of top matching packages as tuples (name, description, source),
              sorted by relevance score in descending order
    """
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

        # Exact or substring match boost
        if query == name_l:
            score += 100
        elif query in name_l:
            score += 50

        # Token prefix match
        for q in query_tokens:
            for token in name_tokens:
                if token.startswith(q):
                    score += 4
            for token in desc_tokens:
                if token.startswith(q):
                    score += 1

        # Boost official/primary packages
        boost_keywords = ["editor", "browser", "ide", "official", "gui", "android", "studio", "stable", "canary", "beta"]
        for word in boost_keywords:
            if word in name_l or word in desc_l:
                score += 3

        # Penalize less-relevant packages
        for bad in LOW_PRIORITY_KEYWORDS:
            if bad in name_l or bad in desc_l:
                score -= 5

        # Prefer binaries (often official)
        if name_l.endswith("-bin"):
            score += 10

        scored_results.append(((name, desc, source), score))

    scored_results.sort(key=lambda x: x[1], reverse=True)
    top = [pkg for pkg, score in scored_results if score > 0][:limit]

    return top

def main():
    """
    Main CLI function for the Arch Package Helper.
    
    Handles command-line argument parsing, searches for packages across multiple sources
    (AUR, pacman, flatpak), displays results in a formatted table, and allows user
    selection and installation of packages.
    
    The function performs the following steps:
    1. Parse command-line arguments for the software query
    2. Search across AUR, pacman, and flatpak repositories
    3. Score and filter results to find top matches
    4. Display results in an interactive table
    5. Handle user selection and generate installation commands
    6. Execute installation if confirmed by user
    
    Args:
        None (uses sys.argv for command-line arguments)
    
    Returns:
        None
    """
    parser = argparse.ArgumentParser(description="Arch Package Helper CLI")
    parser.add_argument('query', type=str, nargs='+', help='Name of the software to search for')
    args = parser.parse_args()
    query = ' '.join(args.query)

    console.print(f"\n:mag: [bold green]Searching for[/bold green] '{query}'...\n")

    aur_results = search_aur(query)
    pacman_results = search_pacman(query)
    flatpak_results = search_flatpak(query)

    all_results = aur_results + pacman_results + flatpak_results

    if not all_results:
        console.print("[red]❌ No packages found.[/red]")
        return

    top_matches = get_top_matches(query, all_results, limit=5)

    if not top_matches:
        console.print("[red]❌ No relevant packages found after filtering.[/red]")
        return

    table = Table(title="Top Matching Packages")
    table.add_column("Index", style="cyan", no_wrap=True)
    table.add_column("Package Name", style="green")
    table.add_column("Source", style="blue")
    table.add_column("Description", style="magenta")

    for idx, (pkg, desc, source) in enumerate(top_matches, 1):
        table.add_row(str(idx), pkg, source, desc or "No description")

    console.print(table)

    try:
        choice = input("\nSelect a package to install [1-5 or press Enter to cancel]: ")
        if not choice.strip():
            console.print("[yellow]⚠️ Cancelled by user.[/yellow]")
            return
        choice = int(choice)
        if 1 <= choice <= len(top_matches):
            selected_pkg = top_matches[choice - 1]
            pkg, desc, source = selected_pkg
            command = generate_command(pkg, source)
            console.print(f"\n[bold green]✅ Install Command:[/bold green] {command}")
            console.print("[bold yellow]Press Enter to install, or Ctrl+C to cancel...[/bold yellow]")
            input()
            console.print("[blue]⏳ Running install command...[/blue]")
            os.system(command)
        else:
            console.print("[yellow]⚠️ Invalid choice. Exiting.[/yellow]")
    except ValueError:
        console.print("[red]❌ Invalid input. Please enter a number.[/red]")
    except KeyboardInterrupt:
        console.print("\n[red]❌ Cancelled with Ctrl+C.[/red]")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[red]❌ Cancelled with Ctrl+C.[/red]")
        sys.exit(0)
