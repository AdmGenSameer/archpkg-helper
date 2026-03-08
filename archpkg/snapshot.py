# snapshot.py
"""Snapshot management module with support for multiple backends.
Supports Timeshift, snapper, and btrfs snapshots for pre-update system backups."""

import subprocess
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from archpkg.config import TIMEOUTS
from archpkg.exceptions import CommandGenerationError, PackageManagerNotFound
from archpkg.logging_config import get_logger, PackageHelperLogger

logger = get_logger(__name__)


class SnapshotBackend:
    """Enumeration of supported snapshot backends."""
    TIMESHIFT = 'timeshift'
    SNAPPER = 'snapper'
    BTRFS = 'btrfs'
    NONE = 'none'


def detect_snapshot_tool() -> Tuple[str, bool]:
    """Detect available snapshot tool on the system.
    
    Returns:
        Tuple[str, bool]: (tool_name, requires_sudo) where tool_name is from SnapshotBackend
    """
    logger.debug("Detecting available snapshot tools")
    
    # Check for Timeshift
    try:
        result = subprocess.run(['which', 'timeshift'], 
                               capture_output=True, 
                               timeout=TIMEOUTS['command_check'])
        if result.returncode == 0:
            logger.info("Detected Timeshift")
            return (SnapshotBackend.TIMESHIFT, True)
    except Exception as e:
        logger.debug(f"Timeshift check failed: {e}")
    
    # Check for snapper
    try:
        result = subprocess.run(['which', 'snapper'], 
                               capture_output=True, 
                               timeout=TIMEOUTS['command_check'])
        if result.returncode == 0:
            logger.info("Detected snapper")
            return (SnapshotBackend.SNAPPER, True)
    except Exception as e:
        logger.debug(f"snapper check failed: {e}")
    
    # Check for btrfs (basic support)
    try:
        result = subprocess.run(['which', 'btrfs'], 
                               capture_output=True, 
                               timeout=TIMEOUTS['command_check'])
        if result.returncode == 0:
            logger.info("Detected btrfs")
            return (SnapshotBackend.BTRFS, True)
    except Exception as e:
        logger.debug(f"btrfs check failed: {e}")
    
    logger.warning("No snapshot tool detected")
    return (SnapshotBackend.NONE, False)


