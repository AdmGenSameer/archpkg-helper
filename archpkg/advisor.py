#!/usr/bin/env python3
"""Automation/advice helpers for normal vs advanced user flows."""

import subprocess
from typing import Dict, Any, Optional
from archpkg.search_aur import get_aur_package_details
from archpkg.logging_config import get_logger

logger = get_logger(__name__)


def get_arch_news() -> Dict[str, Any]:
    """Fetch Arch news via paru.

    Returns:
        Dict with keys: available, has_news, output, error
    """
    try:
        result = subprocess.run(['paru', '-Pw'], capture_output=True, text=True, check=False)
        output = (result.stdout or '').strip()
        error = (result.stderr or '').strip()

        has_news = bool(output)
        return {
            'available': True,
            'has_news': has_news,
            'output': output,
            'error': error,
            'return_code': result.returncode,
        }
    except FileNotFoundError:
        return {
            'available': False,
            'has_news': False,
            'output': '',
            'error': 'paru not found',
            'return_code': 127,
        }


def assess_aur_trust(package_name: str) -> Dict[str, Any]:
    """Assess AUR package trust from AUR metadata.

    Heuristic score ranges 0-100 and confidence labels:
    - 70+ : high
    - 40-69: medium
    - <40 : low
    """
    details = get_aur_package_details(package_name)
    if not details:
        return {
            'package': package_name,
            'score': 35,
            'confidence': 'unknown',
            'reason': 'Could not fetch AUR metadata',
            'details': None,
        }

    votes = int(details.get('votes') or 0)
    popularity = float(details.get('popularity') or 0.0)
    maintainer = details.get('maintainer')
    out_of_date = details.get('out_of_date')

    score = 30
    if votes >= 500:
        score += 30
    elif votes >= 100:
        score += 20
    elif votes >= 25:
        score += 10

    if popularity >= 10:
        score += 25
    elif popularity >= 2:
        score += 15
    elif popularity >= 0.5:
        score += 8

    if maintainer and maintainer != 'orphan':
        score += 10
    else:
        score -= 10

    if out_of_date:
        score -= 20

    score = max(0, min(score, 100))

    if score >= 70:
        confidence = 'high'
    elif score >= 40:
        confidence = 'medium'
    else:
        confidence = 'low'

    return {
        'package': package_name,
        'score': score,
        'confidence': confidence,
        'reason': f"votes={votes}, popularity={popularity:.2f}, maintainer={maintainer or 'orphan'}, out_of_date={'yes' if out_of_date else 'no'}",
        'details': details,
    }


def apply_user_mode_defaults(mode: str) -> Dict[str, Any]:
    """Return config defaults for a user mode."""
    mode = (mode or 'normal').strip().lower()
    if mode == 'advanced':
        return {
            'user_mode': 'advanced',
            'auto_update_enabled': False,
            'auto_update_mode': 'manual',
            'update_check_interval_hours': 24,
            'background_download_enabled': True,
            'notification_enabled': True,
            'auto_handle_arch_news': False,
            'auto_review_aur_trust': False,
            'auto_snapshot_before_update': False,
            'proactive_system_advice': False,
        }

    # normal (recommended)
    return {
        'user_mode': 'normal',
        'auto_update_enabled': True,
        'auto_update_mode': 'automatic',
        'update_check_interval_hours': 24,
        'background_download_enabled': True,
        'notification_enabled': True,
        'auto_handle_arch_news': True,
        'auto_review_aur_trust': True,
        'auto_snapshot_before_update': True,
        'proactive_system_advice': True,
    }
