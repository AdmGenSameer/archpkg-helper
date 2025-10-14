#!/usr/bin/env python3
"""
Background downloading and installation for archpkg-helper
"""

import os
import hashlib
import tempfile
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from archpkg.logging_config import get_logger
from archpkg.installed_apps import (
    get_all_installed_packages,
    update_package_info,
    get_packages_with_updates
)
from archpkg.config_manager import get_user_config

logger = get_logger(__name__)

class DownloadManager:
    """Manages background downloads with resumability"""

    def __init__(self):
        self.active_downloads: Dict[str, Dict[str, Any]] = {}
        self.download_dir = Path.home() / ".archpkg" / "downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def start_download(self, package_name: str, download_url: str,
                      callback: Optional[Callable] = None) -> str:
        """Start a background download"""
        if package_name in self.active_downloads:
            logger.warning(f"Download already in progress for {package_name}")
            return self.active_downloads[package_name]["download_id"]

        download_id = f"{package_name}_{int(datetime.now(timezone.utc).timestamp())}"
        temp_file = self.download_dir / f"{download_id}.tmp"

        download_info = {
            "download_id": download_id,
            "package_name": package_name,
            "url": download_url,
            "temp_file": temp_file,
            "status": "starting",
            "progress": 0,
            "total_size": 0,
            "downloaded_size": 0,
            "callback": callback,
            "thread": None
        }

        self.active_downloads[package_name] = download_info

        # Start download in background thread
        thread = threading.Thread(
            target=self._download_worker,
            args=(download_info,),
            daemon=True,
            name=f"download-{package_name}"
        )
        download_info["thread"] = thread
        thread.start()

        logger.info(f"Started download for {package_name}: {download_id}")
        return download_id

    def _download_worker(self, download_info: Dict[str, Any]) -> None:
        """Background download worker"""
        package_name = download_info["package_name"]
        url = download_info["url"]
        temp_file = download_info["temp_file"]

        try:
            download_info["status"] = "downloading"

            # Create request with resume support
            headers = {}
            if temp_file.exists():
                # Resume download
                downloaded_size = temp_file.stat().st_size
                headers["Range"] = f"bytes={downloaded_size}-"
                download_info["downloaded_size"] = downloaded_size
                logger.info(f"Resuming download for {package_name} from {downloaded_size} bytes")

            req = Request(url, headers=headers)

            with urlopen(req) as response:
                total_size = int(response.headers.get("content-length", 0))
                download_info["total_size"] = total_size

                if total_size > 0 and download_info["downloaded_size"] > 0:
                    # Verify we're resuming correctly
                    if response.code != 206:  # 206 Partial Content
                        logger.warning(f"Server doesn't support resume for {package_name}, restarting")
                        download_info["downloaded_size"] = 0
                        temp_file.unlink(missing_ok=True)

                mode = "ab" if download_info["downloaded_size"] > 0 else "wb"

                with open(temp_file, mode) as f:
                    downloaded = download_info["downloaded_size"]

                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)
                        download_info["downloaded_size"] = downloaded

                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            download_info["progress"] = progress

            download_info["status"] = "completed"
            logger.info(f"Download completed for {package_name}")

            # Notify callback if provided
            if download_info["callback"]:
                try:
                    download_info["callback"](download_info)
                except Exception as e:
                    logger.error(f"Download callback error for {package_name}: {e}")

        except HTTPError as e:
            download_info["status"] = "failed"
            download_info["error"] = f"HTTP {e.code}: {e.reason}"
            logger.error(f"Download failed for {package_name}: {e}")
        except URLError as e:
            download_info["status"] = "failed"
            download_info["error"] = str(e.reason)
            logger.error(f"Download failed for {package_name}: {e}")
        except Exception as e:
            download_info["status"] = "failed"
            download_info["error"] = str(e)
            logger.error(f"Download failed for {package_name}: {e}")

    def get_download_status(self, package_name: str) -> Optional[Dict[str, Any]]:
        """Get status of a download"""
        return self.active_downloads.get(package_name)

    def cancel_download(self, package_name: str) -> bool:
        """Cancel a download"""
        if package_name not in self.active_downloads:
            return False

        download_info = self.active_downloads[package_name]
        download_info["status"] = "cancelled"

        # Clean up temp file
        temp_file = download_info["temp_file"]
        if temp_file.exists():
            temp_file.unlink()

        del self.active_downloads[package_name]
        logger.info(f"Download cancelled for {package_name}")
        return True

    def get_completed_downloads(self) -> List[Dict[str, Any]]:
        """Get list of completed downloads"""
        return [
            info for info in self.active_downloads.values()
            if info["status"] == "completed"
        ]

    def cleanup_old_downloads(self, days_old: int = 7) -> None:
        """Clean up old temporary download files"""
        cutoff_time = datetime.now(timezone.utc).timestamp() - (days_old * 24 * 3600)

        for temp_file in self.download_dir.glob("*.tmp"):
            if temp_file.stat().st_mtime < cutoff_time:
                temp_file.unlink()
                logger.debug(f"Cleaned up old download file: {temp_file}")

