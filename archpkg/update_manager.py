#!/usr/bin/env python3
"""
Update checking and management for archpkg-helper
"""

import threading
import time
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from archpkg.logging_config import get_logger
from archpkg.installed_apps import (
    get_all_installed_packages,
    update_package_info,
    InstalledPackage,
    get_packages_needing_update_check
)
from archpkg.search_aur import search_aur
from archpkg.search_pacman import search_pacman
from archpkg.search_flatpak import search_flatpak
from archpkg.search_snap import search_snap
from archpkg.search_apt import search_apt
from archpkg.search_dnf import search_dnf
from archpkg.config_manager import get_user_config

logger = get_logger(__name__)

class UpdateChecker:
    """Handles checking for package updates"""

    def __init__(self):
        self.is_checking = False
        self.last_check_time = None

    def check_for_updates(self, packages: Optional[List[InstalledPackage]] = None) -> Dict[str, Any]:
        """Check for updates for installed packages"""
        if self.is_checking:
            logger.warning("Update check already in progress")
            return {"status": "busy", "message": "Update check already in progress"}

        self.is_checking = True
        self.last_check_time = datetime.now(timezone.utc)

        try:
            if packages is None:
                packages = get_all_installed_packages()

            if not packages:
                logger.info("No packages to check for updates")
                return {"status": "success", "checked": 0, "updates_found": 0}

            logger.info(f"Checking for updates for {len(packages)} packages")

            updates_found = 0
            checked_count = 0

            for package in packages:
                try:
                    has_update, latest_version = self._check_single_package(package)
                    checked_count += 1

                    if has_update:
                        update_package_info(
                            package.name,
                            available_version=latest_version,
                            update_available=True,
                            last_update_check=datetime.now(timezone.utc).isoformat()
                        )
                        updates_found += 1
                        logger.info(f"Update found for {package.name}: {latest_version}")
                    else:
                        update_package_info(
                            package.name,
                            update_available=False,
                            last_update_check=datetime.now(timezone.utc).isoformat()
                        )

                except Exception as e:
                    logger.error(f"Failed to check updates for {package.name}: {e}")
                    continue

            result = {
                "status": "success",
                "checked": checked_count,
                "updates_found": updates_found,
                "timestamp": self.last_check_time.isoformat()
            }

            logger.info(f"Update check completed: {checked_count} checked, {updates_found} updates found")
            return result

        finally:
            self.is_checking = False

    def _check_single_package(self, package: InstalledPackage) -> tuple[bool, Optional[str]]:
        """Check for updates for a single package"""
        logger.debug(f"Checking updates for {package.name} from {package.source}")

        # Search for the package in the same source it was installed from
        results = []

        try:
            if package.source == "pacman":
                results = search_pacman(package.name)
            elif package.source == "aur":
                results = search_aur(package.name)
            elif package.source == "flatpak":
                results = search_flatpak(package.name)
            elif package.source == "snap":
                results = search_snap(package.name)
            elif package.source == "apt":
                results = search_apt(package.name)
            elif package.source == "dnf":
                results = search_dnf(package.name)
            else:
                logger.warning(f"Unknown package source: {package.source}")
                return False, None

        except Exception as e:
            logger.error(f"Failed to search for {package.name}: {e}")
            return False, None

        if not results:
            logger.debug(f"No results found for {package.name}")
            return False, None

        # Find the best match (usually the first result)
        latest_name, latest_desc, latest_source = results[0]

        # For now, we'll assume any difference means an update is available
        # In a real implementation, we'd need proper version comparison
        # For this demo, we'll just check if the package exists
        has_update = True  # Simplified logic
        latest_version = "latest"  # Would need proper version parsing

        return has_update, latest_version

class BackgroundUpdateManager:
    """Manages background update checking and downloading"""

    def __init__(self):
        self.update_checker = UpdateChecker()
        self.background_thread = None
        self.is_running = False
        self.check_interval_hours = 24

    def start_background_service(self) -> None:
        """Start the background update service"""
        if self.is_running:
            logger.warning("Background update service already running")
            return

        config = get_user_config()
        if not config.auto_update_enabled:
            logger.info("Auto-update not enabled, not starting background service")
            return

        self.check_interval_hours = config.update_check_interval_hours
        self.is_running = True

        self.background_thread = threading.Thread(
            target=self._background_worker,
            daemon=True,
            name="archpkg-update-checker"
        )
        self.background_thread.start()

        logger.info("Background update service started")

    def stop_background_service(self) -> None:
        """Stop the background update service"""
        self.is_running = False
        if self.background_thread:
            self.background_thread.join(timeout=5)
        logger.info("Background update service stopped")

    def _background_worker(self) -> None:
        """Background worker thread"""
        logger.info("Background update worker started")

        while self.is_running:
            try:
                # Check if we need to run update checks
                packages_to_check = get_packages_needing_update_check(self.check_interval_hours)

                if packages_to_check:
                    logger.info(f"Background update check: {len(packages_to_check)} packages need checking")
                    result = self.update_checker.check_for_updates(packages_to_check)

                    if result.get("updates_found", 0) > 0:
                        logger.info(f"Background update check found {result['updates_found']} updates")
                        # Could send notifications here

                # Sleep for the check interval
                sleep_time = self.check_interval_hours * 3600
                time.sleep(min(sleep_time, 300))  # Sleep in 5-minute chunks to allow quick shutdown

            except Exception as e:
                logger.error(f"Background update worker error: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying

        logger.info("Background update worker stopped")

    def trigger_manual_check(self) -> Dict[str, Any]:
        """Manually trigger an update check"""
        logger.info("Manual update check triggered")
        return self.update_checker.check_for_updates()

# Global update manager instance
update_manager = BackgroundUpdateManager()

def check_for_updates(packages: Optional[List[InstalledPackage]] = None) -> Dict[str, Any]:
    """Check for updates for installed packages"""
    return update_manager.update_checker.check_for_updates(packages)

def start_background_updates() -> None:
    """Start background update service"""
    update_manager.start_background_service()

def stop_background_updates() -> None:
    """Stop background update service"""
    update_manager.stop_background_service()

def trigger_update_check() -> Dict[str, Any]:
    """Trigger a manual update check"""
    return update_manager.trigger_manual_check()