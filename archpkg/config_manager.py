#!/usr/bin/env python3
"""
Configuration management for archpkg-helper
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from archpkg.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class UserConfig:
    """User configuration settings"""
    user_mode: str = "normal"  # "normal" or "advanced"
    auto_update_enabled: bool = False
    auto_update_mode: str = "manual"  # "automatic" or "manual"
    update_check_interval_hours: int = 24
    background_download_enabled: bool = True
    notification_enabled: bool = True
    auto_handle_arch_news: bool = True
    auto_review_aur_trust: bool = True
    auto_snapshot_before_update: bool = False
    proactive_system_advice: bool = True

class ConfigManager:
    """Manages user configuration with atomic file operations"""

    def __init__(self):
        self.config_dir = Path.home() / ".archpkg"
        self.config_file = self.config_dir / "config.json"
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Ensure configuration directory exists"""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _atomic_write(self, data: Dict[str, Any]) -> None:
        """Atomically write configuration to file"""
        temp_file = self.config_file.with_suffix('.tmp')

        try:
            # Write to temporary file first
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Atomic move to final location
            temp_file.replace(self.config_file)
            logger.info(f"Configuration saved to {self.config_file}")

        except Exception as e:
            # Clean up temp file on error
            if temp_file.exists():
                temp_file.unlink()
            logger.error(f"Failed to save configuration: {e}")
            raise

    def load_config(self) -> UserConfig:
        """Load configuration from file"""
        if not self.config_file.exists():
            logger.info("No configuration file found, using defaults")
            return UserConfig()

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Create config object from loaded data
            config = UserConfig()
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)

            logger.info("Configuration loaded successfully")
            return config

        except Exception as e:
            logger.warning(f"Failed to load configuration, using defaults: {e}")
            return UserConfig()

    def save_config(self, config: UserConfig) -> None:
        """Save configuration to file atomically"""
        data = asdict(config)
        self._atomic_write(data)

    def get_config_value(self, key: str) -> Any:
        """Get a specific configuration value"""
        config = self.load_config()
        return getattr(config, key, None)

    def set_config_value(self, key: str, value: Any) -> None:
        """Set a specific configuration value"""
        config = self.load_config()
        if hasattr(config, key):
            setattr(config, key, value)
            self.save_config(config)
            logger.info(f"Configuration updated: {key} = {value}")
        else:
            raise ValueError(f"Unknown configuration key: {key}")

    def show_config(self) -> str:
        """Get formatted configuration display"""
        config = self.load_config()
        lines = [
            f"Configuration file: {self.config_file}",
            "",
            "Current settings:",
            f"  User mode: {config.user_mode}",
            f"  Auto-update enabled: {config.auto_update_enabled}",
            f"  Auto-update mode: {config.auto_update_mode}",
            f"  Update check interval: {config.update_check_interval_hours} hours",
            f"  Background download: {config.background_download_enabled}",
            f"  Notifications: {config.notification_enabled}",
            f"  Auto-handle Arch news: {config.auto_handle_arch_news}",
            f"  Auto-review AUR trust: {config.auto_review_aur_trust}",
            f"  Auto-snapshot before update: {config.auto_snapshot_before_update}",
            f"  Proactive system advice: {config.proactive_system_advice}",
        ]
        return "\n".join(lines)

# Global configuration manager instance
config_manager = ConfigManager()

def get_user_config() -> UserConfig:
    """Get current user configuration"""
    return config_manager.load_config()

def save_user_config(config: UserConfig) -> None:
    """Save user configuration"""
    config_manager.save_config(config)

def set_config_option(key: str, value: Any) -> None:
    """Set a configuration option"""
    config_manager.set_config_value(key, value)

def get_config_option(key: str) -> Any:
    """Get a configuration option"""
    return config_manager.get_config_value(key)

def show_current_config() -> str:
    """Show current configuration"""
    return config_manager.show_config()