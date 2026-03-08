#!/usr/bin/env python3
# search_ranking.py
"""
Search result ranking and deduplication utilities.

This module contains the core ranking algorithm used by both CLI and GUI
to rank and deduplicate search results for optimal user experience.
"""

import re
from typing import List, Tuple, Optional
from archpkg.config import JUNK_KEYWORDS, LOW_PRIORITY_KEYWORDS, BOOST_KEYWORDS
from archpkg.logging_config import get_logger

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

logger = get_logger(__name__)

# Minimum length for meaningful prefix matching in scoring
MIN_PREFIX_LENGTH = 3


def _normalize_for_match(text: str) -> str:
    """Normalize text for fuzzy matching consistency."""
    return (text or "").lower().replace("_", " ").replace("-", " ").strip()


def _tokenize(text: str) -> List[str]:
    """Tokenize text into alphanumeric chunks for resilient matching."""
    return re.findall(r"[a-z0-9]+", _normalize_for_match(text))


def _acronym(tokens: List[str]) -> str:
    """Build acronym from token list (e.g., visual studio code -> vsc)."""
    return "".join(token[0] for token in tokens if token)


def _rapidfuzz_score(query: str, package_name: str, description: str) -> int:
    """Compute fuzzy relevance score using RapidFuzz (0-140)."""
    if not HAS_RAPIDFUZZ:
        return 0

    query_n = _normalize_for_match(query)
    name_n = _normalize_for_match(package_name)
    desc_n = _normalize_for_match(description)

    query_tokens = _tokenize(query_n)
    name_tokens = _tokenize(name_n)

    # Focus mostly on package name, lightly on description
    name_token = fuzz.token_set_ratio(query_n, name_n)
    name_partial = fuzz.partial_ratio(query_n, name_n)
    name_ordered = fuzz.ratio(query_n, name_n)
    desc_token = fuzz.token_set_ratio(query_n, desc_n) if desc_n else 0

    combined = (
        (name_token * 0.45) +
        (name_partial * 0.25) +
        (name_ordered * 0.20) +
        (desc_token * 0.10)
    )

    # Acronym support helps many real-world queries (e.g., vscode, k8s, nvim)
    if query_tokens and name_tokens:
        query_acr = _acronym(query_tokens)
        name_acr = _acronym(name_tokens)
        if query_acr and name_acr:
            acr_score = max(
                fuzz.ratio(query_acr, name_acr),
                fuzz.partial_ratio(query_n.replace(" ", ""), name_acr)
            )
            combined = (combined * 0.9) + (acr_score * 0.1)

    # Convert 0-100 fuzzy score into bounded rank contribution
    return int((combined / 100.0) * 120)


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
        
    query = query.lower().strip()
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return []

    # Create hyphenated and concatenated versions for better matching
    query_hyphenated = query.replace(" ", "-")
    query_concat = "".join(_tokenize(query))
    scored_results = []

    for name, desc, source in all_packages:
        if not is_valid_package(name, desc):
            continue

        name_l = name.lower()
        desc_l = (desc or "").lower()
        name_tokens = set(_tokenize(name_l))
        desc_tokens = set(_tokenize(desc_l))

        score = 0

        # Better handling of multi-word queries
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
            if any(bad in name_l for bad in LOW_PRIORITY_KEYWORDS) and not any(bad in query_tokens for bad in LOW_PRIORITY_KEYWORDS):
                score += 20
                logger.debug(f"Low-priority substring bonus for '{name}': +20")
            else:
                score += 80
                logger.debug(f"Substring match bonus for '{name}': +80")
        # Check if hyphenated query is in name
        elif query_hyphenated in name_l:
            if any(bad in name_l for bad in LOW_PRIORITY_KEYWORDS) and not any(bad in query_tokens for bad in LOW_PRIORITY_KEYWORDS):
                score += 15
                logger.debug(f"Low-priority hyphenated substring bonus for '{name}': +15")
            else:
                score += 70
                logger.debug(f"Hyphenated substring match bonus for '{name}': +70")

        # Boundary-aware boosts (prefer whole token hits over random substrings)
        if query_concat and name_l.replace("-", "").replace("_", "").startswith(query_concat):
            score += 35
        for token in query_tokens:
            if token in name_tokens:
                score += 8

        # Token matching with better weight for multi-word queries
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

            # Coverage reward across name + description for generic queries
            full_tokens = name_tokens | desc_tokens
            coverage = len(query_tokens & full_tokens) / len(query_tokens)
            score += int(coverage * 30)

        # Prefix matching for query tokens
        for q in query_tokens:
            for token in name_tokens:
                if token.startswith(q) and len(q) >= MIN_PREFIX_LENGTH:  # Only count meaningful prefixes
                    score += 4
            for token in desc_tokens:
                if token.startswith(q) and len(q) >= MIN_PREFIX_LENGTH:
                    score += 1

        # RapidFuzz semantic/fuzzy layer (handles abbreviations, typos, reordered tokens)
        fuzzy_bonus = _rapidfuzz_score(query, name_l, desc_l)
        score += fuzzy_bonus

        # Penalize missing intent tokens to reduce false positives
        full_tokens = name_tokens | desc_tokens
        missing_tokens = query_tokens - full_tokens
        if missing_tokens:
            if fuzzy_bonus >= 70:
                # High fuzzy confidence likely indicates typo/variant query
                score -= min(12, len(missing_tokens) * 6)
            elif fuzzy_bonus >= 50:
                score -= min(25, len(missing_tokens) * 10)
            else:
                score -= min(45, len(missing_tokens) * 18)
        else:
            # Strong reward when all query terms are represented
            score += 30

        # Boost keywords
        for word in BOOST_KEYWORDS:
            if word in name_l or word in desc_l:
                score += 3

        # Penalize low priority
        for bad in LOW_PRIORITY_KEYWORDS:
            if bad in name_l or bad in desc_l:
                if bad in query_tokens:
                    score -= 8
                else:
                    score -= 24

        # Extra penalty when low-priority marker is in package name itself
        if any(bad in name_l for bad in LOW_PRIORITY_KEYWORDS) and not any(bad in query_tokens for bad in LOW_PRIORITY_KEYWORDS):
            score -= 20

        # Strong demotion for wrapper/helper packages on generic single-token queries
        if len(query_tokens) == 1 and any(bad in name_l for bad in LOW_PRIORITY_KEYWORDS):
            score -= 45

        # Mild penalty for very long package names with weak lexical signal
        if len(name_l) > 28 and fuzzy_bonus < 35:
            score -= 8

        # Prefer primary packages over wrappers/variants unless explicitly requested
        variant_suffixes = ("-qt", "-gtk", "-cli", "-helper", "-theme", "-plugin", "-extension")
        if name_l.endswith(variant_suffixes):
            requested_variant = any(suffix.strip("-") in query_tokens for suffix in ["qt", "gtk", "cli", "helper", "theme", "plugin", "extension"])
            if not requested_variant:
                score -= 14

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

        # Confidence floor to filter noisy near-matches in big result sets
        if score < 25 and fuzzy_bonus < 60:
            logger.debug(f"Low-confidence match skipped: {name} (score={score}, fuzzy={fuzzy_bonus})")
            continue

        scored_results.append(((name, desc, source), score))

    scored_results.sort(key=lambda x: x[1], reverse=True)
    top = [pkg for pkg, score in scored_results][:limit]

    # Fallback for typo-heavy or sparse matches: return best available scored results
    if not top:
        fallback_scored = []
        for name, desc, source in all_packages:
            if not is_valid_package(name, desc):
                continue
            base_score = _rapidfuzz_score(query, name.lower(), (desc or "").lower())
            base_score += {
                "pacman": 25, "apt": 25, "dnf": 25, "zypper": 25,
                "aur": 12, "flatpak": 8, "snap": 5
            }.get(source.lower(), 0)
            if base_score > 20:
                fallback_scored.append(((name, desc, source), base_score))

        fallback_scored.sort(key=lambda x: x[1], reverse=True)
        top = [pkg for pkg, _ in fallback_scored[:limit]]
    
    logger.info(f"Found {len(top)} top matches from {len(all_packages)} total packages")
    for i, (pkg_info, score) in enumerate(scored_results[:limit]):
        logger.debug(f"Top match #{i+1}: {pkg_info[0]} (score: {score})")
    
    return top
