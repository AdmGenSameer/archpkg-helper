#!/usr/bin/python
# suggest.py
"""Smart hybrid purpose-based app suggestions module for archpkg."""

import re
from typing import List, Dict, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import logging

console = Console()
logger = logging.getLogger(__name__)

class PurposeSuggester:
    """Handles smart hybrid purpose-based app suggestions."""
    
    # Configuration constants
    MAX_SEARCH_TERMS = 3  # Limit search terms to avoid excessive API calls
    LIBRARY_KEYWORDS = ['lib', '-dev', '-devel', 'headers', 'sdk', 'api']
    SOURCE_PRIORITY = {
        'pacman': 3, 'apt': 3, 'dnf': 3, 'zypper': 3,
        'aur': 2,
        'flatpak': 1,
        'snap': 0
    }
    DESCRIPTION_MAX_LENGTH = 60
    DESCRIPTION_TRUNCATE_AT = 57
    
    def __init__(self):
        """Initialize the suggester with intent patterns and mappings."""
        self.intent_patterns = self._init_intent_patterns()
        self.intent_search_terms = self._init_intent_search_terms()
        self.popular_apps = self._init_popular_apps()
        
    def _init_intent_patterns(self) -> List[Tuple[re.Pattern, str]]:
        """Initialize regex patterns for intent extraction.
        
        Returns:
            List of (pattern, intent) tuples
        """
        patterns = [
            # Video editing
            (re.compile(r'\b(edit|editing|cut|trim|produce|production)\b.*\b(video|videos|movie|movies|film)\b', re.IGNORECASE), 'video-editor'),
            (re.compile(r'\bvideo\b.*\b(edit|editing|editor|cut|trim)\b', re.IGNORECASE), 'video-editor'),
            (re.compile(r'\b(kdenlive|shotcut|openshot|davinci)\b', re.IGNORECASE), 'video-editor'),
            
            # Code/Programming
            (re.compile(r'\b(code|coding|program|programming|develop|development|IDE)\b', re.IGNORECASE), 'code-editor'),
            (re.compile(r'\b(vscode|vim|neovim|emacs|sublime|atom|intellij)\b', re.IGNORECASE), 'code-editor'),
            (re.compile(r'\btext\b.*\beditor\b', re.IGNORECASE), 'text-editor'),
            
            # Image/Graphics editing
            (re.compile(r'\b(photoshop|gimp|krita)\b', re.IGNORECASE), 'image-editor'),
            (re.compile(r'\b(edit|editing)\b.*\b(image|images|photo|photos|picture)\b', re.IGNORECASE), 'image-editor'),
            (re.compile(r'\b(image|photo|picture)\b.*\b(edit|editing|editor)\b', re.IGNORECASE), 'image-editor'),
            (re.compile(r'\b(graphic|graphics|design|drawing|paint)\b', re.IGNORECASE), 'image-editor'),
            
            # Office/Productivity
            (re.compile(r'\b(office|word|excel|powerpoint|spreadsheet|document|presentation)\b', re.IGNORECASE), 'office'),
            (re.compile(r'\b(libreoffice|onlyoffice|openoffice)\b', re.IGNORECASE), 'office'),
            (re.compile(r'\bproductivity\b', re.IGNORECASE), 'office'),
            
            # Web browsing
            (re.compile(r'\b(browser|browsing|web|internet|surf)\b', re.IGNORECASE), 'web-browser'),
            (re.compile(r'\b(firefox|chrome|chromium|brave|vivaldi)\b', re.IGNORECASE), 'web-browser'),
            
            # Music/Audio
            (re.compile(r'\b(music|audio|sound)\b.*\b(player|play|listen)\b', re.IGNORECASE), 'music-player'),
            (re.compile(r'\b(music|audio)\b.*\b(edit|editing|editor|produce|production)\b', re.IGNORECASE), 'audio-editor'),
            (re.compile(r'\b(spotify|rhythmbox|audacity|ardour)\b', re.IGNORECASE), 'music-player'),
            
            # Gaming
            (re.compile(r'\b(game|games|gaming|play)\b', re.IGNORECASE), 'gaming'),
            (re.compile(r'\b(steam|lutris|wine)\b', re.IGNORECASE), 'gaming'),
            
            # Communication
            (re.compile(r'\b(chat|messaging|voice|video.*call|communicate)\b', re.IGNORECASE), 'communication'),
            (re.compile(r'\b(discord|telegram|signal|slack|teams|zoom)\b', re.IGNORECASE), 'communication'),
            
            # Media player
            (re.compile(r'\b(media|video|movie)\b.*\bplayer\b', re.IGNORECASE), 'media-player'),
            (re.compile(r'\b(vlc|mpv)\b', re.IGNORECASE), 'media-player'),
            
            # System utilities
            (re.compile(r'\b(system|monitor|utility|utilities|tool|tools)\b', re.IGNORECASE), 'system-utility'),
        ]
        
        return patterns
    
    def _init_intent_search_terms(self) -> Dict[str, List[str]]:
        """Initialize mapping from intents to search terms.
        
        Returns:
            Dict mapping intent names to lists of search terms
        """
        return {
            'video-editor': ['video editor', 'kdenlive', 'shotcut', 'openshot', 'davinci resolve', 'obs studio', 'video editing'],
            'code-editor': ['code editor', 'vscode', 'vim', 'neovim', 'sublime text', 'atom', 'ide', 'intellij'],
            'image-editor': ['image editor', 'gimp', 'krita', 'inkscape', 'photo editor', 'graphics editor', 'darktable'],
            'text-editor': ['text editor', 'vim', 'emacs', 'nano', 'gedit', 'kate'],
            'office': ['libreoffice', 'onlyoffice', 'office suite', 'calligra', 'document editor'],
            'web-browser': ['firefox', 'chromium', 'brave', 'vivaldi', 'web browser', 'browser'],
            'music-player': ['music player', 'spotify', 'rhythmbox', 'vlc', 'clementine', 'audio player'],
            'audio-editor': ['audio editor', 'audacity', 'ardour', 'lmms', 'sound editor'],
            'gaming': ['steam', 'lutris', 'wine', 'playonlinux', 'gaming', 'game'],
            'communication': ['discord', 'telegram', 'signal', 'slack', 'teams', 'zoom', 'chat', 'messenger'],
            'media-player': ['vlc', 'mpv', 'media player', 'video player', 'smplayer'],
            'system-utility': ['htop', 'system monitor', 'gparted', 'timeshift', 'disk utility'],
        }
    
    def _init_popular_apps(self) -> Dict[str, List[str]]:
        """Initialize popular apps for each intent.
        
        Returns:
            Dict mapping intent names to lists of popular app names
        """
        return {
            'video-editor': ['kdenlive', 'shotcut', 'openshot', 'obs-studio', 'obs studio', 'davinci-resolve'],
            'code-editor': ['vscode', 'code', 'visual studio code', 'neovim', 'vim', 'sublime-text', 'intellij'],
            'image-editor': ['gimp', 'krita', 'inkscape', 'darktable', 'rawtherapee'],
            'text-editor': ['vim', 'neovim', 'emacs', 'nano', 'gedit', 'kate', 'micro'],
            'office': ['libreoffice', 'libreoffice-fresh', 'onlyoffice', 'calligra'],
            'web-browser': ['firefox', 'chromium', 'brave', 'brave-bin', 'vivaldi', 'opera'],
            'music-player': ['spotify', 'rhythmbox', 'vlc', 'clementine', 'deadbeef'],
            'audio-editor': ['audacity', 'ardour', 'lmms', 'reaper'],
            'gaming': ['steam', 'lutris', 'wine', 'playonlinux', 'retroarch'],
            'communication': ['discord', 'telegram-desktop', 'signal-desktop', 'slack', 'zoom', 'teams'],
            'media-player': ['vlc', 'mpv', 'smplayer', 'celluloid'],
            'system-utility': ['htop', 'btop', 'neofetch', 'gparted', 'timeshift', 'gnome-disk-utility'],
        }
    
    def extract_intent(self, query: str) -> Optional[str]:
        """Extract intent from user query using regex patterns.
        
        Args:
            query: User input query
            
        Returns:
            Detected intent name or None
        """
        query_lower = query.lower().strip()
        
        # Try to match patterns
        for pattern, intent in self.intent_patterns:
            if pattern.search(query_lower):
                logger.info(f"Detected intent '{intent}' from query '{query}'")
                return intent
        
        logger.info(f"No specific intent detected from query '{query}'")
        return None
    
    def search_packages(self, search_terms: List[str]) -> List[Tuple[str, str, str]]:
        """Search for packages using multiple search terms.
        
        Args:
            search_terms: List of search terms to query
            
        Returns:
            List of (name, description, source) tuples
        """
        from archpkg.search_pacman import search_pacman
        from archpkg.search_aur import search_aur
        from archpkg.search_flatpak import search_flatpak
        from archpkg.search_snap import search_snap
        from archpkg.search_apt import search_apt
        from archpkg.search_dnf import search_dnf
        from archpkg.search_zypper import search_zypper
        from archpkg.exceptions import PackageManagerNotFound, PackageSearchException
        import distro
        
        all_results = []
        detected_distro = distro.id().lower().strip()
        
        # Determine which native package managers to use
        native_searches = []
        if detected_distro in ['arch', 'manjaro', 'endeavouros', 'garuda']:
            native_searches = [
                ('pacman', search_pacman),
                ('aur', search_aur),
            ]
        elif detected_distro in ['ubuntu', 'debian', 'mint', 'pop', 'elementary']:
            native_searches = [('apt', search_apt)]
        elif detected_distro in ['fedora', 'rhel', 'centos', 'rocky', 'almalinux']:
            native_searches = [('dnf', search_dnf)]
        elif detected_distro in ['opensuse', 'opensuse-leap', 'opensuse-tumbleweed', 'suse', 'sles']:
            native_searches = [('zypper', search_zypper)]
        
        # Universal package managers
        universal_searches = [
            ('flatpak', search_flatpak),
            ('snap', search_snap),
        ]
        
        # Search with each term (limited to avoid excessive API calls)
        for term in search_terms[:self.MAX_SEARCH_TERMS]:
            logger.debug(f"Searching for term: '{term}'")
            
            # Search native package managers
            for source_name, search_func in native_searches:
                try:
                    # No cache for suggestions - they're exploratory queries with varied terms
                    results = search_func(term, None)
                    all_results.extend(results)
                    logger.debug(f"Found {len(results)} results from {source_name} for '{term}'")
                except (PackageManagerNotFound, PackageSearchException) as e:
                    logger.debug(f"{source_name} search failed for '{term}': {e}")
                except Exception as e:
                    logger.debug(f"Unexpected error in {source_name} search for '{term}': {e}")
            
            # Search universal package managers
            for source_name, search_func in universal_searches:
                try:
                    # No cache for suggestions - they're exploratory queries with varied terms
                    results = search_func(term, None)
                    all_results.extend(results)
                    logger.debug(f"Found {len(results)} results from {source_name} for '{term}'")
                except (PackageManagerNotFound, PackageSearchException) as e:
                    logger.debug(f"{source_name} search failed for '{term}': {e}")
                except Exception as e:
                    logger.debug(f"Unexpected error in {source_name} search for '{term}': {e}")
        
        return all_results
    
    def rank_packages(self, packages: List[Tuple[str, str, str]], intent: Optional[str], query: str) -> List[Tuple[str, str, str, int]]:
        """Rank packages by relevance with smart scoring.
        
        Args:
            packages: List of (name, description, source) tuples
            intent: Detected intent
            query: Original query
            
        Returns:
            List of (name, description, source, score) tuples, sorted by score
        """
        scored = []
        query_lower = query.lower()
        popular = self.popular_apps.get(intent, []) if intent else []
        
        # Deduplicate packages by name
        seen_names = {}
        for name, desc, source in packages:
            name_lower = name.lower()
            if name_lower not in seen_names:
                seen_names[name_lower] = (name, desc, source)
            else:
                # Prefer packages from certain sources based on priority
                _, _, existing_source = seen_names[name_lower]
                if self.SOURCE_PRIORITY.get(source, 0) > self.SOURCE_PRIORITY.get(existing_source, 0):
                    seen_names[name_lower] = (name, desc, source)
        
        # Score each unique package
        for name, desc, source in seen_names.values():
            name_lower = name.lower()
            desc_lower = (desc or '').lower()
            score = 0
            
            # Popular app bonus
            if intent and any(pop.lower() in name_lower for pop in popular):
                score += 40
                logger.debug(f"Popular app bonus for '{name}': +40")
            
            # Name match with query or intent
            if query_lower in name_lower:
                score += 50
                logger.debug(f"Name match bonus for '{name}': +50")
            elif intent and intent.replace('-', ' ') in name_lower:
                score += 30
                logger.debug(f"Intent match bonus for '{name}': +30")
            
            # Query words in name or description
            query_words = set(query_lower.split())
            name_words = set(name_lower.replace('-', ' ').split())
            desc_words = set(desc_lower.split())
            
            word_matches = len(query_words & name_words)
            if word_matches > 0:
                score += word_matches * 10
                logger.debug(f"Word match bonus for '{name}': +{word_matches * 10}")
            
            desc_matches = len(query_words & desc_words)
            if desc_matches > 0:
                score += desc_matches * 5
                logger.debug(f"Description match bonus for '{name}': +{desc_matches * 5}")
            
            # Official repo bonus
            if source in ['pacman', 'apt', 'dnf', 'zypper']:
                score += 20
                logger.debug(f"Official repo bonus for '{name}': +20")
            
            # Penalize likely libraries/development packages
            if any(kw in name_lower for kw in self.LIBRARY_KEYWORDS):
                score -= 30
                logger.debug(f"Library penalty for '{name}': -30")
            
            # Bonus for desktop applications (common app suffixes)
            if any(name_lower.endswith(suffix) for suffix in ['-desktop', '-app', '-gtk', '-qt']):
                score += 10
                logger.debug(f"Desktop app bonus for '{name}': +10")
            
            scored.append((name, desc, source, score))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[3], reverse=True)
        
        return scored
    
    def suggest_apps(self, query: str, max_results: int = 10) -> List[Tuple[str, str, str, int]]:
        """Get app suggestions for a given purpose query using smart hybrid approach.
        
        Args:
            query: User purpose query
            max_results: Maximum number of apps to return
            
        Returns:
            List of (name, description, source, score) tuples
        """
        # Extract intent
        intent = self.extract_intent(query)
        
        # Get search terms
        if intent and intent in self.intent_search_terms:
            search_terms = self.intent_search_terms[intent]
            logger.info(f"Using search terms for intent '{intent}': {search_terms[:3]}")
        else:
            # Fallback to using query as search term
            search_terms = [query]
            logger.info(f"No specific intent, using query as search term: '{query}'")
        
        # Search packages
        packages = self.search_packages(search_terms)
        logger.info(f"Found {len(packages)} total packages")
        
        if not packages:
            return []
        
        # Rank packages
        ranked = self.rank_packages(packages, intent, query)
        
        return ranked[:max_results]
    
    def display_suggestions(self, query: str, max_results: int = 10) -> bool:
        """Display app suggestions in a formatted table with smart hybrid approach.
        
        Args:
            query: User purpose query
            max_results: Maximum number of suggestions to display
            
        Returns:
            True if suggestions were found and displayed, False otherwise
        """
        # Show understanding message
        intent = self.extract_intent(query)
        if intent:
            intent_display = intent.replace('-', ' ').title()
            console.print(Panel(
                f"🔍 Understanding: [cyan]'{query}'[/cyan]\n"
                f"Detected intent: [bold green]{intent_display}[/bold green]",
                border_style="blue"
            ))
        else:
            console.print(Panel(
                f"🔍 Searching for: [cyan]'{query}'[/cyan]",
                border_style="blue"
            ))
        
        console.print()
        
        suggestions = self.suggest_apps(query, max_results)
        
        if not suggestions:
            console.print(Panel(
                f"[yellow]No suggestions found for '{query}'.[/yellow]\n\n"
                "[bold cyan]Try these examples:[/bold cyan]\n"
                "- [cyan]archpkg suggest I want to edit videos[/cyan]\n"
                "- [cyan]archpkg suggest something like photoshop[/cyan]\n"
                "- [cyan]archpkg suggest IDE for python[/cyan]\n"
                "- [cyan]archpkg suggest office apps[/cyan]\n"
                "- [cyan]archpkg suggest web browser[/cyan]",
                title="No Suggestions Found",
                border_style="yellow"
            ))
            return False
        
        # Display results in a table
        table = Table(title="📦 Suggested Apps")
        table.add_column("#", style="cyan", no_wrap=True, width=3)
        table.add_column("Package", style="green", no_wrap=True)
        table.add_column("Source", style="blue", no_wrap=True, width=8)
        table.add_column("Description", style="magenta")
        
        for idx, (name, desc, source, score) in enumerate(suggestions, 1):
            # Truncate description if too long
            display_desc = desc if desc else "No description"
            if len(display_desc) > self.DESCRIPTION_MAX_LENGTH:
                display_desc = display_desc[:self.DESCRIPTION_TRUNCATE_AT] + "..."
            
            table.add_row(str(idx), name, source, display_desc)
        
        console.print(table)
        console.print()
        
        return True
    
    def list_available_intents(self) -> None:
        """Display all available intents and their search terms."""
        table = Table(title="Available Intents")
        table.add_column("Intent", style="green")
        table.add_column("Example Queries", style="cyan")
        table.add_column("Search Terms", style="magenta")
        
        intent_examples = {
            'video-editor': 'edit videos, video editor',
            'code-editor': 'code editor, IDE for python',
            'image-editor': 'something like photoshop, image editor',
            'text-editor': 'text editor',
            'office': 'office apps, productivity',
            'web-browser': 'web browser, browser',
            'music-player': 'music player',
            'audio-editor': 'audio editor, edit sound',
            'gaming': 'gaming, play games',
            'communication': 'chat, messaging',
            'media-player': 'video player, media player',
            'system-utility': 'system tools, utilities',
        }
        
        for intent, search_terms in self.intent_search_terms.items():
            examples = intent_examples.get(intent, intent)
            terms = ", ".join(search_terms[:3])
            if len(search_terms) > 3:
                terms += "..."
            table.add_row(intent.replace('-', ' ').title(), examples, terms)
        
        console.print(table)
        console.print()
        console.print("[bold cyan]Tip:[/bold cyan] You can use natural language like:")
        console.print("  • [cyan]archpkg suggest I want to edit videos[/cyan]")
        console.print("  • [cyan]archpkg suggest something like photoshop[/cyan]")
        console.print("  • [cyan]archpkg suggest IDE for python[/cyan]")


def suggest_apps(query: str) -> bool:
    """Convenience function to suggest apps for a given purpose.
    
    Args:
        query: User purpose query
        
    Returns:
        True if suggestions were found and displayed, False otherwise
    """
    suggester = PurposeSuggester()
    return suggester.display_suggestions(query)


def list_purposes() -> None:
    """Convenience function to list all available intents."""
    suggester = PurposeSuggester()
    suggester.list_available_intents()
