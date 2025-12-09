#!/usr/bin/env python3
"""
Security validations for archpkg-helper
"""

import hashlib
import hmac
import os
from typing import Optional, Dict, Any
from pathlib import Path
from archpkg.logging_config import get_logger

logger = get_logger(__name__)

class SecurityValidator:
    """Handles security validations for package updates"""

    def __init__(self):
        self.supported_hash_algorithms = {
            'md5': hashlib.md5,
            'sha1': hashlib.sha1,
            'sha256': hashlib.sha256,
            'sha512': hashlib.sha512
        }

    def validate_checksum(self, file_path: Path, expected_hash: str,
                         algorithm: str = 'sha256') -> bool:
        """Validate file checksum against expected hash"""
        if algorithm not in self.supported_hash_algorithms:
            logger.error(f"Unsupported hash algorithm: {algorithm}")
            return False

        if not file_path.exists():
            logger.error(f"File does not exist: {file_path}")
            return False

        try:
            hash_func = self.supported_hash_algorithms[algorithm]()

            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_func.update(chunk)

            calculated_hash = hash_func.hexdigest()
            is_valid = calculated_hash.lower() == expected_hash.lower()

            if is_valid:
                logger.info(f"Checksum validation passed for {file_path.name}")
            else:
                logger.error(f"Checksum validation failed for {file_path.name}")
                logger.debug(f"Expected: {expected_hash}")
                logger.debug(f"Calculated: {calculated_hash}")

            return is_valid

        except Exception as e:
            logger.error(f"Error validating checksum for {file_path}: {e}")
            return False

    def generate_checksum(self, file_path: Path, algorithm: str = 'sha256') -> Optional[str]:
        """Generate checksum for a file"""
        if algorithm not in self.supported_hash_algorithms:
            logger.error(f"Unsupported hash algorithm: {algorithm}")
            return None

        if not file_path.exists():
            logger.error(f"File does not exist: {file_path}")
            return None

        try:
            hash_func = self.supported_hash_algorithms[algorithm]()

            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_func.update(chunk)

            return hash_func.hexdigest()

        except Exception as e:
            logger.error(f"Error generating checksum for {file_path}: {e}")
            return None

