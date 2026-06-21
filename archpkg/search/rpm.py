#!/usr/bin/env python3
"""
RPM search module for generic RPM-based distributions.
Handles rpm command for querying packages.
"""

import subprocess
import re
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

def search_rpm(query: str, limit: int = 10) -> List[Tuple[str, str, str]]:
    """
    Search for packages using rpm command.
    Works on RPM-based systems (RHEL, CentOS, Rocky Linux, AlmaLinux, etc.).
    
    Args:
        query: Package name to search for
        limit: Maximum number of results to return
        
    Returns:
        List of tuples (package_name, description, source)
    """
    try:
        # Try rpm -qa for installed packages first
        cmd = ["rpm", "-qa", "--queryformat", "%{NAME}\t%{VERSION}\t%{SUMMARY}\\n", f"*{query}*"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        
        results = []
        
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            
            for line in lines[:limit]:
                parts = line.split('\t')
                if len(parts) >= 3:
                    name = parts[0].strip()
                    version = parts[1].strip()
                    summary = parts[2].strip()
                    results.append((name, f"{summary} (v{version})", "RPM (Installed)"))
        
        # If no results or need more, try yum/dnf search
        if len(results) < limit:
            try:
                # Try yum first (older systems)
                yum_cmd = ["yum", "search", query]
                yum_result = subprocess.run(
                    yum_cmd,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False
                )
                
                if yum_result.returncode == 0:
                    in_results = False
                    for line in yum_result.stdout.split('\n'):
                        if '=====' in line or 'Matched' in line.lower():
                            in_results = True
                            continue
                        
                        if in_results and ':' in line:
                            match = re.match(r'^(\S+)\s*:\s*(.+)$', line)
                            if match:
                                name = match.group(1).strip()
                                desc = match.group(2).strip()
                                results.append((name, desc, "RPM (Available)"))
                                
                                if len(results) >= limit:
                                    break
            except FileNotFoundError:
                logger.debug("yum not found, skipping")
        
        return results[:limit]
        
    except subprocess.TimeoutExpired:
        logger.warning("RPM search timed out")
        return []
    except FileNotFoundError:
        logger.debug("rpm command not found")
        return []
    except Exception as e:
        logger.error(f"Error searching with rpm: {e}")
        return []
