#!/usr/bin/env python3
# gui.py
"""Native desktop GUI for Arjax using PyQt5.

A professional, cross-distro package manager interface with search,
install, remove, and system maintenance capabilities.
"""

import sys
import subprocess
import threading
import shutil
import webbrowser
from typing import List, Tuple, Optional, Dict
from pathlib import Path

try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QLabel,
        QComboBox, QTabWidget, QTextEdit, QProgressBar, QMessageBox,
        QHeaderView, QStatusBar, QGroupBox, QCheckBox, QSpinBox,
        QListWidget, QListWidgetItem, QSplitter, QFrame
    )
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt5.QtGui import QFont, QPalette, QColor, QIcon
except ImportError:
    print("PyQt5 is required for the GUI.")
    print("Install with: pip install PyQt5")
    sys.exit(1)

import distro
from arjax.config.base import DISTRO_MAP
from arjax.search.pacman import search_pacman
from arjax.search.aur import search_aur, get_aur_package_details
from arjax.search.apt import search_apt
from arjax.search.dnf import search_dnf
from arjax.search.zypper import search_zypper
from arjax.search.flatpak import search_flatpak
from arjax.search.snap import search_snap
from arjax.package_management.command_gen import generate_command
from arjax.config.manager import get_user_config, save_user_config, set_config_option
from arjax.intelligence.advisor import assess_aur_trust, get_arch_news, apply_user_mode_defaults
from arjax.integrations.github import install_from_github, validate_github_url
from arjax.config.logging import get_logger
from arjax.search.ranking import deduplicate_packages, get_top_matches

logger = get_logger(__name__)

SEARCH_SOURCES = ["pacman", "aur", "apt", "dnf", "zypper", "flatpak", "snap", "github"]
SOURCE_COMMANDS = {
    "pacman": ["paru", "pacman"],
    "aur": [],
    "apt": ["apt-cache"],
    "dnf": ["dnf"],
    "zypper": ["zypper"],
    "flatpak": ["flatpak"],
    "snap": ["snap"],
    "github": [],
}


class SearchWorker(QThread):
    """Background worker for package searches."""
    
    results_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, query: str, detected_distro: str, distro_family: str, sources: List[str]):
        super().__init__()
        self.query = query
        self.detected_distro = detected_distro
        self.distro_family = distro_family
        self.sources = sources
    
    def run(self):
        """Execute search in background thread."""
        try:
            results = []
            
            for source in self.sources:
                try:
                    if source == 'pacman':
                        pkg_list = search_pacman(self.query)
                        results.extend(pkg_list)
                    elif source == 'aur':
                        pkg_list = search_aur(self.query)
                        results.extend(pkg_list)
                    elif source == 'apt':
                        pkg_list = search_apt(self.query)
                        results.extend(pkg_list)
                    elif source == 'dnf':
                        pkg_list = search_dnf(self.query)
                        results.extend(pkg_list)
                    elif source == 'zypper':
                        pkg_list = search_zypper(self.query)
                        results.extend(pkg_list)
                    elif source == 'flatpak':
                        pkg_list = search_flatpak(self.query)
                        results.extend(pkg_list)
                    elif source == 'snap':
                        pkg_list = search_snap(self.query)
                        results.extend(pkg_list)
                except Exception as e:
                    logger.error(f"Error searching {source}: {e}")
            
            # Apply ranking and deduplication for better search results
            if results:
                # Deduplicate results (prefer pacman over AUR for duplicates)
                results = deduplicate_packages(results, prefer_aur=False)
                logger.info(f"Deduplicated to {len(results)} unique packages")
                
                # Rank results by relevance using sophisticated scoring algorithm
                # Show top 50 most relevant results instead of all results
                results = get_top_matches(self.query, results, limit=50)
                logger.info(f"Ranked and limited to top {len(results)} matches")
            
            self.results_ready.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))


class InstallWorker(QThread):
    """Background worker for package installation."""
    
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)
    
    def __init__(self, package_name: str, source: str):
        super().__init__()
        self.package_name = package_name
        self.source = source
    
    def run(self):
        """Execute installation in background thread."""
        try:
            self.progress.emit(f"Generating install command for {self.package_name}...")
            
            command = generate_command(self.package_name, self.source)
            if not command:
                self.finished.emit(False, f"Could not generate install command for {self.package_name}")
                return
            
            self.progress.emit(f"Executing: {command}")
            
            # Run installation command
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            output_lines = []
            if process.stdout:
                for line in process.stdout:
                    output_lines.append(line.strip())
                    self.progress.emit(line.strip())
            
            process.wait()
            
            if process.returncode == 0:
                self.finished.emit(True, f"Successfully installed {self.package_name}")
            else:
                self.finished.emit(False, f"Installation failed: {self.package_name}\n" + "\n".join(output_lines[-10:]))
        
        except Exception as e:
            self.finished.emit(False, f"Error during installation: {str(e)}")


class GitHubInstallWorker(QThread):
    """Background worker for GitHub repository installation."""

    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)

    def __init__(self, repo_spec: str):
        super().__init__()
        self.repo_spec = repo_spec

    def run(self):
        """Execute GitHub repository installation in background."""
        try:
            self.progress.emit(f"Preparing GitHub install for {self.repo_spec}...")
            success = install_from_github(self.repo_spec)
            if success:
                self.finished.emit(True, f"Successfully installed from GitHub: {self.repo_spec}")
            else:
                self.finished.emit(False, f"GitHub installation failed for {self.repo_spec}")
        except Exception as e:
            self.finished.emit(False, f"Error during GitHub installation: {str(e)}")