class PackageSecurityValidator:
    """Validates package security and integrity"""

    def __init__(self):
        self.security_validator = SecurityValidator()
        self.trusted_keys: Dict[str, str] = {}  # Package name -> expected public key

    def validate_package_source(self, package_name: str, source: str) -> Dict[str, Any]:
        """Validate that the package source is trusted"""
        result = {
            "valid": False,
            "reason": "",
            "warnings": []
        }

        # Basic source validation
        trusted_sources = ['pacman', 'aur', 'flatpak', 'snap', 'apt', 'dnf']

        if source not in trusted_sources:
            result["reason"] = f"Unknown package source: {source}"
            logger.warning(f"Package {package_name} from unknown source: {source}")
            return result

        # Additional validation for AUR (less trusted)
        if source == 'aur':
            result["warnings"].append(
                "AUR packages are user-contributed and may pose security risks"
            )
            logger.warning(f"AUR package {package_name} - additional caution advised")

        result["valid"] = True
        logger.info(f"Package source validation passed for {package_name} from {source}")
        return result

    def validate_download_integrity(self, download_path: Path,
                                  expected_checksums: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Validate downloaded package integrity"""
        result = {
            "valid": False,
            "checksums_validated": [],
            "errors": []
        }

        if not download_path.exists():
            result["errors"].append(f"Download file does not exist: {download_path}")
            return result

        # If no expected checksums provided, we can only do basic validation
        if not expected_checksums:
            logger.warning("No expected checksums provided - limited validation possible")
            result["valid"] = True  # Allow but warn
            result["warnings"] = ["No checksum validation available"]
            return result

        # Validate against provided checksums
        all_valid = True
        for algorithm, expected_hash in expected_checksums.items():
            is_valid = self.security_validator.validate_checksum(
                download_path, expected_hash, algorithm
            )

            result["checksums_validated"].append({
                "algorithm": algorithm,
                "valid": is_valid
            })

            if not is_valid:
                all_valid = False
                result["errors"].append(f"{algorithm} checksum validation failed")

        result["valid"] = all_valid

        if all_valid:
            logger.info(f"Download integrity validation passed for {download_path.name}")
        else:
            logger.error(f"Download integrity validation failed for {download_path.name}")

        return result

    def validate_installation_safety(self, package_name: str, install_command: str) -> Dict[str, Any]:
        """Validate that the installation command is safe to execute"""
        result = {
            "safe": False,
            "warnings": [],
            "blocked": False,
            "reason": ""
        }

        # Dangerous command patterns to block
        # NOTE: This is a basic pattern matching implementation
        # A production system should use:
        # 1. Proper shell command parsing
        # 2. Regex patterns for more flexible matching
        # 3. Whitelist of allowed commands rather than blacklist
        # 4. Integration with security scanning tools
        import re
        
        dangerous_patterns = [
            r'rm\s+-rf\s+/',  # Recursive delete from root
            r'dd\s+if=',  # Disk operations
            r'mkfs',  # Filesystem formatting
            r'fdisk',  # Disk partitioning
            r'format',  # Formatting operations
            r'wget.*\|.*bash',  # Pipe to bash
            r'curl.*\|.*bash',  # Pipe to bash
            r'chmod\s+777',  # Overly permissive permissions
            r'chown.*root',  # Change ownership to root
            r'passwd',  # Password changes
            r'shadow',  # Shadow file access
            r'sudoers',  # Sudoers file modification
        ]

        command_lower = install_command.lower()

        for pattern in dangerous_patterns:
            if re.search(pattern, command_lower):
                result["blocked"] = True
                result["reason"] = f"Command contains dangerous pattern: {pattern}"
                logger.error(f"Blocked dangerous install command for {package_name}: {pattern}")
                return result

        # Check for sudo usage (warn but allow)
        if 'sudo' in command_lower:
            result["warnings"].append("Command uses sudo - ensure you have appropriate permissions")

        # Check for network downloads in install commands (warn)
        if 'wget' in command_lower or 'curl' in command_lower:
            result["warnings"].append("Command downloads from network - verify source trustworthiness")

        result["safe"] = True
        logger.info(f"Installation safety validation passed for {package_name}")
        return result

class UpdateSecurityManager:
    """Manages security for the update process"""

    def __init__(self):
        self.package_validator = PackageSecurityValidator()

    def pre_update_validation(self, package_name: str, source: str,
                            install_command: str) -> Dict[str, Any]:
        """Perform all security validations before allowing an update"""
        validation_result = {
            "approved": False,
            "source_valid": False,
            "command_safe": False,
            "warnings": [],
            "errors": []
        }

        # Validate package source
        source_validation = self.package_validator.validate_package_source(package_name, source)
        validation_result["source_valid"] = source_validation["valid"]
        validation_result["warnings"].extend(source_validation.get("warnings", []))

        if not source_validation["valid"]:
            validation_result["errors"].append(f"Source validation failed: {source_validation['reason']}")
            return validation_result

        # Validate installation command safety
        command_validation = self.package_validator.validate_installation_safety(package_name, install_command)
        validation_result["command_safe"] = command_validation["safe"]
        validation_result["warnings"].extend(command_validation.get("warnings", []))

        if command_validation["blocked"]:
            validation_result["errors"].append(f"Command blocked: {command_validation['reason']}")
            return validation_result

        # All validations passed
        validation_result["approved"] = True
        logger.info(f"Pre-update security validation passed for {package_name}")

        return validation_result

    def validate_downloaded_package(self, package_name: str, download_path: Path,
                                  expected_checksums: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Validate a downloaded package before installation"""
        return self.package_validator.validate_download_integrity(download_path, expected_checksums)

# Global security manager instance
security_manager = UpdateSecurityManager()

def validate_update_security(package_name: str, source: str, install_command: str) -> Dict[str, Any]:
    """Validate security for a package update"""
    return security_manager.pre_update_validation(package_name, source, install_command)

def validate_download_integrity(download_path: Path, expected_checksums: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Validate download integrity"""
    return security_manager.validate_downloaded_package("unknown", download_path, expected_checksums)