class UpdateInstaller:
    """Handles installation of downloaded updates"""

    def __init__(self):
        self.download_manager = DownloadManager()

    def install_updates(self, package_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """Install updates for specified packages or all available updates"""
        config = get_user_config()

        if package_names is None:
            # Get all packages with available updates
            packages_with_updates = get_packages_with_updates()
            package_names = [p.name for p in packages_with_updates]

        if not package_names:
            return {"status": "success", "installed": 0, "message": "No updates available"}

        installed_count = 0
        failed_count = 0
        results = []

        for package_name in package_names:
            try:
                result = self._install_single_update(package_name)
                results.append(result)

                if result["status"] == "success":
                    installed_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                logger.error(f"Failed to install update for {package_name}: {e}")
                results.append({
                    "package": package_name,
                    "status": "error",
                    "error": str(e)
                })
                failed_count += 1

        return {
            "status": "success",
            "installed": installed_count,
            "failed": failed_count,
            "results": results
        }

    def _install_single_update(self, package_name: str) -> Dict[str, Any]:
        """Install update for a single package"""
        logger.info(f"Installing update for {package_name}")

        # This is a placeholder - actual installation would depend on the package source
        # For now, we'll just mark it as installed

        try:
            # In a real implementation, this would:
            # 1. Get the package info
            # 2. Run the appropriate installation command based on source
            # 3. Verify installation
            # 4. Update the installed package info

            update_package_info(
                package_name,
                installed_version="latest",  # Would be actual version
                update_available=False,
                last_updated=datetime.now(timezone.utc).isoformat()
            )

            return {
                "package": package_name,
                "status": "success",
                "message": "Update installed successfully"
            }

        except Exception as e:
            return {
                "package": package_name,
                "status": "failed",
                "error": str(e)
            }

class BackgroundUpdateService:
    """Complete background update service"""

    def __init__(self):
        self.download_manager = DownloadManager()
        self.update_installer = UpdateInstaller()
        self.is_running = False
        self.background_thread = None

    def start_service(self) -> None:
        """Start the background update service"""
        if self.is_running:
            return

        config = get_user_config()
        if not config.auto_update_enabled:
            logger.info("Auto-update not enabled")
            return

        self.is_running = True

        self.background_thread = threading.Thread(
            target=self._background_worker,
            daemon=True,
            name="archpkg-background-updates"
        )
        self.background_thread.start()

        logger.info("Background update service started")

    def stop_service(self) -> None:
        """Stop the background update service"""
        self.is_running = False
        if self.background_thread:
            self.background_thread.join(timeout=5)
        logger.info("Background update service stopped")

    def _background_worker(self) -> None:
        """Background worker for automatic updates"""
        logger.info("Background update worker started")

        while self.is_running:
            try:
                config = get_user_config()

                if config.auto_install_updates:
                    # Automatically install available updates
                    packages_with_updates = get_packages_with_updates()
                    if packages_with_updates:
                        logger.info(f"Auto-installing {len(packages_with_updates)} updates")
                        result = self.update_installer.install_updates()
                        logger.info(f"Auto-install result: {result}")

                # Clean up old downloads periodically
                self.download_manager.cleanup_old_downloads()

                # Sleep for check interval
                sleep_time = config.update_check_interval_hours * 3600
                time.sleep(min(sleep_time, 3600))  # Sleep in 1-hour chunks

            except Exception as e:
                logger.error(f"Background update worker error: {e}")
                time.sleep(3600)  # Wait 1 hour before retrying

        logger.info("Background update worker stopped")

# Global instances
download_manager = DownloadManager()
update_installer = UpdateInstaller()
background_update_service = BackgroundUpdateService()

def start_download(package_name: str, download_url: str,
                  callback: Optional[Callable] = None) -> str:
    """Start a background download"""
    return download_manager.start_download(package_name, download_url, callback)

def get_download_status(package_name: str) -> Optional[Dict[str, Any]]:
    """Get download status"""
    return download_manager.get_download_status(package_name)

def install_updates(package_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """Install updates"""
    return update_installer.install_updates(package_names)

def start_background_update_service() -> None:
    """Start background update service"""
    background_update_service.start_service()

def stop_background_update_service() -> None:
    """Stop background update service"""
    background_update_service.stop_service()