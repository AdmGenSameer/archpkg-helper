#!/usr/bin/python
# archpkg.py

import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import webbrowser
from rich.console import Console
from rich.table import Table
import typer
from search_aur import search_aur
from search_pacman import search_pacman
from search_flatpak import search_flatpak
from search_snap import search_snap
from search_apt import search_apt
from search_dnf import search_dnf
from command_gen import generate_command

console = Console()
app = typer.Typer(help="Universal Package Helper CLI")

try:
    import distro
except ModuleNotFoundError:
    console.print("[red]❌ The 'distro' module is not installed. Please install it using 'pip install distro'.[/red]")
    sys.exit(1)

JUNK_KEYWORDS = ["icon", "dummy", "meta", "symlink", "wrap", "material", "launcher", "unionfs"]
LOW_PRIORITY_KEYWORDS = ["extension", "plugin", "helper", "daemon", "patch", "theme"]

SUPPORTED_PLATFORMS = ["arch", "debian", "ubuntu", "linuxmint", "fedora", "manjaro"]

def detect_distro():
    try:
        dist = distro.id().lower().strip()

        DISTRO_MAP = {
            "arch": "arch",
            "manjaro": "arch",
            "endeavouros": "arch",
            "arco": "arch",
            "garuda": "arch",
            "ubuntu": "debian",
            "debian": "debian",
            "linuxmint": "debian",
            "pop": "debian",
            "elementary": "debian",
            "fedora": "fedora",
            "rhel": "fedora",
            "centos": "fedora",
            "rocky": "fedora",
            "alma": "fedora"
        }

        return DISTRO_MAP.get(dist, "unknown")
    except Exception as e:
        console.print(f"[red]⚠️ Failed to detect distro: {e}[/red]")
        return "unknown"


def is_valid_package(name, desc):
    desc = (desc or "").lower()
    return not any(bad in desc for bad in JUNK_KEYWORDS)

def get_top_matches(query, all_packages, limit=5):
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

        # 🎯 Exact match
        if query == name_l:
            score += 150
        elif query in name_l:
            score += 80

        # 🔍 Fuzzy token matching
        for q in query_tokens:
            for token in name_tokens:
                if token.startswith(q):
                    score += 4
            for token in desc_tokens:
                if token.startswith(q):
                    score += 1

        # 💡 Boost keywords
        boost_keywords = ["editor", "browser", "ide", "official", "gui", "android", "studio", "stable", "canary", "beta"]
        for word in boost_keywords:
            if word in name_l or word in desc_l:
                score += 3

        # 🛑 Penalize junk
        for bad in LOW_PRIORITY_KEYWORDS:
            if bad in name_l or bad in desc_l:
                score -= 10

        if name_l.endswith("-bin"):
            score += 5  # lower than before

        # 📦 Source priority
        if source == "pacman" or source == "apt" or source == "dnf":
            score += 40  # official distro repo
        elif source == "aur":
            score += 20
        elif source == "flatpak":
            score += 10
        elif source == "snap":
            score += 5

        scored_results.append(((name, desc, source), score))

    scored_results.sort(key=lambda x: x[1], reverse=True)
    top = [pkg for pkg, score in scored_results if score > 0][:limit]
    return top

def github_fallback(query):
    console.print(f"[yellow]\n🔎 No packages found. Searching GitHub for '{query}'...[/yellow]")
    url = f"https://github.com/search?q={query.replace(' ', '+')}&type=repositories"
    console.print(f"[blue]🌐 Opening:[/blue] {url}")
    webbrowser.open(url)

def main():
    parser = argparse.ArgumentParser(description="Universal Package Helper CLI")
    parser.add_argument('query', type=str, nargs='+', help='Name of the software to search for')
    args = parser.parse_args()
    query = ' '.join(args.query)

    detected = detect_distro()
    console.print(f"\n:mag: [bold green]Searching for[/bold green] '{query}' on [cyan]{detected}[/cyan] platform...\n")

    results = []
    if detected == "arch":
        results += search_aur(query)
        results += search_pacman(query)
    elif detected == "debian":
        results += search_apt(query)
    elif detected == "fedora":
        results += search_dnf(query)

    results += search_flatpak(query)
    results += search_snap(query)

    if not results:
        github_fallback(query)
        return

    top_matches = get_top_matches(query, results, limit=5)
    if not top_matches:
        github_fallback(query)
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
    except Exception as e:
        console.print(f"[red]❌ An error occurred: {e}[/red]")
        sys.exit(1)

# Add Typer app command to match entry point in pyproject.toml
@app.callback()
def callback():
    """Universal Package Helper CLI"""
    pass

@app.command()
def search(query: str = typer.Argument(..., help="Name of the software to search for")):
    """Search for packages across multiple sources"""
    try:
        # Convert query to list format expected by main
        args = query.split()
        sys.argv = [sys.argv[0]] + args
        main()
    except KeyboardInterrupt:
        console.print("\n[red]❌ Cancelled with Ctrl+C.[/red]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]❌ An error occurred: {e}[/red]")
        sys.exit(1)