class MainWindow(QMainWindow):
    """Main application window for Arjax GUI."""
    
    def __init__(self):
        super().__init__()
        
        self.detected_distro = distro.id().lower()
        self.distro_family = DISTRO_MAP.get(self.detected_distro, self.detected_distro)
        self.config = get_user_config()
        
        self.search_worker = None
        self.install_worker = None
        self.current_results = []
        self.theme_mode = getattr(self.config, "theme_mode", "system")
        if self.theme_mode not in {"system", "light", "dark"}:
            self.theme_mode = "system"
        self.active_theme = "light"
        
        self.init_ui()
        self.apply_stylesheet()
        
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle(f"Arjax - Cross-Platform Software Center ({self.detected_distro.title()})")
        self.setGeometry(80, 60, 1320, 860)
        self.setMinimumSize(1160, 760)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 18, 20, 14)
        main_layout.setSpacing(12)

        # Top store-style header
        header = QFrame()
        header.setObjectName("TopHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)

        title_col = QVBoxLayout()
        header_title = QLabel("Arjax Software Center")
        header_title.setObjectName("HeaderTitle")
        header_subtitle = QLabel("Discover, install, and maintain software across repositories")
        header_subtitle.setObjectName("HeaderSubtitle")
        title_col.addWidget(header_title)
        title_col.addWidget(header_subtitle)
        header_layout.addLayout(title_col)
        header_layout.addStretch()

        distro_badge = QLabel(f"{self.detected_distro.title()} / {self.distro_family}")
        distro_badge.setObjectName("DistroBadge")
        header_layout.addWidget(distro_badge)

        self.theme_badge = QLabel("Theme: Auto")
        self.theme_badge.setObjectName("ThemeBadge")
        header_layout.addWidget(self.theme_badge)

        self.theme_toggle_button = QPushButton("Theme: Auto")
        self.theme_toggle_button.setObjectName("ThemeToggleButton")
        self.theme_toggle_button.clicked.connect(self.cycle_theme_mode)
        header_layout.addWidget(self.theme_toggle_button)
        main_layout.addWidget(header)
        
        # Create tab widget
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.West)
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setUsesScrollButtons(True)
        self.tabs.tabBar().setElideMode(Qt.ElideRight)
        main_layout.addWidget(self.tabs)
        
        # Create tabs
        self.create_search_tab()
        self.create_installed_tab()
        self.create_maintenance_tab()
        self.create_settings_tab()
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(f"Ready - Distribution: {self.detected_distro.title()}")

        # Keep theme aligned with system settings
        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self.refresh_theme_if_needed)
        self.theme_timer.start(3000)
        
    def create_search_tab(self):
        """Create the search and install tab."""
        search_widget = QWidget()
        layout = QVBoxLayout(search_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        
        # Search controls
        search_card = QFrame()
        search_card.setObjectName("SearchBarCard")
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(12, 12, 12, 12)
        search_layout.setSpacing(10)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search apps and packages (e.g., firefox, code, blender)...")
        self.search_input.returnPressed.connect(self.perform_search)
        search_layout.addWidget(self.search_input, stretch=3)
        
        # Source filters
        self.source_combo = QComboBox()
        self.update_source_combo()
        search_layout.addWidget(QLabel("Sources:"))
        search_layout.addWidget(self.source_combo)
        
        self.search_button = QPushButton("Search")
        self.search_button.setObjectName("PrimaryAction")
        self.search_button.clicked.connect(self.perform_search)
        search_layout.addWidget(self.search_button)
        
        search_card.setLayout(search_layout)
        layout.addWidget(search_card)

        # Discovery chips (software-center style)
        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        self.trending_chip = QLabel("Trending: firefox, vscode, blender")
        self.trending_chip.setObjectName("InfoChip")
        chips_row.addWidget(self.trending_chip)

        self.scope_chip = QLabel("Scope: native repos, AUR, Flatpak, and Snap where available")
        self.scope_chip.setObjectName("InfoChip")
        chips_row.addWidget(self.scope_chip)
        chips_row.addStretch()
        layout.addLayout(chips_row)

        self.results_meta = QLabel("Results: 0")
        self.results_meta.setObjectName("ResultMeta")
        layout.addWidget(self.results_meta)
        
        # Results table and details splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Package Name", "Source", "Trust", "Description"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)
        self.results_table.itemSelectionChanged.connect(self.on_package_selected)
        splitter.addWidget(self.results_table)
        
        # Package details panel
        details_widget = QWidget()
        details_widget.setObjectName("DetailsCard")
        details_layout = QVBoxLayout(details_widget)
        
        details_layout.addWidget(QLabel("Package Details"))
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.install_button = QPushButton("Install")
        self.install_button.setObjectName("PrimaryAction")
        self.install_button.clicked.connect(self.install_selected_package)
        self.install_button.setEnabled(False)
        button_layout.addWidget(self.install_button)
        
        self.remove_button = QPushButton("Remove")
        self.remove_button.setObjectName("SecondaryAction")
        self.remove_button.clicked.connect(self.remove_selected_package)
        self.remove_button.setEnabled(False)
        button_layout.addWidget(self.remove_button)
        
        details_layout.addLayout(button_layout)
        splitter.addWidget(details_widget)
        
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Output log
        output_group = QGroupBox("Output Log")
        output_layout = QVBoxLayout()
        self.output_log = QTextEdit()
        self.output_log.setReadOnly(True)
        self.output_log.setMaximumHeight(150)
        output_layout.addWidget(self.output_log)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        self.tabs.addTab(search_widget, "Search & Install")
    
    def create_installed_tab(self):
        """Create the installed packages tab."""
        installed_widget = QWidget()
        layout = QVBoxLayout(installed_widget)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        refresh_button = QPushButton("Refresh List")
        refresh_button.clicked.connect(self.refresh_installed_packages)
        controls_layout.addWidget(refresh_button)
        
        controls_layout.addStretch()
        
        if self.distro_family == 'arch':
            audit_button = QPushButton("Audit AUR Packages")
            audit_button.clicked.connect(self.run_aur_audit)
            controls_layout.addWidget(audit_button)
        
        layout.addLayout(controls_layout)

        # Installed packages split view
        split_layout = QSplitter(Qt.Horizontal)

        apps_group = QGroupBox("Applications (Explicit/Manual)")
        apps_layout = QVBoxLayout()
        self.apps_list = QListWidget()
        self.apps_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.apps_list.setTextElideMode(Qt.ElideNone)
        apps_layout.addWidget(self.apps_list)
        apps_group.setLayout(apps_layout)
        split_layout.addWidget(apps_group)

        deps_group = QGroupBox("Dependencies (Auto-installed)")
        deps_layout = QVBoxLayout()
        self.deps_list = QListWidget()
        self.deps_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.deps_list.setTextElideMode(Qt.ElideNone)
        deps_layout.addWidget(self.deps_list)
        deps_group.setLayout(deps_layout)
        split_layout.addWidget(deps_group)

        split_layout.setStretchFactor(0, 1)
        split_layout.setStretchFactor(1, 1)
        split_layout.setChildrenCollapsible(False)
        layout.addWidget(split_layout)
        
        # Info label
        self.installed_info_label = QLabel("Click 'Refresh List' to load applications and dependencies")
        layout.addWidget(self.installed_info_label)
        
        self.tabs.addTab(installed_widget, "Installed Packages")
    
    def create_maintenance_tab(self):
        """Create the system maintenance tab."""
        maintenance_widget = QWidget()
        layout = QVBoxLayout(maintenance_widget)
        
        # Update section
        update_group = QGroupBox("System Updates")
        update_layout = QVBoxLayout()
        
        update_buttons_layout = QHBoxLayout()
        
        check_updates_btn = QPushButton("Check for Updates")
        check_updates_btn.clicked.connect(self.check_updates)
        update_buttons_layout.addWidget(check_updates_btn)
        
        install_updates_btn = QPushButton("Install Updates")
        install_updates_btn.clicked.connect(self.install_updates)
        update_buttons_layout.addWidget(install_updates_btn)
        
        update_layout.addLayout(update_buttons_layout)
        update_group.setLayout(update_layout)
        layout.addWidget(update_group)
        
        # Arch-specific maintenance
        if self.distro_family == 'arch':
            # Cleanup section
            cleanup_group = QGroupBox("System Cleanup (Arch)")
            cleanup_layout = QVBoxLayout()
            
            cleanup_buttons_layout = QHBoxLayout()
            
            orphans_btn = QPushButton("Remove Orphans")
            orphans_btn.clicked.connect(self.cleanup_orphans)
            cleanup_buttons_layout.addWidget(orphans_btn)
            
            cache_btn = QPushButton("Clean Cache")
            cache_btn.clicked.connect(self.cleanup_cache)
            cleanup_buttons_layout.addWidget(cache_btn)
            
            cleanup_layout.addLayout(cleanup_buttons_layout)
            cleanup_group.setLayout(cleanup_layout)
            layout.addWidget(cleanup_group)
            
            # Snapshot section
            snapshot_group = QGroupBox("System Snapshots (Arch)")
            snapshot_layout = QVBoxLayout()
            
            snapshot_buttons_layout = QHBoxLayout()
            
            create_snapshot_btn = QPushButton("Create Snapshot")
            create_snapshot_btn.clicked.connect(self.create_snapshot)
            snapshot_buttons_layout.addWidget(create_snapshot_btn)
            
            list_snapshots_btn = QPushButton("List Snapshots")
            list_snapshots_btn.clicked.connect(self.list_snapshots)
            snapshot_buttons_layout.addWidget(list_snapshots_btn)
            
            snapshot_layout.addLayout(snapshot_buttons_layout)
            snapshot_group.setLayout(snapshot_layout)
            layout.addWidget(snapshot_group)
            
            # Arch news section
            news_group = QGroupBox("Arch News")
            news_layout = QVBoxLayout()
            
            news_btn = QPushButton("Check Arch News")
            news_btn.clicked.connect(self.check_arch_news)
            news_layout.addWidget(news_btn)
            
            news_group.setLayout(news_layout)
            layout.addWidget(news_group)
        
        # Maintenance log
        log_group = QGroupBox("Maintenance Log")
        log_layout = QVBoxLayout()
        self.maintenance_log = QTextEdit()
        self.maintenance_log.setReadOnly(True)
        log_layout.addWidget(self.maintenance_log)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        layout.addStretch()
        
        self.tabs.addTab(maintenance_widget, "System Maintenance")
    
    def create_settings_tab(self):
        """Create the settings tab."""
        settings_widget = QWidget()
        layout = QVBoxLayout(settings_widget)
        
        # User mode section
        mode_group = QGroupBox("User Profile")
        mode_layout = QVBoxLayout()
        
        mode_label = QLabel("Select your profile mode:")
        mode_layout.addWidget(mode_label)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["normal", "advanced"])
        self.mode_combo.setCurrentText(self.config.user_mode)
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        
        mode_info = QLabel(
            "Normal: Automatic updates, news checks, trust reviews\n"
            "Advanced: Manual control over all operations"
        )
        mode_info.setWordWrap(True)
        mode_layout.addWidget(mode_info)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Automation settings (for normal mode)
        automation_group = QGroupBox("Automation Settings")
        automation_layout = QVBoxLayout()
        
        self.auto_news_check = QCheckBox("Auto-check Arch news before updates")
        self.auto_news_check.setChecked(self.config.auto_handle_arch_news)
        self.auto_news_check.stateChanged.connect(self.save_settings)
        automation_layout.addWidget(self.auto_news_check)
        
        self.auto_trust_check = QCheckBox("Auto-review AUR package trust")
        self.auto_trust_check.setChecked(self.config.auto_review_aur_trust)
        self.auto_trust_check.stateChanged.connect(self.save_settings)
        automation_layout.addWidget(self.auto_trust_check)
        
        self.auto_snapshot_check = QCheckBox("Auto-create snapshot before updates")
        self.auto_snapshot_check.setChecked(self.config.auto_snapshot_before_update)
        self.auto_snapshot_check.stateChanged.connect(self.save_settings)
        automation_layout.addWidget(self.auto_snapshot_check)
        
        self.proactive_advice_check = QCheckBox("Enable proactive system advice")
        self.proactive_advice_check.setChecked(self.config.proactive_system_advice)
        self.proactive_advice_check.stateChanged.connect(self.save_settings)
        automation_layout.addWidget(self.proactive_advice_check)
        
        automation_group.setLayout(automation_layout)
        layout.addWidget(automation_group)

        # Appearance settings
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QVBoxLayout()

        self.theme_mode_combo = QComboBox()
        self.theme_mode_combo.addItems(["system", "light", "dark"])
        self.theme_mode_combo.setCurrentText(self.theme_mode)
        self.theme_mode_combo.currentTextChanged.connect(self.on_theme_mode_changed)
        appearance_layout.addWidget(self.theme_mode_combo)

        appearance_info = QLabel("System follows your desktop theme. Light and dark stay fixed until changed again.")
        appearance_info.setWordWrap(True)
        appearance_layout.addWidget(appearance_info)

        appearance_group.setLayout(appearance_layout)
        layout.addWidget(appearance_group)
        
        # Distribution info
        info_group = QGroupBox("System Information")
        info_layout = QVBoxLayout()
        
        distro_info = QLabel(
            f"Distribution: {self.detected_distro.title()}\n"
            f"Family: {self.distro_family}\n"
            f"Python: {sys.version.split()[0]}"
        )
        info_layout.addWidget(distro_info)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        layout.addStretch()
        
        # Save button
        save_btn = QPushButton("Apply Settings")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
        self.tabs.addTab(settings_widget, "Settings")

    def detect_system_theme(self) -> str:
        """Detect whether the system palette indicates dark or light theme."""
        app = QApplication.instance()
        palette = app.palette() if app else self.palette()
        window_lightness = palette.color(QPalette.Window).lightness()
        base_lightness = palette.color(QPalette.Base).lightness()
        average = (window_lightness + base_lightness) / 2
        return "dark" if average < 128 else "light"

    def refresh_theme_if_needed(self):
        """Re-apply stylesheet when system theme changes."""
        if self.theme_mode != "system":
            return
        detected = self.detect_system_theme()
        if detected != self.active_theme:
            self.apply_stylesheet()
    
    def update_source_combo(self):
        """Update source combo box based on detected distro."""
        sources = ["All", "Pacman", "AUR", "APT", "DNF", "Zypper", "Flatpak", "Snap", "GitHub"]
        
        self.source_combo.clear()
        self.source_combo.addItems(sources)

    def get_available_search_sources(self) -> List[str]:
        """Return search sources that are likely available on this system."""
        available = []
        for source in SEARCH_SOURCES:
            if source == "aur":
                available.append(source)
                continue
            required_commands = SOURCE_COMMANDS.get(source, [])
            if any(shutil.which(command) for command in required_commands):
                available.append(source)
        return available

    def build_remove_command(self, pkg_name: str, source: str) -> Optional[str]:
        """Build a removal command for the selected package and source."""
        from arjax.package_management.command_gen import build_privileged_command
        source = source.lower()

        if source == "flatpak":
            return f"flatpak uninstall {pkg_name}"
        if source == "snap":
            return build_privileged_command(f"snap remove {pkg_name}")
        if source in {"pacman", "aur"}:
            if shutil.which("paru"):
                return f"paru -Rns {pkg_name}"
            if shutil.which("pacman"):
                return build_privileged_command(f"pacman -Rns {pkg_name}")
            return None
        if source == "apt":
            return build_privileged_command(f"apt remove {pkg_name}")
        if source == "dnf":
            return build_privileged_command(f"dnf remove {pkg_name}")
        if source == "zypper":
            return build_privileged_command(f"zypper remove {pkg_name}")

        return None

    def perform_search(self):
        """Perform package search."""
        query = self.search_input.text().strip()
        
        if not query:
            self.status_bar.showMessage("Please enter a search query")
            return
        
        source_selection = self.source_combo.currentText()
        source_key = source_selection.lower()

        if source_key == "github":
            if self.is_github_repo_spec(query):
                self.install_from_github_repo(query)
            else:
                self.open_github_search(query)
            return
        
        # Determine which sources to search
        if source_selection == "All":
            sources = self.get_available_search_sources()
        else:
            sources = [source_key]
        
        self.status_bar.showMessage(f"Searching for '{query}'...")
        self.search_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Clear previous results
        self.results_table.setRowCount(0)
        self.current_results = []
        
        # Start search in background
        self.search_worker = SearchWorker(query, self.detected_distro, self.distro_family, sources)
        self.search_worker.results_ready.connect(self.display_search_results)
        self.search_worker.error_occurred.connect(self.handle_search_error)
        self.search_worker.start()
    
    def display_search_results(self, results: List[Tuple[str, str, str]]):
        """Display search results in the table."""
        self.current_results = results
        self.results_table.setRowCount(len(results))
        self.results_meta.setText(f"Results: {len(results)}")
        
        for row, (pkg_name, description, source) in enumerate(results):
            # Package name
            self.results_table.setItem(row, 0, QTableWidgetItem(pkg_name))
            
            # Source
            self.results_table.setItem(row, 1, QTableWidgetItem(source))
            
            # Trust score (for AUR packages)
            trust_item = QTableWidgetItem("-")
            if source == 'aur':
                try:
                    trust = assess_aur_trust(pkg_name)
                    score = trust.get('score', 0)
                    trust_item = QTableWidgetItem(str(score))
                    
                    # Color code based on score
                    if score >= 75:
                        trust_item.setForeground(QColor(0, 150, 0))  # Green
                    elif score >= 50:
                        trust_item.setForeground(QColor(200, 150, 0))  # Yellow/Orange
                    else:
                        trust_item.setForeground(QColor(200, 0, 0))  # Red
                except Exception:
                    trust_item = QTableWidgetItem("?")
            
            self.results_table.setItem(row, 2, trust_item)
            
            # Description
            self.results_table.setItem(row, 3, QTableWidgetItem(description or "No description"))
        
        self.search_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage(f"Found {len(results)} package(s)")
        
        self.log_to_output(f"Search completed: {len(results)} results")
    
    def handle_search_error(self, error_message: str):
        """Handle search errors."""
        self.search_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Search failed")
        
        QMessageBox.critical(self, "Search Error", f"Search failed:\n{error_message}")
    
    def on_package_selected(self):
        """Handle package selection in results table."""
        selected_items = self.results_table.selectedItems()
        
        if not selected_items:
            self.install_button.setEnabled(False)
            self.remove_button.setEnabled(False)
            self.details_text.clear()
            return
        
        row = self.results_table.currentRow()
        
        if row < 0 or row >= len(self.current_results):
            return
        
        pkg_name, description, source = self.current_results[row]
        
        self.install_button.setEnabled(True)
        self.remove_button.setEnabled(True)
        
        # Display package details
        details = f"Package: {pkg_name}\n"
        details += f"Source: {source}\n"
        details += f"Description: {description}\n\n"
        
        # Get additional details for AUR packages
        if source == 'aur':
            try:
                aur_details = get_aur_package_details(pkg_name)
                if aur_details:
                    details += f"Version: {aur_details.get('version', 'unknown')}\n"
                    details += f"Votes: {aur_details.get('votes', 0)}\n"
                    details += f"Popularity: {aur_details.get('popularity', 0):.2f}\n"
                    details += f"Maintainer: {aur_details.get('maintainer', 'unknown')}\n"
                    details += f"URL: {aur_details.get('url', 'N/A')}\n\n"
                    
                    # Trust assessment
                    trust = assess_aur_trust(pkg_name)
                    details += f"Trust Score: {trust.get('score', 0)}/100 ({trust.get('confidence', 'unknown')})\n"
                    details += f"Assessment: {trust.get('reason', 'No details')}\n"
            except Exception as e:
                details += f"\nCould not fetch additional details: {str(e)}\n"
        
        self.details_text.setPlainText(details)
    
    def install_selected_package(self):
        """Install the selected package."""
        row = self.results_table.currentRow()
        
        if row < 0 or row >= len(self.current_results):
            return
        
        pkg_name, description, source = self.current_results[row]
        
        # Confirm installation
        reply = QMessageBox.question(
            self,
            "Confirm Installation",
            f"Install package '{pkg_name}' from {source}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Check trust for AUR packages in normal mode
        if source == 'aur' and self.config.auto_review_aur_trust:
            trust = assess_aur_trust(pkg_name)
            score = trust.get('score', 0)
            
            if score < 40:
                warning = QMessageBox.warning(
                    self,
                    "Low Trust Package",
                    f"Warning: This package has a low trust score ({score}/100)\n\n"
                    f"Reason: {trust.get('reason', 'Unknown')}\n\n"
                    f"Do you want to proceed with installation?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if warning != QMessageBox.Yes:
                    return
        
        self.log_to_output(f"Starting installation of {pkg_name} from {source}...")
        self.status_bar.showMessage(f"Installing {pkg_name}...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        self.install_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        
        # Start installation in background
        self.install_worker = InstallWorker(pkg_name, source)
        self.install_worker.progress.connect(self.log_to_output)
        self.install_worker.finished.connect(self.installation_finished)
        self.install_worker.start()
    
    def installation_finished(self, success: bool, message: str):
        """Handle installation completion."""
        self.progress_bar.setVisible(False)
        self.install_button.setEnabled(True)
        self.remove_button.setEnabled(True)
        self.search_button.setEnabled(True)
        
        self.log_to_output(message)
        
        if success:
            self.status_bar.showMessage("Installation completed successfully")
            QMessageBox.information(self, "Success", message)
        else:
            self.status_bar.showMessage("Installation failed")
            QMessageBox.critical(self, "Installation Failed", message)
    
    def remove_selected_package(self):
        """Remove the selected package."""
        row = self.results_table.currentRow()
        
        if row < 0 or row >= len(self.current_results):
            return
        
        pkg_name, _, source = self.current_results[row]
        
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Remove package '{pkg_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        self.log_to_output(f"Removing {pkg_name}...")
        self.status_bar.showMessage(f"Removing {pkg_name}...")
        
        cmd = self.build_remove_command(pkg_name, source)
        if not cmd:
            QMessageBox.warning(
                self,
                "Not Supported",
                f"Removal is not available for source '{source}' on this system."
            )
            return
        
        # Run in terminal (needs user interaction for sudo)
        self.run_terminal_command(cmd)
        
        self.status_bar.showMessage(f"Removal command sent for {pkg_name}")
    
    def refresh_installed_packages(self):
        """Refresh the list of installed packages."""
        self.apps_list.clear()
        self.deps_list.clear()
        self.installed_info_label.setText("Loading installed packages...")

        try:
            apps = set()
            deps = set()

            # Get installed package split based on distro
            if self.distro_family == 'arch':
                apps_result = subprocess.run(['paru', '-Qe'], capture_output=True, text=True, timeout=30)
                deps_result = subprocess.run(['paru', '-Qd'], capture_output=True, text=True, timeout=30)

                if apps_result.returncode == 0:
                    for line in apps_result.stdout.split('\n'):
                        parts = line.split()
                        if parts:
                            apps.add(parts[0])

                if deps_result.returncode == 0:
                    for line in deps_result.stdout.split('\n'):
                        parts = line.split()
                        if parts:
                            deps.add(parts[0])

            elif self.distro_family == 'debian':
                apps_result = subprocess.run(['apt-mark', 'showmanual'], capture_output=True, text=True, timeout=30)
                deps_result = subprocess.run(['apt-mark', 'showauto'], capture_output=True, text=True, timeout=30)

                if apps_result.returncode == 0:
                    for line in apps_result.stdout.split('\n'):
                        pkg = line.strip()
                        if pkg:
                            apps.add(pkg)

                if deps_result.returncode == 0:
                    for line in deps_result.stdout.split('\n'):
                        pkg = line.strip()
                        if pkg:
                            deps.add(pkg)

            elif self.distro_family == 'fedora':
                user_result = subprocess.run(
                    ['dnf', 'repoquery', '--userinstalled', '--qf', '%{name}'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                all_result = subprocess.run(
                    ['dnf', 'repoquery', '--installed', '--qf', '%{name}'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if user_result.returncode == 0:
                    for line in user_result.stdout.split('\n'):
                        pkg = line.strip()
                        if pkg:
                            apps.add(pkg)

                if all_result.returncode == 0:
                    all_pkgs = set()
                    for line in all_result.stdout.split('\n'):
                        pkg = line.strip()
                        if pkg:
                            all_pkgs.add(pkg)
                    deps = all_pkgs - apps

            elif self.distro_family == 'suse':
                user_result = subprocess.run(
                    ['zypper', '--quiet', 'pa', '--userinstalled'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                all_result = subprocess.run(['rpm', '-qa'], capture_output=True, text=True, timeout=30)

                if user_result.returncode == 0:
                    for line in user_result.stdout.split('\n'):
                        line = line.strip()
                        if line and '|' in line:
                            parts = [part.strip() for part in line.split('|')]
                            if len(parts) >= 3 and parts[0] in {'i', 'i+'}:
                                name = parts[2]
                                if name and name != 'Name':
                                    apps.add(name)

                if all_result.returncode == 0:
                    all_pkgs = set(pkg.strip() for pkg in all_result.stdout.split('\n') if pkg.strip())
                    deps = all_pkgs - apps

            else:
                self.installed_info_label.setText("Package listing not supported for this distribution")
                return

            # Remove overlap defensively
            deps = deps - apps

            for pkg in sorted(apps):
                item = QListWidgetItem(pkg)
                item.setToolTip(pkg)
                self.apps_list.addItem(item)

            for pkg in sorted(deps):
                item = QListWidgetItem(pkg)
                item.setToolTip(pkg)
                self.deps_list.addItem(item)

            total_count = len(apps) + len(deps)
            self.installed_info_label.setText(
                f"Applications: {len(apps)} | Dependencies: {len(deps)} | Total: {total_count}"
            )

            if total_count == 0:
                self.installed_info_label.setText("No installed packages found or package manager query failed")

        except Exception as e:
            self.installed_info_label.setText(f"Error: {str(e)}")
    
    def run_aur_audit(self):
        """Run AUR package trust audit."""
        self.maintenance_log.append("Starting AUR trust audit...")
        self.run_terminal_command("arjax audit --all")
    
    def check_updates(self):
        """Check for available updates."""
        self.maintenance_log.append("Checking for updates...")
        
        if self.distro_family == 'arch':
            self.run_terminal_command("paru -Qu")
        elif self.distro_family == 'debian':
            self.run_terminal_command("apt list --upgradable")
        elif self.distro_family == 'fedora':
            self.run_terminal_command("dnf check-update")
        elif self.distro_family == 'suse':
            self.run_terminal_command("zypper list-updates")
    
    def install_updates(self):
        """Install available updates."""
        reply = QMessageBox.question(
            self,
            "Confirm Updates",
            "Install all available updates?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        self.maintenance_log.append("Installing updates...")
        
        if self.distro_family == 'arch':
            self.run_terminal_command("paru -Syu")
        elif self.distro_family == 'debian':
            self.run_terminal_command("sudo apt upgrade")
        elif self.distro_family == 'fedora':
            self.run_terminal_command("sudo dnf upgrade")
        elif self.distro_family == 'suse':
            self.run_terminal_command("sudo zypper update")
    
    def cleanup_orphans(self):
        """Remove orphaned packages."""
        self.maintenance_log.append("Cleaning up orphaned packages...")
        self.run_terminal_command("arjax cleanup orphans")
    
    def cleanup_cache(self):
        """Clean package cache."""
        self.maintenance_log.append("Cleaning package cache...")
        self.run_terminal_command("arjax cleanup cache")
    
    def create_snapshot(self):
        """Create system snapshot."""
        self.maintenance_log.append("Creating system snapshot...")
        self.run_terminal_command("arjax snapshot create --comment 'Manual snapshot from GUI'")
    
    def list_snapshots(self):
        """List system snapshots."""
        self.maintenance_log.append("Listing system snapshots...")
        self.run_terminal_command("arjax snapshot list")
    
    def check_arch_news(self):
        """Check Arch news."""
        self.maintenance_log.append("Checking Arch news...")
        
        try:
            news = get_arch_news()
            if news.get('has_news'):
                output = news.get('output', 'No news details available')
                self.maintenance_log.append(output)
            else:
                self.maintenance_log.append("No new Arch news")
        except Exception as e:
            self.maintenance_log.append(f"Error checking news: {str(e)}")
    
    def on_mode_changed(self, mode: str):
        """Handle user mode change."""
        defaults = apply_user_mode_defaults(mode)
        
        for key, value in defaults.items():
            setattr(self.config, key, value)
        
        # Update checkboxes
        self.auto_news_check.setChecked(self.config.auto_handle_arch_news)
        self.auto_trust_check.setChecked(self.config.auto_review_aur_trust)
        self.auto_snapshot_check.setChecked(self.config.auto_snapshot_before_update)
        self.proactive_advice_check.setChecked(self.config.proactive_system_advice)
        
        self.save_settings()

    def on_theme_mode_changed(self, mode: str):
        """Handle theme mode changes from the settings tab."""
        if mode not in {"system", "light", "dark"}:
            return

        self.theme_mode = mode
        self.config.theme_mode = mode
        self.save_settings()
        self.apply_stylesheet()

    def cycle_theme_mode(self):
        """Cycle the theme mode from the header button."""
        order = ["system", "light", "dark"]
        current_index = order.index(self.theme_mode) if self.theme_mode in order else 0
        next_mode = order[(current_index + 1) % len(order)]
        if hasattr(self, "theme_mode_combo"):
            self.theme_mode_combo.blockSignals(True)
            self.theme_mode_combo.setCurrentText(next_mode)
            self.theme_mode_combo.blockSignals(False)
        self.on_theme_mode_changed(next_mode)

    def open_github_search(self, query: str):
        """Open a GitHub repository search for the current query."""
        url = f"https://github.com/search?q={query.replace(' ', '+')}&type=repositories"
        try:
            self.results_table.setRowCount(0)
            self.current_results = []
            self.install_button.setEnabled(False)
            self.remove_button.setEnabled(False)
            webbrowser.open(url)
            self.status_bar.showMessage("Opened GitHub search in browser")
            self.results_meta.setText("Results: GitHub search opened in browser")
            self.log_to_output(f"Opened GitHub search: {url}")
        except Exception as e:
            self.status_bar.showMessage("Failed to open GitHub search")
            QMessageBox.warning(
                self,
                "GitHub Search Failed",
                f"Could not open GitHub search.\n\nURL: {url}\n\nError: {str(e)}"
            )

    def is_github_repo_spec(self, query: str) -> bool:
        """Return True when the input looks like a GitHub repository specification."""
        query = query.strip()
        if not query or " " in query:
            return False

        return (
            query.startswith("github:")
            or query.startswith("https://github.com/")
            or query.startswith("http://github.com/")
            or query.startswith("git@github.com:")
            or (query.count("/") == 1 and "/" in query)
        )

    def install_from_github_repo(self, repo_spec: str):
        """Install a project directly from a GitHub repository spec."""
        repo_url = validate_github_url(repo_spec)
        if not repo_url:
            QMessageBox.warning(
                self,
                "Invalid GitHub Repo",
                "Enter a GitHub repository as github:user/repo, https://github.com/user/repo, or git@github.com:user/repo.git"
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirm GitHub Install",
            f"Install and build from GitHub repository?\n\n{repo_url}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        self.log_to_output(f"Starting GitHub install: {repo_url}")
        self.status_bar.showMessage(f"Installing from GitHub: {repo_url}...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.search_button.setEnabled(False)
        self.install_button.setEnabled(False)
        self.remove_button.setEnabled(False)

        self.install_worker = GitHubInstallWorker(repo_url)
        self.install_worker.progress.connect(self.log_to_output)
        self.install_worker.finished.connect(self.installation_finished)
        self.install_worker.start()
    
    def save_settings(self):
        """Save user settings."""
        self.config.user_mode = self.mode_combo.currentText()
        if hasattr(self, "theme_mode_combo"):
            self.config.theme_mode = self.theme_mode_combo.currentText()
            self.theme_mode = self.config.theme_mode
        self.config.auto_handle_arch_news = self.auto_news_check.isChecked()
        self.config.auto_review_aur_trust = self.auto_trust_check.isChecked()
        self.config.auto_snapshot_before_update = self.auto_snapshot_check.isChecked()
        self.config.proactive_system_advice = self.proactive_advice_check.isChecked()
        
        save_user_config(self.config)
        self.status_bar.showMessage("Settings saved", 3000)
    
    def log_to_output(self, message: str):
        """Add message to output log."""
        self.output_log.append(message)
        # Auto-scroll to bottom
        self.output_log.verticalScrollBar().setValue(
            self.output_log.verticalScrollBar().maximum()
        )
    
    def run_terminal_command(self, command: str):
        """Run a command in a terminal emulator."""
        # Try common terminal emulators
        terminals = [
            f"konsole -e {command}",
            f"gnome-terminal -- bash -c '{command}; read -p \"Press Enter to close...\"'",
            f"xterm -e {command}",
            f"alacritty -e {command}",
            f"kitty -e {command}",
        ]
        
        for terminal_cmd in terminals:
            try:
                subprocess.Popen(terminal_cmd, shell=True)
                return
            except Exception:
                continue
        
        QMessageBox.warning(self, "Terminal Not Found", "Could not find a suitable terminal emulator")
    
    def apply_stylesheet(self):
        """Apply subtle software-center stylesheet based on system theme."""
        if self.theme_mode == "system":
            self.active_theme = self.detect_system_theme()
        else:
            self.active_theme = self.theme_mode

        if self.theme_badge:
            mode_label = "System" if self.theme_mode == "system" else "Manual"
            self.theme_badge.setText(f"Theme: {self.active_theme.title()} ({mode_label})")

        if hasattr(self, "theme_toggle_button"):
            button_label = {
                "system": "Theme: Auto",
                "light": "Theme: Light",
                "dark": "Theme: Dark",
            }.get(self.theme_mode, "Theme: Auto")
            self.theme_toggle_button.setText(button_label)

        if hasattr(self, "theme_mode_combo"):
            self.theme_mode_combo.blockSignals(True)
            self.theme_mode_combo.setCurrentText(self.theme_mode)
            self.theme_mode_combo.blockSignals(False)

        light_tokens = {
            "main_bg": "#f4f6fa",
            "panel_bg": "#ffffff",
            "text": "#1f2933",
            "muted": "#5b6777",
            "border": "#dce4ef",
            "soft": "#eef3f8",
            "soft_alt": "#f8fbfd",
            "accent": "#18a558",
            "accent_dark": "#0f8f4b",
            "accent_soft": "#ddf3e6",
            "danger_soft": "#f8f1f2",
            "danger_text": "#8b1e2c",
            "header_grad_a": "#f9fbff",
            "header_grad_b": "#eef8f2",
            "badge_bg": "#e9f8ef",
            "badge_text": "#0f7f49",
            "tab_bg": "#edf2f8",
            "tab_hover": "#e4ecf5",
            "status_bg": "#ffffff",
            "list_sep": "#f0f4f8",
            "secondary_badge_bg": "#eef3fb",
            "secondary_badge_text": "#36506e"
        }

        dark_tokens = {
            "main_bg": "#151b22",
            "panel_bg": "#1d252f",
            "text": "#e3ebf4",
            "muted": "#a4b2c0",
            "border": "#2e3947",
            "soft": "#222d39",
            "soft_alt": "#1b242e",
            "accent": "#27b764",
            "accent_dark": "#1ea05a",
            "accent_soft": "#1f3a2a",
            "danger_soft": "#3a2328",
            "danger_text": "#ffb7c0",
            "header_grad_a": "#1d252f",
            "header_grad_b": "#1d3024",
            "badge_bg": "#1e3b2b",
            "badge_text": "#8fe1b1",
            "tab_bg": "#222d39",
            "tab_hover": "#2a3644",
            "status_bg": "#1b242e",
            "list_sep": "#2a3644",
            "secondary_badge_bg": "#243244",
            "secondary_badge_text": "#b9d4f2"
        }

        c = dark_tokens if self.active_theme == "dark" else light_tokens

        stylesheet = """
            QMainWindow {{
                background: {main_bg};
            }}
            QWidget {{
                background: {main_bg};
                color: {text};
                font-family: 'Noto Sans', 'Segoe UI', 'Ubuntu', sans-serif;
                font-size: 10.5pt;
            }}
            QFrame#TopHeader {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {header_grad_a}, stop:1 {header_grad_b});
                border: 1px solid {border};
                border-radius: 14px;
            }}
            QLabel#HeaderTitle {{ font-size: 20px; font-weight: 700; color: {text}; background: transparent; }}
            QLabel#HeaderSubtitle {{ font-size: 11px; color: {muted}; background: transparent; }}
            QLabel#DistroBadge {{ background: {badge_bg}; color: {badge_text}; border: 1px solid {border}; border-radius: 12px; padding: 6px 12px; font-weight: 600; }}
            QLabel#ThemeBadge {{ background: {secondary_badge_bg}; color: {secondary_badge_text}; border: 1px solid {border}; border-radius: 12px; padding: 6px 12px; font-weight: 600; }}
            QLabel#InfoChip {{ background: {soft}; color: {muted}; border: 1px solid {border}; border-radius: 12px; padding: 5px 10px; }}
            QLabel#ResultMeta {{ color: {muted}; font-weight: 600; padding-left: 2px; }}
            QFrame#SearchBarCard, QWidget#DetailsCard {{ background: {panel_bg}; border: 1px solid {border}; border-radius: 12px; }}
            QLineEdit {{ background: {panel_bg}; border: 1px solid {border}; border-radius: 10px; padding: 8px 10px; color: {text}; }}
            QLineEdit:focus {{ border: 2px solid {accent}; }}
            QPushButton {{ background: {soft}; color: {text}; border: 1px solid {border}; border-radius: 10px; padding: 8px 16px; font-weight: 600; }}
            QPushButton:hover {{ background: {tab_hover}; }}
            QPushButton:pressed {{ background: {tab_bg}; }}
            QPushButton:disabled {{ background: {soft_alt}; color: {muted}; border: 1px solid {border}; }}
            QPushButton#PrimaryAction {{ background: {accent}; color: #ffffff; border: 1px solid {accent_dark}; }}
            QPushButton#PrimaryAction:hover, QPushButton#PrimaryAction:pressed {{ background: {accent_dark}; }}
            QPushButton#SecondaryAction {{ background: {danger_soft}; color: {danger_text}; border: 1px solid {border}; }}
            QTableWidget {{ background: {panel_bg}; alternate-background-color: {soft_alt}; selection-background-color: {accent_soft}; selection-color: {text}; border: 1px solid {border}; border-radius: 10px; gridline-color: {soft}; }}
            QTableWidget::item {{ padding: 8px; border-bottom: 1px solid {soft}; }}
            QHeaderView::section {{ background: {soft}; color: {text}; padding: 8px; border: none; border-bottom: 1px solid {border}; font-weight: 700; }}
            QTextEdit {{ background: {panel_bg}; border: 1px solid {border}; border-radius: 10px; padding: 8px; color: {text}; }}
            QComboBox {{ background: {panel_bg}; border: 1px solid {border}; border-radius: 10px; padding: 7px 10px; color: {text}; }}
            QComboBox:hover {{ border: 1px solid {accent}; }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{ background: {panel_bg}; selection-background-color: {accent_soft}; color: {text}; }}
            QTabWidget::pane {{ border: 1px solid {border}; border-radius: 12px; background: {panel_bg}; }}
            QTabBar::tab {{ background: {tab_bg}; color: {muted}; padding: 12px 18px; margin: 6px 6px; border: 1px solid {border}; border-radius: 10px; min-width: 130px; text-align: left; font-weight: 600; }}
            QTabBar::tab:selected {{ background: {accent}; color: #ffffff; border: 1px solid {accent_dark}; }}
            QTabBar::tab:hover {{ background: {tab_hover}; }}
            QProgressBar {{ border: 1px solid {border}; border-radius: 8px; text-align: center; background: {panel_bg}; color: {muted}; }}
            QProgressBar::chunk {{ background: {accent}; border-radius: 7px; }}
            QGroupBox {{ background: {panel_bg}; border: 1px solid {border}; border-radius: 10px; margin-top: 12px; padding-top: 12px; font-weight: 700; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 5px; color: {accent}; }}
            QStatusBar {{ background: {status_bg}; color: {muted}; border-top: 1px solid {border}; }}
            QListWidget {{ background: {panel_bg}; border: 1px solid {border}; border-radius: 10px; }}
            QListWidget::item {{ padding: 7px; border-bottom: 1px solid {list_sep}; }}
            QListWidget::item:selected {{ background: {accent_soft}; color: {text}; }}
            QCheckBox {{ spacing: 8px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {border}; border-radius: 3px; background: {panel_bg}; }}
            QCheckBox::indicator:checked {{ background: {accent}; border: 1px solid {accent}; }}
            QLabel {{ color: {text}; }}
        """.format(**c)
        
        self.setStyleSheet(stylesheet)


def launch_gui():
    """Launch the GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Arjax")
    app.setOrganizationName("Arjax")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    launch_gui()