def create_snapshot(comment: Optional[str] = None, tool: Optional[str] = None) -> bool:
    """Create a system snapshot using available tool.
    
    Args:
        comment: Optional comment/description for the snapshot
        tool: Force specific tool (timeshift, snapper, btrfs) or auto-detect
        
    Returns:
        bool: True if snapshot created successfully, False otherwise
        
    Raises:
        PackageManagerNotFound: When no snapshot tool is available
        CommandGenerationError: When snapshot creation fails
    """
    logger.info(f"Creating system snapshot with comment: '{comment}'")
    
    # Detect or validate tool
    if tool:
        detected_tool = tool
        requires_sudo = True
    else:
        detected_tool, requires_sudo = detect_snapshot_tool()
    
    if detected_tool == SnapshotBackend.NONE:
        logger.error("No snapshot tool available")
        raise PackageManagerNotFound(
            "No snapshot tool found. Install one of:\n"
            "- Timeshift: sudo pacman -S timeshift\n"
            "- snapper: sudo pacman -S snapper\n"
            "- For btrfs: sudo pacman -S btrfs-progs"
        )
    
    # Default comment
    if not comment:
        comment = f"Pre-update snapshot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    try:
        if detected_tool == SnapshotBackend.TIMESHIFT:
            cmd = ['sudo', 'timeshift', '--create', '--comments', comment]
            logger.debug(f"Running Timeshift command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info("Timeshift snapshot created successfully")
                return True
            else:
                logger.error(f"Timeshift snapshot failed: {result.stderr}")
                raise CommandGenerationError(f"Timeshift snapshot failed: {result.stderr}")
        
        elif detected_tool == SnapshotBackend.SNAPPER:
            cmd = ['sudo', 'snapper', 'create', '-d', comment]
            logger.debug(f"Running snapper command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                logger.info("snapper snapshot created successfully")
                return True
            else:
                logger.error(f"snapper snapshot failed: {result.stderr}")
                raise CommandGenerationError(f"snapper snapshot failed: {result.stderr}")
        
        elif detected_tool == SnapshotBackend.BTRFS:
            # Basic btrfs snapshot (requires manual configuration)
            logger.warning("btrfs snapshot requires manual subvolume configuration")
            raise CommandGenerationError(
                "btrfs snapshots require manual configuration. "
                "Consider using Timeshift or snapper for easier snapshot management."
            )
        
    except subprocess.TimeoutExpired:
        logger.error("Snapshot creation timed out")
        raise CommandGenerationError(f"{detected_tool} snapshot creation timed out")
    except Exception as e:
        PackageHelperLogger.log_exception(logger, f"Error creating {detected_tool} snapshot", e)
        raise CommandGenerationError(f"Failed to create snapshot: {str(e)}")
    
    return False


def list_snapshots(tool: Optional[str] = None, limit: int = 10) -> List[Dict[str, str]]:
    """List available snapshots.
    
    Args:
        tool: Force specific tool or auto-detect
        limit: Maximum number of snapshots to return
        
    Returns:
        List[Dict]: List of snapshot information dictionaries
    """
    logger.info("Listing available snapshots")
    
    # Detect or validate tool
    if tool:
        detected_tool = tool
    else:
        detected_tool, _ = detect_snapshot_tool()
    
    if detected_tool == SnapshotBackend.NONE:
        logger.warning("No snapshot tool available")
        return []
    
    snapshots = []
    
    try:
        if detected_tool == SnapshotBackend.TIMESHIFT:
            cmd = ['sudo', 'timeshift', '--list', '--scripted']
            logger.debug(f"Running Timeshift list command")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Parse Timeshift output
                for line in result.stdout.split('\n'):
                    if line.strip() and not line.startswith('#'):
                        parts = line.split()
                        if len(parts) >= 3:
                            snapshots.append({
                                'id': parts[0],
                                'date': f"{parts[1]} {parts[2]}",
                                'description': ' '.join(parts[3:]) if len(parts) > 3 else '',
                                'tool': 'timeshift'
                            })
                logger.info(f"Found {len(snapshots)} Timeshift snapshots")
        
        elif detected_tool == SnapshotBackend.SNAPPER:
            cmd = ['sudo', 'snapper', 'list', '--columns', 'number,date,description']
            logger.debug(f"Running snapper list command")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Parse snapper output (skip header lines)
                lines = result.stdout.split('\n')[2:]  # Skip header
                for line in lines:
                    if line.strip():
                        parts = line.split('|')
                        if len(parts) >= 3:
                            snapshots.append({
                                'id': parts[0].strip(),
                                'date': parts[1].strip(),
                                'description': parts[2].strip(),
                                'tool': 'snapper'
                            })
                logger.info(f"Found {len(snapshots)} snapper snapshots")
    
    except subprocess.TimeoutExpired:
        logger.error("Listing snapshots timed out")
        return []
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Error listing snapshots", e)
        return []
    
    return snapshots[:limit]


def restore_snapshot(snapshot_id: str, tool: Optional[str] = None) -> bool:
    """Restore a system snapshot.
    
    Args:
        snapshot_id: ID of the snapshot to restore
        tool: Force specific tool or auto-detect
        
    Returns:
        bool: True if restoration initiated successfully
        
    Raises:
        CommandGenerationError: When restoration fails
    """
    logger.info(f"Attempting to restore snapshot: {snapshot_id}")
    
    # Detect or validate tool
    if tool:
        detected_tool = tool
    else:
        detected_tool, _ = detect_snapshot_tool()
    
    if detected_tool == SnapshotBackend.NONE:
        logger.error("No snapshot tool available")
        raise PackageManagerNotFound("No snapshot tool found for restoration")
    
    try:
        if detected_tool == SnapshotBackend.TIMESHIFT:
            cmd = ['sudo', 'timeshift', '--restore', '--snapshot', snapshot_id]
            logger.warning("Timeshift restore requires reboot - this will start the restore process")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info(f"Timeshift restore initiated for snapshot {snapshot_id}")
                return True
            else:
                logger.error(f"Timeshift restore failed: {result.stderr}")
                raise CommandGenerationError(f"Restore failed: {result.stderr}")
        
        elif detected_tool == SnapshotBackend.SNAPPER:
            cmd = ['sudo', 'snapper', 'rollback', snapshot_id]
            logger.warning("snapper rollback requires reboot to take effect")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                logger.info(f"snapper rollback initiated for snapshot {snapshot_id}")
                return True
            else:
                logger.error(f"snapper rollback failed: {result.stderr}")
                raise CommandGenerationError(f"Rollback failed: {result.stderr}")
    
    except subprocess.TimeoutExpired:
        logger.error("Snapshot restore timed out")
        raise CommandGenerationError("Snapshot restore timed out")
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Error restoring snapshot", e)
        raise CommandGenerationError(f"Failed to restore snapshot: {str(e)}")
    
    return False


def delete_snapshot(snapshot_id: str, tool: Optional[str] = None) -> bool:
    """Delete a system snapshot.
    
    Args:
        snapshot_id: ID of the snapshot to delete
        tool: Force specific tool or auto-detect
        
    Returns:
        bool: True if deletion successful
    """
    logger.info(f"Deleting snapshot: {snapshot_id}")
    
    # Detect or validate tool
    if tool:
        detected_tool = tool
    else:
        detected_tool, _ = detect_snapshot_tool()
    
    if detected_tool == SnapshotBackend.NONE:
        logger.error("No snapshot tool available")
        return False
    
    try:
        if detected_tool == SnapshotBackend.TIMESHIFT:
            cmd = ['sudo', 'timeshift', '--delete', '--snapshot', snapshot_id]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return result.returncode == 0
        
        elif detected_tool == SnapshotBackend.SNAPPER:
            cmd = ['sudo', 'snapper', 'delete', snapshot_id]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return result.returncode == 0
    
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Error deleting snapshot", e)
        return False
    
    return False
