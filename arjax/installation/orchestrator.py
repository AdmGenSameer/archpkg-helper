"""High-level installation orchestration for the existing arjax CLI."""

from __future__ import annotations

import time
import logging
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from arjax.config.logging import get_logger
from arjax.installation.models import ProviderResult
from arjax.installation.providers import ProviderManager

logger = get_logger(__name__)


class InstallationOrchestrator:
    """Small wrapper around ProviderManager for CLI use with rich step-based output."""

    def __init__(self, provider_manager: Optional[ProviderManager] = None):
        self.provider_manager = provider_manager or ProviderManager()

    def install(self, package: str, provider_hint: Optional[str] = None) -> ProviderResult:
        logger.info("Installing %s using provider hint %s", package, provider_hint)
        console = Console()

        # Nice startup banner
        console.print()
        console.print(Panel(
            Text.assemble(
                ("Package : ", "bold"), (package, "green bold"), "\n",
                ("Action  : ", "bold"), ("Install", "cyan")
            ),
            title="[bold cyan]Arjax[/bold cyan]",
            border_style="cyan",
            width=45
        ))
        console.print()

        # Step 1: Resolving package...
        start_resolve = time.perf_counter()
        console.print("[bold cyan]▶[/bold cyan] [bold]Resolving package...[/bold]")
        with console.status("[bold blue]Resolving recipe...[/bold blue]"):
            recipe = self.provider_manager.recipes.find(package)
            time.sleep(0.2)  # small timing buffer for spinner visibility
        end_resolve = time.perf_counter()
        resolve_time = end_resolve - start_resolve

        if recipe:
            console.print(f"[green]✓[/green] Found recipe: [bold]{recipe.name}[/bold]")
        else:
            console.print(f"[cyan]ℹ[/cyan] No recipe found for '{package}', using default repository package")
        console.print()

        # Step 2: Selecting provider...
        start_select = time.perf_counter()
        console.print("[bold cyan]▶[/bold cyan] [bold]Selecting provider...[/bold]")
        
        # Determine candidate providers and log others
        candidate_providers = []
        for provider in self.provider_manager.providers:
            if provider_hint and provider.name != provider_hint.lower().strip():
                console.print(f"  {provider.name:<12} ...... [dim]not selected[/dim]")
                continue

            if not provider.supports(package, recipe):
                console.print(f"  {provider.name:<12} ...... [yellow]not supported[/yellow]")
                continue

            candidate_providers.append(provider)

        if not candidate_providers:
            end_select = time.perf_counter()
            select_time = end_select - start_select
            console.print("[red]✗[/red] No supported providers found for this request.")
            console.print()
            
            result = ProviderResult(
                provider_name="manager",
                package=package,
                success=False,
                message="No supported providers found",
            )
            
            # Print timing summary even on failure
            self._print_timing_summary(console, package, resolve_time, select_time, 0, 0, result)
            return result

        # Print candidate status
        for i, provider in enumerate(candidate_providers):
            status_text = "[green]selected[/green]" if i == 0 else "[dim]queued (fallback)[/dim]"
            console.print(f"  {provider.name:<12} ...... {status_text}")
        console.print()
        
        end_select = time.perf_counter()
        select_time = end_select - start_select

        selected_result = None
        dependency_time = 0.0
        install_time = 0.0

        for provider in candidate_providers:
            # Step 3: Checking dependencies...
            start_dep = time.perf_counter()
            console.print(f"[bold cyan]▶[/bold cyan] [bold]Checking dependencies for {provider.name}...[/bold]")
            
            dep_ok = True
            dep_msg = "Dependencies ready"
            
            if provider.name in ["repository", "vendor"]:
                from arjax.installation.providers import default_package_manager
                pm = default_package_manager()
                from arjax.package_management.command_gen import check_command_availability
                if not check_command_availability(pm):
                    dep_ok = False
                    dep_msg = f"Package manager '{pm}' not found on system"
            elif provider.name == "flatpak":
                from arjax.package_management.command_gen import check_command_availability
                if not check_command_availability("flatpak"):
                    dep_ok = False
                    dep_msg = "Flatpak CLI not found on system"
            elif provider.name == "snap":
                from arjax.package_management.command_gen import check_command_availability
                if not check_command_availability("snap"):
                    dep_ok = False
                    dep_msg = "Snap CLI not found on system"
            
            end_dep = time.perf_counter()
            dependency_time += (end_dep - start_dep)

            if not dep_ok:
                console.print(f"[yellow]⚠[/yellow] Dependency check failed: {dep_msg}")
                console.print()
                continue
            else:
                console.print("[green]✓[/green] Dependencies ready")
                console.print()

            # Step 4: Running installation...
            start_inst = time.perf_counter()
            console.print(f"[bold cyan]▶[/bold cyan] [bold]Running installation via {provider.name}...[/bold]")
            
            with console.status(f"[bold blue]Installing {package}...[/bold blue]"):
                result = provider.install(package, recipe)
            
            end_inst = time.perf_counter()
            install_time += (end_inst - start_inst)

            if result.success:
                console.print(f"[green]✓[/green] Successfully installed {package} via {provider.name}")
                selected_result = result
                break
            elif result.skipped:
                console.print(f"[yellow]⚠[/yellow] Skipped {provider.name}: {result.message}")
                console.print()
                # Try next provider
                continue
            else:
                console.print(f"[red]✗[/red] Failed {provider.name}: {result.error or result.message}")
                selected_result = result
                break

        if not selected_result:
            selected_result = ProviderResult(
                provider_name="manager",
                package=package,
                success=False,
                message="No provider could install the package",
            )

        # Print final timing and status summary
        self._print_timing_summary(console, package, resolve_time, select_time, dependency_time, install_time, selected_result)
        return selected_result

    def _print_timing_summary(self, console: Console, package: str, resolve_time: float, select_time: float, dependency_time: float, install_time: float, result: ProviderResult) -> None:
        total_time = resolve_time + select_time + dependency_time + install_time

        def fmt_time(seconds):
            if seconds < 1.0:
                return f"{seconds * 1000:.0f} ms"
            return f"{seconds:.2f} s"

        console.print()
        console.print("[bold cyan]Installation Complete[/bold cyan]")
        console.print("[dim]───────────────────────────────────────[/dim]")
        console.print(f"Resolving recipe.......... {fmt_time(resolve_time)}")
        console.print(f"Selecting provider........ {fmt_time(select_time)}")
        console.print(f"Checking dependencies..... {fmt_time(dependency_time)}")
        console.print(f"Installing............... {fmt_time(install_time)}")
        console.print(f"[bold]Total.................... {fmt_time(total_time)}[/bold]")
        console.print("[dim]───────────────────────────────────────[/dim]")
        
        status_text = "[bold green]Success[/bold green]" if result.success else "[bold red]Failed[/bold red]"
        console.print(f"Package : [bold]{package}[/bold]")
        console.print(f"Provider: {result.provider_name}")
        console.print(f"Time    : {fmt_time(total_time)}")
        console.print(f"Status  : {status_text}")
        if not result.success and result.error:
            console.print(f"Error   : [red]{result.error}[/red]")
        console.print()
