#!/usr/bin/python
# completion.py
"""Autocomplete backend for archpkg with trie-based search and smart ranking."""

import os
import json
import re
import time
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class CompletionResult:
    """Represents a completion suggestion with metadata."""
    package_name: str
    description: str
    source: str
    score: float
    alias: Optional[str] = None

class TrieNode:
    """Trie node for efficient prefix matching."""
    
    def __init__(self):
        self.children: Dict[str, 'TrieNode'] = {}
        self.packages: Set[str] = set()
        self.is_end: bool = False

class PackageTrie:
    """Trie data structure for fast package name prefix matching."""
    
    def __init__(self):
        self.root = TrieNode()
        self.package_data: Dict[str, Dict] = {}
    
    def insert(self, package_name: str, data: Dict) -> None:
        """Insert a package into the trie."""
        self.package_data[package_name] = data
        node = self.root
        for char in package_name.lower():
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
            node.packages.add(package_name)
        node.is_end = True
    
    def search_prefix(self, prefix: str) -> Set[str]:
        """Find all packages with the given prefix."""
        node = self.root
        for char in prefix.lower():
            if char not in node.children:
                return set()
            node = node.children[char]
        return node.packages.copy()
    
    def search_abbreviation(self, abbrev: str) -> Set[str]:
        """Find packages matching abbreviation (e.g., 'vsc' -> 'visual-studio-code')."""
        matches = set()
        abbrev_lower = abbrev.lower()
        
        for package_name, data in self.package_data.items():
            # Generate abbreviation from package name
            package_abbrev = self._generate_abbreviation(package_name)
            if abbrev_lower in package_abbrev or package_abbrev.startswith(abbrev_lower):
                matches.add(package_name)
        
        return matches
    
    def _generate_abbreviation(self, package_name: str) -> str:
        """Generate abbreviation from package name."""
        # Remove common separators and split into words
        words = re.split(r'[-_]', package_name.lower())
        # Take first letter of each word
        return ''.join(word[0] for word in words if word)

