#!/usr/bin/env python3
"""
Installed applications tracking for archpkg-helper
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from archpkg.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class InstalledPackage:
    """Represents an installed package"""
    name: str
    version: Optional[str] = None
    source: str = "unknown"
    install_date: str = ""
    last_update_check: Optional[str] = None
    available_version: Optional[str] = None
    update_available: bool = False
    install_method: str = "archpkg"  # "archpkg", "github", "manual"

class InstalledAppsManager:
    """Manages tracking of installed applications"""

    def __init__(self):
        self.config_dir = Path.home() / ".archpkg"
        self.installed_file = self.config_dir / "installed.json"
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Ensure configuration directory exists"""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _atomic_write(self, data: Dict[str, Any]) -> None:
        """Atomically write installed apps data to file"""
        temp_file = self.installed_file.with_suffix('.tmp')

        try:
            # Write to temporary file first
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Atomic move to final location
            temp_file.replace(self.installed_file)
            logger.debug(f"Installed apps data saved to {self.installed_file}")

        except Exception as e:
            # Clean up temp file on error
            if temp_file.exists():
                temp_file.unlink()
            logger.error(f"Failed to save installed apps data: {e}")
            raise

    def _load_installed_data(self) -> Dict[str, Dict[str, Any]]:
        """Load installed packages data from file"""
        if not self.installed_file.exists():
            logger.debug("No installed apps file found, starting fresh")
            return {}

        try:
            with open(self.installed_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"Loaded installed apps data with {len(data)} packages")
                return data

        except Exception as e:
            logger.warning(f"Failed to load installed apps data, starting fresh: {e}")
            return {}

    def _save_installed_data(self, data: Dict[str, Dict[str, Any]]) -> None:
        """Save installed packages data to file atomically"""
        self._atomic_write(data)

    def add_package(self, package: InstalledPackage) -> None:
        """Add a package to the installed list"""
        data = self._load_installed_data()

        # Set install date if not provided
        if not package.install_date:
            package.install_date = datetime.now(timezone.utc).isoformat()

        data[package.name] = asdict(package)
        self._save_installed_data(data)
        logger.info(f"Added package to tracking: {package.name} ({package.source})")

    def remove_package(self, package_name: str) -> bool:
        """Remove a package from the installed list"""
        data = self._load_installed_data()

        if package_name in data:
            del data[package_name]
            self._save_installed_data(data)
            logger.info(f"Removed package from tracking: {package_name}")
            return True

        logger.warning(f"Package not found in tracking: {package_name}")
        return False

    def get_package(self, package_name: str) -> Optional[InstalledPackage]:
        """Get information about an installed package"""
        data = self._load_installed_data()

        if package_name in data:
            pkg_data = data[package_name]
            return InstalledPackage(**pkg_data)

        return None

    def get_all_packages(self) -> List[InstalledPackage]:
        """Get all installed packages"""
        data = self._load_installed_data()
        packages = []

        for pkg_data in data.values():
            packages.append(InstalledPackage(**pkg_data))

        return packages

    def update_package_info(self, package_name: str, **updates) -> bool:
        """Update information for an installed package"""
        data = self._load_installed_data()

        if package_name in data:
            # Update the package data
            data[package_name].update(updates)

            # Update last update check timestamp if we're checking for updates
            if 'last_update_check' not in updates:
                data[package_name]['last_update_check'] = datetime.now(timezone.utc).isoformat()

            self._save_installed_data(data)
            logger.debug(f"Updated package info: {package_name}")
            return True

        logger.warning(f"Package not found for update: {package_name}")
        return False

    def get_packages_needing_update_check(self, max_age_hours: int = 24) -> List[InstalledPackage]:
        """Get packages that need update checking"""
        packages = self.get_all_packages()
        needing_check = []

        now = datetime.now(timezone.utc)

        for pkg in packages:
            needs_check = True

            if pkg.last_update_check:
                try:
                    last_check = datetime.fromisoformat(pkg.last_update_check.replace('Z', '+00:00'))
                    hours_since_check = (now - last_check).total_seconds() / 3600

                    if hours_since_check < max_age_hours:
                        needs_check = False
                except ValueError:
                    # Invalid timestamp, needs check
                    pass

            if needs_check:
                needing_check.append(pkg)

        logger.debug(f"Found {len(needing_check)} packages needing update check")
        return needing_check

    def get_packages_with_updates(self) -> List[InstalledPackage]:
        """Get packages that have available updates"""
        packages = self.get_all_packages()
        with_updates = [pkg for pkg in packages if pkg.update_available]

        logger.debug(f"Found {len(with_updates)} packages with available updates")
        return with_updates

    def mark_update_available(self, package_name: str, available_version: str) -> bool:
        """Mark that an update is available for a package"""
        return self.update_package_info(
            package_name,
            available_version=available_version,
            update_available=True,
            last_update_check=datetime.now(timezone.utc).isoformat()
        )

    def mark_update_installed(self, package_name: str, new_version: str) -> bool:
        """Mark that an update has been installed for a package"""
        return self.update_package_info(
            package_name,
            version=new_version,
            available_version=None,
            update_available=False,
            last_update_check=datetime.now(timezone.utc).isoformat()
        )

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about installed packages"""
        packages = self.get_all_packages()
        with_updates = len([p for p in packages if p.update_available])

        return {
            'total_packages': len(packages),
            'packages_with_updates': with_updates,
            'packages_up_to_date': len(packages) - with_updates,
        }

    def show_installed_packages(self) -> str:
        """Get formatted display of installed packages"""
        packages = self.get_all_packages()

        if not packages:
            return "No packages installed via archpkg."

        lines = [f"Installed packages ({len(packages)}):", ""]

        for pkg in packages:
            status = "✓ Up to date"
            if pkg.update_available:
                status = f"⚠ Update available: {pkg.available_version}"

            lines.append(f"  {pkg.name} ({pkg.version or 'unknown'}) - {pkg.source}")
            lines.append(f"    Status: {status}")
            lines.append(f"    Installed: {pkg.install_date}")
            if pkg.last_update_check:
                lines.append(f"    Last checked: {pkg.last_update_check}")
            lines.append("")

        return "\n".join(lines)

# Global installed apps manager instance
installed_apps_manager = InstalledAppsManager()

def add_installed_package(package: InstalledPackage) -> None:
    """Add a package to the installed list"""
    installed_apps_manager.add_package(package)

def remove_installed_package(package_name: str) -> bool:
    """Remove a package from the installed list"""
    return installed_apps_manager.remove_package(package_name)

def get_installed_package(package_name: str) -> Optional[InstalledPackage]:
    """Get information about an installed package"""
    return installed_apps_manager.get_package(package_name)

def get_all_installed_packages() -> List[InstalledPackage]:
    """Get all installed packages"""
    return installed_apps_manager.get_all_packages()

def update_package_info(package_name: str, **updates) -> bool:
    """Update information for an installed package"""
    return installed_apps_manager.update_package_info(package_name, **updates)

def get_packages_needing_update_check(max_age_hours: int = 24) -> List[InstalledPackage]:
    """Get packages that need update checking"""
    return installed_apps_manager.get_packages_needing_update_check(max_age_hours)

def get_packages_with_updates() -> List[InstalledPackage]:
    """Get packages that have available updates"""
    return installed_apps_manager.get_packages_with_updates()

def get_installed_stats() -> Dict[str, int]:
    """Get statistics about installed packages"""
    return installed_apps_manager.get_stats()