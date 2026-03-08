#!/usr/bin/env python3
# monitor.py
"""Background monitoring service for Arch Linux system maintenance.

This module provides background monitoring functionality for normal mode users.
It checks for Arch news, available updates, and provides proactive system advice.
"""

import sys
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import json

from archpkg.config_manager import get_user_config
from archpkg.advisor import get_arch_news, assess_aur_trust
from archpkg.logging_config import get_logger

logger = get_logger(__name__)


def check_system_status() -> Dict[str, Any]:
    """
    Check overall system status including news, updates, and trust issues.
    
    Returns:
        Dict with status information including news, updates, and recommendations
    """
    logger.info("Starting system status check")
    
    status = {
        'timestamp': datetime.now().isoformat(),
        'news': [],
        'updates_available': False,
        'update_count': 0,
        'low_trust_packages': [],
        'recommendations': []
    }
    
    # Check for Arch news
    try:
        news_items = get_arch_news()
        if news_items:
            status['news'] = news_items
            status['recommendations'].append(f"Review {len(news_items)} new Arch news item(s)")
    except Exception as e:
        logger.error(f"Failed to check Arch news: {e}")
    
    # Check for available updates
    try:
        result = subprocess.run(
            ['paru', '-Qu'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout.strip():
            updates = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            status['updates_available'] = True
            status['update_count'] = len(updates)
            status['recommendations'].append(f"{len(updates)} package update(s) available")
    except Exception as e:
        logger.error(f"Failed to check for updates: {e}")
    
    # Check trust scores of installed AUR packages
    try:
        result = subprocess.run(
            ['paru', '-Qm'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            installed_aur = []
            for line in result.stdout.split('\n'):
                if line.strip():
                    parts = line.strip().split()
                    if parts:
                        installed_aur.append(parts[0])
            
            # Only check first 10 packages to avoid long delays
            for pkg_name in installed_aur[:10]:
                try:
                    trust_result = assess_aur_trust(pkg_name)
                    score = trust_result.get('score', 0)
                    
                    if score < 40:
                        status['low_trust_packages'].append({
                            'name': pkg_name,
                            'score': score,
                            'reason': trust_result.get('reason', 'Low trust score')
                        })
                except Exception as e:
                    logger.debug(f"Failed to check trust for {pkg_name}: {e}")
            
            if status['low_trust_packages']:
                status['recommendations'].append(
                    f"{len(status['low_trust_packages'])} low-trust AUR package(s) detected"
                )
    except Exception as e:
        logger.error(f"Failed to audit AUR packages: {e}")
    
    logger.info(f"System status check complete: {len(status['recommendations'])} recommendations")
    return status


def send_notification(title: str, message: str, urgency: str = "normal") -> None:
    """
    Send a desktop notification to the user.
    
    Args:
        title: Notification title
        message: Notification message
        urgency: Urgency level (low, normal, critical)
    """
    try:
        subprocess.run(
            ['notify-send', '-u', urgency, '-a', 'archpkg', title, message],
            timeout=5
        )
        logger.info(f"Sent notification: {title}")
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")


def save_status_report(status: Dict) -> None:
    """
    Save status report to cache directory for later review.
    
    Args:
        status: Status dictionary from check_system_status()
    """
    try:
        cache_dir = Path.home() / '.cache' / 'archpkg'
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        status_file = cache_dir / 'monitor_status.json'
        with open(status_file, 'w') as f:
            json.dump(status, f, indent=2)
        
        logger.debug(f"Saved status report to {status_file}")
    except Exception as e:
        logger.error(f"Failed to save status report: {e}")


def monitor_once() -> None:
    """
    Perform a single monitoring check and notify if needed.
    Called by systemd timer or can be run manually.
    """
    logger.info("Running archpkg monitor check")
    
    # Check if monitoring is enabled
    config = get_user_config()
    
    # Only run in normal mode with proactive advice enabled
    if config.user_mode != 'normal' or not config.proactive_system_advice:
        logger.info("Monitoring disabled (not in normal mode or proactive advice off)")
        return
    
    # Check system status
    status = check_system_status()
    
    # Save status report
    save_status_report(status)
    
    # Send notifications if there are recommendations
    if status['recommendations']:
        recommendation_count = len(status['recommendations'])
        
        if recommendation_count == 1:
            title = "System Maintenance Recommendation"
            message = status['recommendations'][0]
        else:
            title = f"{recommendation_count} System Recommendations"
            message = '\n'.join(f"• {rec}" for rec in status['recommendations'][:3])
            if recommendation_count > 3:
                message += f"\n• +{recommendation_count - 3} more..."
        
        # Determine urgency
        urgency = "normal"
        if status['low_trust_packages']:
            urgency = "critical"
        elif status['news']:
            urgency = "normal"
        
        send_notification(title, message, urgency)
        logger.info(f"Sent {urgency} notification with {recommendation_count} recommendations")
    else:
        logger.info("No recommendations - system status is good")


def monitor_continuous(interval: int = 3600) -> None:
    """
    Run monitoring continuously with specified interval.
    
    Args:
        interval: Check interval in seconds (default: 3600 = 1 hour)
    """
    logger.info(f"Starting continuous monitoring with {interval}s interval")
    
    while True:
        try:
            monitor_once()
        except Exception as e:
            logger.error(f"Error during monitoring: {e}")
        
        logger.debug(f"Sleeping for {interval} seconds")
        time.sleep(interval)


if __name__ == '__main__':
    # Support running directly from command line
    import argparse
    
    parser = argparse.ArgumentParser(description='archpkg background monitor')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=3600, help='Check interval in seconds')
    args = parser.parse_args()
    
    if args.once:
        monitor_once()
    else:
        monitor_continuous(args.interval)