class CompletionBackend:
    """Main completion backend with smart ranking and caching."""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize the completion backend."""
        self.cache_dir = cache_dir or os.path.expanduser("~/.cache/archpkg")
        self.trie = PackageTrie()
        self.alias_map: Dict[str, str] = {}
        self.frequency_cache: Dict[str, int] = {}
        self.recent_packages: List[str] = []
        self.max_recent = 50
        
        # Load data
        self._load_alias_mappings()
        self._load_frequency_cache()
        self._load_package_data()
    
    def _load_alias_mappings(self) -> None:
        """Load alias mappings for common package names."""
        self.alias_map = {
            # VS Code aliases
            'vscode': 'visual-studio-code',
            'code': 'visual-studio-code',
            'vsc': 'visual-studio-code',
            
            # Browser aliases
            'chrome': 'google-chrome',
            'ff': 'firefox',
            'brave': 'brave-bin',
            
            # Development tools
            'vim': 'gvim',
            'nvim': 'neovim',
            'node': 'nodejs',
            'npm': 'nodejs-npm',
            'yarn': 'yarn',
            
            # Media players
            'vlc': 'vlc',
            'mpv': 'mpv',
            
            # Office suites
            'libre': 'libreoffice-fresh',
            'office': 'libreoffice-fresh',
            'word': 'libreoffice-fresh',
            'excel': 'libreoffice-fresh',
            
            # Graphics
            'gimp': 'gimp',
            'photoshop': 'gimp',
            'inkscape': 'inkscape',
            'illustrator': 'inkscape',
            
            # Gaming
            'steam': 'steam',
            'wine': 'wine',
            
            # System tools
            'htop': 'htop',
            'top': 'htop',
            'neofetch': 'neofetch',
            'fetch': 'neofetch',
            
            # Communication
            'discord': 'discord',
            'telegram': 'telegram-desktop',
            'signal': 'signal-desktop',
            'slack': 'slack-desktop',
            'zoom': 'zoom',
            'teams': 'teams',
            
            # Music
            'spotify': 'spotify',
            'audacity': 'audacity',
            'music': 'vlc',
            
            # Video editing
            'kdenlive': 'kdenlive',
            'shotcut': 'shotcut',
            'openshot': 'openshot',
            'obs': 'obs-studio',
            'obs-studio': 'obs-studio',
            
            # Text editors
            'nano': 'nano',
            'emacs': 'emacs',
            'sublime': 'sublime-text',
            'atom': 'atom',
            
            # Utilities
            'curl': 'curl',
            'wget': 'wget',
            'git': 'git',
            'docker': 'docker',
            'python': 'python',
            'pip': 'python-pip',
        }
        
        logger.info(f"Loaded {len(self.alias_map)} alias mappings")
    
    def _load_frequency_cache(self) -> None:
        """Load frequency cache from disk."""
        cache_file = os.path.join(self.cache_dir, 'frequency_cache.json')
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    self.frequency_cache = json.load(f)
                logger.info(f"Loaded frequency cache with {len(self.frequency_cache)} entries")
        except Exception as e:
            logger.warning(f"Failed to load frequency cache: {e}")
            self.frequency_cache = {}
    
    def _save_frequency_cache(self) -> None:
        """Save frequency cache to disk."""
        os.makedirs(self.cache_dir, exist_ok=True)
        cache_file = os.path.join(self.cache_dir, 'frequency_cache.json')
        try:
            with open(cache_file, 'w') as f:
                json.dump(self.frequency_cache, f)
        except Exception as e:
            logger.warning(f"Failed to save frequency cache: {e}")
    
    def _load_package_data(self) -> None:
        """Load package data from various sources."""
        # This would typically load from package managers, but for now
        # we'll use a comprehensive static list based on the purpose mapping
        package_data = self._get_static_package_data()
        
        for package_name, data in package_data.items():
            self.trie.insert(package_name, data)
        
        logger.info(f"Loaded {len(package_data)} packages into trie")
    
    def _get_static_package_data(self) -> Dict[str, Dict]:
        """Get static package data for completion."""
        return {
            # Video editing
            'kdenlive': {'description': 'Professional video editor', 'source': 'pacman'},
            'shotcut': {'description': 'Free, open-source video editor', 'source': 'pacman'},
            'openshot': {'description': 'Simple video editor', 'source': 'pacman'},
            'obs-studio': {'description': 'Live streaming and recording software', 'source': 'pacman'},
            'davinci-resolve': {'description': 'Professional video editing software', 'source': 'aur'},
            'blender': {'description': '3D creation suite', 'source': 'pacman'},
            
            # Office
            'libreoffice-fresh': {'description': 'Complete office suite', 'source': 'pacman'},
            'onlyoffice-bin': {'description': 'Office suite with online collaboration', 'source': 'aur'},
            'wps-office': {'description': 'WPS Office suite', 'source': 'aur'},
            'calligra': {'description': 'KDE office suite', 'source': 'pacman'},
            
            # Music
            'audacity': {'description': 'Audio editor and recorder', 'source': 'pacman'},
            'vlc': {'description': 'Media player', 'source': 'pacman'},
            'lmms': {'description': 'Digital audio workstation', 'source': 'pacman'},
            'ardour': {'description': 'Digital audio workstation', 'source': 'pacman'},
            'reaper': {'description': 'Digital audio workstation', 'source': 'aur'},
            'musescore': {'description': 'Music notation software', 'source': 'pacman'},
            'spotify': {'description': 'Music streaming service', 'source': 'aur'},
            
            # Coding
            'visual-studio-code': {'description': 'Code editor by Microsoft', 'source': 'aur'},
            'vscode': {'description': 'Code editor by Microsoft', 'source': 'aur'},
            'neovim': {'description': 'Vim-based text editor', 'source': 'pacman'},
            'intellij-idea-community': {'description': 'Java IDE', 'source': 'pacman'},
            'android-studio': {'description': 'Android development IDE', 'source': 'aur'},
            'sublime-text': {'description': 'Text editor', 'source': 'aur'},
            'atom': {'description': 'Text editor', 'source': 'aur'},
            'codeblocks': {'description': 'C/C++ IDE', 'source': 'pacman'},
            'qtcreator': {'description': 'Qt development IDE', 'source': 'pacman'},
            
            # Graphics
            'gimp': {'description': 'Image editor', 'source': 'pacman'},
            'inkscape': {'description': 'Vector graphics editor', 'source': 'pacman'},
            'krita': {'description': 'Digital painting application', 'source': 'pacman'},
            'darktable': {'description': 'Photo workflow application', 'source': 'pacman'},
            'rawtherapee': {'description': 'Raw photo processor', 'source': 'pacman'},
            
            # Gaming
            'steam': {'description': 'Gaming platform', 'source': 'pacman'},
            'lutris': {'description': 'Gaming platform', 'source': 'pacman'},
            'wine': {'description': 'Windows compatibility layer', 'source': 'pacman'},
            'playonlinux': {'description': 'Wine frontend', 'source': 'pacman'},
            'retroarch': {'description': 'Retro gaming emulator', 'source': 'pacman'},
            
            # Browsing
            'firefox': {'description': 'Web browser', 'source': 'pacman'},
            'chromium': {'description': 'Web browser', 'source': 'pacman'},
            'google-chrome': {'description': 'Web browser', 'source': 'aur'},
            'brave-bin': {'description': 'Privacy-focused browser', 'source': 'aur'},
            'vivaldi': {'description': 'Web browser', 'source': 'aur'},
            'opera': {'description': 'Web browser', 'source': 'aur'},
            
            # Communication
            'discord': {'description': 'Voice and text chat', 'source': 'aur'},
            'telegram-desktop': {'description': 'Messaging app', 'source': 'pacman'},
            'signal-desktop': {'description': 'Secure messaging', 'source': 'aur'},
            'slack-desktop': {'description': 'Team communication', 'source': 'aur'},
            'zoom': {'description': 'Video conferencing', 'source': 'aur'},
            'teams': {'description': 'Microsoft Teams', 'source': 'aur'},
            
            # Development
            'git': {'description': 'Version control system', 'source': 'pacman'},
            'docker': {'description': 'Container platform', 'source': 'pacman'},
            'docker-compose': {'description': 'Docker orchestration', 'source': 'pacman'},
            'nodejs': {'description': 'JavaScript runtime', 'source': 'pacman'},
            'python': {'description': 'Python interpreter', 'source': 'pacman'},
            'go': {'description': 'Go programming language', 'source': 'pacman'},
            'rust': {'description': 'Rust programming language', 'source': 'pacman'},
            'clang': {'description': 'C/C++ compiler', 'source': 'pacman'},
            'gcc': {'description': 'GNU compiler collection', 'source': 'pacman'},
            
            # System
            'htop': {'description': 'Interactive process viewer', 'source': 'pacman'},
            'neofetch': {'description': 'System information tool', 'source': 'pacman'},
            'timeshift': {'description': 'System restore tool', 'source': 'aur'},
            'gparted': {'description': 'Disk partitioning tool', 'source': 'pacman'},
            'gnome-disk-utility': {'description': 'Disk utility', 'source': 'pacman'},
            'system-monitor': {'description': 'System monitor', 'source': 'pacman'},
            
            # Text editing
            'vim': {'description': 'Text editor', 'source': 'pacman'},
            'emacs': {'description': 'Text editor', 'source': 'pacman'},
            'nano': {'description': 'Text editor', 'source': 'pacman'},
            'micro': {'description': 'Text editor', 'source': 'pacman'},
            'kate': {'description': 'Text editor', 'source': 'pacman'},
            'gedit': {'description': 'Text editor', 'source': 'pacman'},
            
            # Media
            'mpv': {'description': 'Media player', 'source': 'pacman'},
            'smplayer': {'description': 'Media player', 'source': 'pacman'},
            'rhythmbox': {'description': 'Music player', 'source': 'pacman'},
            'youtube-dl': {'description': 'Video downloader', 'source': 'pacman'},
            
            # Utilities
            'curl': {'description': 'Data transfer tool', 'source': 'pacman'},
            'wget': {'description': 'File downloader', 'source': 'pacman'},
            'unzip': {'description': 'Archive extractor', 'source': 'pacman'},
            'zip': {'description': 'Archive creator', 'source': 'pacman'},
            'tar': {'description': 'Archive tool', 'source': 'pacman'},
            'rsync': {'description': 'File synchronization', 'source': 'pacman'},
            'tree': {'description': 'Directory tree viewer', 'source': 'pacman'},
            'bat': {'description': 'Cat clone with syntax highlighting', 'source': 'pacman'},
            'exa': {'description': 'Modern ls replacement', 'source': 'pacman'},
        }
    
    def get_completions(self, query: str, context: str = "install", limit: int = 10) -> List[CompletionResult]:
        """Get completion suggestions for the given query."""
        if not query.strip():
            return []
        
        query = query.strip().lower()
        logger.debug(f"Getting completions for query: '{query}' in context: '{context}'")
        
        # Check for alias matches first
        if query in self.alias_map:
            canonical_name = self.alias_map[query]
            if canonical_name in self.trie.package_data:
                data = self.trie.package_data[canonical_name]
                return [CompletionResult(
                    package_name=canonical_name,
                    description=data['description'],
                    source=data['source'],
                    score=100.0,
                    alias=query
                )]
        
        # Get prefix matches
        prefix_matches = self.trie.search_prefix(query)
        
        # Get abbreviation matches
        abbrev_matches = self.trie.search_abbreviation(query)
        
        # Combine and deduplicate
        all_matches = prefix_matches.union(abbrev_matches)
        
        if not all_matches:
            return []
        
        # Score and rank matches
        results = []
        for package_name in all_matches:
            data = self.trie.package_data[package_name]
            score = self._calculate_score(query, package_name, data, context)
            
            results.append(CompletionResult(
                package_name=package_name,
                description=data['description'],
                source=data['source'],
                score=score
            ))
        
        # Sort by score (descending) and limit results
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]
    
    def _calculate_score(self, query: str, package_name: str, data: Dict, context: str) -> float:
        """Calculate relevance score for a package match."""
        score = 0.0
        query_lower = query.lower()
        package_lower = package_name.lower()
        description_lower = data.get('description', '').lower()
        
        # Exact match bonus
        if query_lower == package_lower:
            score += 100.0
        elif package_lower.startswith(query_lower):
            score += 80.0
        elif query_lower in package_lower:
            score += 60.0
        
        # Abbreviation match
        package_abbrev = self.trie._generate_abbreviation(package_name)
        if query_lower in package_abbrev or package_abbrev.startswith(query_lower):
            score += 70.0
        
        # Description match
        if query_lower in description_lower:
            score += 20.0
        
        # Word boundary matches
        query_words = set(query_lower.split())
        package_words = set(re.split(r'[-_]', package_lower))
        description_words = set(description_lower.split())
        
        for word in query_words:
            for pkg_word in package_words:
                if pkg_word.startswith(word):
                    score += 10.0
            for desc_word in description_words:
                if desc_word.startswith(word):
                    score += 5.0
        
        # Frequency bonus
        frequency = self.frequency_cache.get(package_name, 0)
        score += min(frequency * 2, 20.0)  # Cap at 20 points
        
        # Recent usage bonus
        if package_name in self.recent_packages:
            recent_index = self.recent_packages.index(package_name)
            score += max(10.0 - recent_index, 0.0)
        
        # Source priority
        source_priority = {
            'pacman': 10.0,
            'aur': 8.0,
            'flatpak': 6.0,
            'snap': 4.0,
            'apt': 5.0,
            'dnf': 5.0
        }
        score += source_priority.get(data.get('source', ''), 0.0)
        
        # Context-aware scoring
        if context == "remove" and package_name in self.recent_packages:
            score += 15.0  # Boost recently used packages for removal
        
        return score
    
    def record_usage(self, package_name: str) -> None:
        """Record package usage for frequency tracking."""
        # Update frequency cache
        self.frequency_cache[package_name] = self.frequency_cache.get(package_name, 0) + 1
        
        # Update recent packages list
        if package_name in self.recent_packages:
            self.recent_packages.remove(package_name)
        self.recent_packages.insert(0, package_name)
        
        # Keep only recent packages
        if len(self.recent_packages) > self.max_recent:
            self.recent_packages = self.recent_packages[:self.max_recent]
        
        # Save frequency cache periodically
        if len(self.frequency_cache) % 10 == 0:
            self._save_frequency_cache()
    
    def get_completion_text(self, query: str, context: str = "install", limit: int = 10) -> str:
        """Get completion suggestions as newline-separated text for shell integration."""
        completions = self.get_completions(query, context, limit)
        return '\n'.join(comp.package_name for comp in completions)

# Global completion backend instance
_completion_backend = None

def get_completion_backend() -> CompletionBackend:
    """Get the global completion backend instance."""
    global _completion_backend
    if _completion_backend is None:
        _completion_backend = CompletionBackend()
    return _completion_backend

def complete_packages(query: str, context: str = "install", limit: int = 10) -> str:
    """Convenience function for shell integration."""
    backend = get_completion_backend()
    return backend.get_completion_text(query, context, limit)
