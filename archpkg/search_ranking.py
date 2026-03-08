#!/usr/bin/env python3
# search_ranking.py
"""
Search result ranking and deduplication utilities.

This module contains the core ranking algorithm used by both CLI and GUI
to rank and deduplicate search results for optimal user experience.
"""

from typing import List, Tuple, Optional
from archpkg.config import JUNK_KEYWORDS, LOW_PRIORITY_KEYWORDS, BOOST_KEYWORDS
from archpkg.logging_config import get_logger

logger = get_logger(__name__)

# Minimum length for meaningful prefix matching in scoring
MIN_PREFIX_LENGTH = 3


def is_valid_package(name: str, desc: Optional[str]) -> bool:
    """Check if a package is valid (not junk/meta package).
    
    Args:
        name: Package name
        desc: Package description
        
    Returns:
        bool: True if package is valid, False if it's a junk/meta package
    """
    desc = (desc or "").lower()
    is_junk = any(bad in desc for bad in JUNK_KEYWORDS)
    
    if is_junk:
        logger.debug(f"Package '{name}' filtered out as junk package")
    
    return not is_junk


def deduplicate_packages(packages: List[Tuple[str, str, str]], prefer_aur: bool = False) -> List[Tuple[str, str, str]]:
    """Remove duplicate packages, preferring Pacman over AUR by default.
    
    Args:
        packages: List of (name, description, source) tuples
        prefer_aur: If True, prefer AUR packages over Pacman when duplicates exist
        
    Returns:
        List[Tuple[str, str, str]]: Deduplicated packages with preferred sources
    """
    logger.debug(f"Deduplicating {len(packages)} packages, prefer_aur={prefer_aur}")
    
    package_groups = {}
    for name, desc, source in packages:
        if name not in package_groups:
            package_groups[name] = []
        package_groups[name].append((name, desc, source))
    
    deduplicated = []
    for name, group in package_groups.items():
        if len(group) == 1:
            deduplicated.append(group[0])
        else:
            sources = [source for _, _, source in group]
            
            if prefer_aur and 'aur' in sources:
                preferred = next((pkg for pkg in group if pkg[2] == 'aur'), group[0])
                logger.debug(f"Package '{name}' available in multiple sources, preferring AUR")
            elif 'pacman' in sources:
                preferred = next((pkg for pkg in group if pkg[2] == 'pacman'), group[0])
                logger.debug(f"Package '{name}' available in multiple sources, preferring Pacman")
            else:
                preferred = group[0]
                logger.debug(f"Package '{name}' available in multiple sources, using first: {preferred[2]}")
            
            deduplicated.append(preferred)
    
    logger.info(f"Deduplicated {len(packages)} packages to {len(deduplicated)} unique packages")
    return deduplicated


def get_top_matches(query: str, all_packages: List[Tuple[str, str, str]], limit: int = 5) -> List[Tuple[str, str, str]]:
    """Get top matching packages with improved scoring algorithm for multi-word queries.
    
    Implements a sophisticated scoring system that considers:
    - Exact matches (highest priority)
    - Hyphenated and concatenated versions ("vs code" matches "vscode")
    - Token matching with partial boost
    - Source priority (official repos > AUR > flatpak > snap)
    - Boost/penalty keywords
    
    Args:
        query: Search query string
        all_packages: List of (name, description, source) tuples
        limit: Maximum number of results to return (default: 5)
        
    Returns:
        List[Tuple[str, str, str]]: Top-ranked packages limited to 'limit'
    """
    logger.debug(f"Scoring {len(all_packages)} packages for query: '{query}'")
    
    if not all_packages:
        logger.debug("No packages to score")
        return []
        
    query = query.lower()
    query_tokens = set(query.split())
    # Create hyphenated and concatenated versions for better matching
    query_hyphenated = query.replace(" ", "-")
    query_concat = query.replace(" ", "")
    scored_results = []

    for name, desc, source in all_packages:
        if not is_valid_package(name, desc):
            continue

        name_l = name.lower()
        desc_l = (desc or "").lower()
        name_tokens = set(name_l.replace("-", " ").split())
        desc_tokens = set(desc_l.split())

        score = 0

        # IMPROVED: Better handling of multi-word queries
        # Exact match (highest priority)
        if query == name_l:
            score += 150
            logger.debug(f"Exact match bonus for '{name}': +150")
        # Check hyphenated version: "vs code" matches "vscode"
        elif query_hyphenated == name_l:
            score += 140
            logger.debug(f"Hyphenated match bonus for '{name}': +140")
        # Check concatenated version: "vs code" matches "vscode"  
        elif query_concat == name_l:
            score += 130
            logger.debug(f"Concatenated match bonus for '{name}': +130")
        # Substring match
        elif query in name_l:
            score += 80
            logger.debug(f"Substring match bonus for '{name}': +80")
        # Check if hyphenated query is in name
        elif query_hyphenated in name_l:
            score += 70
            logger.debug(f"Hyphenated substring match bonus for '{name}': +70")

        # IMPROVED: Token matching with better weight for multi-word queries
        matched_tokens = query_tokens & name_tokens
        if matched_tokens:
            # If most query tokens match, give significant bonus
            match_ratio = len(matched_tokens) / len(query_tokens)
            if match_ratio >= 0.8:  # 80% or more tokens match
                score += 60
                logger.debug(f"High token match ratio for '{name}': +60")
            elif match_ratio >= 0.5:  # 50% or more tokens match
                score += 30
                logger.debug(f"Medium token match ratio for '{name}': +30")
            else:
                score += len(matched_tokens) * 5
                logger.debug(f"Token matches for '{name}': +{len(matched_tokens) * 5}")

        # Prefix matching for query tokens
        for q in query_tokens:
            for token in name_tokens:
                if token.startswith(q) and len(q) >= MIN_PREFIX_LENGTH:  # Only count meaningful prefixes
                    score += 4
            for token in desc_tokens:
                if token.startswith(q) and len(q) >= MIN_PREFIX_LENGTH:
                    score += 1

        # Boost keywords
        for word in BOOST_KEYWORDS:
            if word in name_l or word in desc_l:
                score += 3

        # Penalize low priority
        for bad in LOW_PRIORITY_KEYWORDS:
            if bad in name_l or bad in desc_l:
                score -= 10

        if name_l.endswith("-bin"):
            score += 5

        # Source priority (IMPROVED: consistent scoring)
        source_priority = {
            "pacman": 40, "apt": 40, "dnf": 40, "zypper": 40,
            "aur": 20,
            "flatpak": 10,
            "snap": 5
        }
        score += source_priority.get(source.lower(), 0)

        scored_results.append(((name, desc, source), score))

    scored_results.sort(key=lambda x: x[1], reverse=True)
    top = [pkg for pkg, score in scored_results if score > 0][:limit]
    
    logger.info(f"Found {len(top)} top matches from {len(all_packages)} total packages")
    for i, (pkg_info, score) in enumerate(scored_results[:limit]):
        logger.debug(f"Top match #{i+1}: {pkg_info[0]} (score: {score})")
    
    return top
