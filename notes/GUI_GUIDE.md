# archpkg GUI User Guide

## Overview

The archpkg helper native desktop GUI provides a professional, cross-distribution graphical interface for package management on Linux. Built with PyQt5, it offers a modern dark theme and comprehensive package management features.

## Installation

### Prerequisites

The GUI requires PyQt5. Install it using one of these methods:

**Using pip:**
```bash
pip install PyQt5
```

**Using your system package manager:**
```bash
# Arch Linux
sudo pacman -S python-pyqt5

# Debian/Ubuntu
sudo apt install python3-pyqt5

# Fedora
sudo dnf install python3-qt5

# openSUSE
sudo zypper install python3-qt5
```

**During archpkg installation:**
```bash
pipx install archpkg[gui]
# or
pipx install archpkg[all]  # includes all optional features
```

## Launching the GUI

**From command line:**
```bash
archpkg gui
```

**From application menu:**
Look for "archpkg helper" in your desktop environment's application menu:
- **GNOME**: Search for "archpkg" in Activities
- **KDE Plasma**: Find in Application Menu → System → Package Manager
- **XFCE**: Application Finder → System → Package Manager
- **Other DEs**: Check System or Package Manager category

## Interface Overview

The GUI consists of 4 main tabs:

### 1. Search & Install Tab

The primary tab for discovering and installing packages.

**Components:**
- **Search Bar**: Enter package names or keywords
- **Source Filter**: Choose which repositories to search (All, pacman, AUR, apt, dnf, flatpak, snap)
- **Results Table**: Displays matching packages with:
  - Package Name
  - Source (repository)
  - Trust Score (for AUR packages, color-coded)
  - Description
- **Package Details Panel**: Shows detailed information when a package is selected
- **Action Buttons**:
  - Install: Install the selected package
  - Remove: Remove the selected package
- **Output Log**: Real-time command output during installations

**Trust Scores (AUR only):**
- Green (75-100): High trust - well-maintained, popular packages
- Yellow (50-74): Medium trust - proceed with caution
- Red (0-49): Low trust - review carefully before installing
- "-": Not applicable (non-AUR packages)
- "?": Unable to determine (network error)

**Usage:**
1. Enter a search query and press Enter or click Search
2. Review the results table
3. Click on a package to see detailed information
4. Click Install to install the package
5. Confirm the installation in the dialog
6. Watch the output log for progress

### 2. Installed Packages Tab

View and manage installed packages on your system.

**Features:**
- **Refresh List**: Load all installed packages from your system
- **Package Count**: Total number of installed packages
- **AUR Audit** (Arch only): Check trust scores of installed AUR packages

**Usage:**
1. Click "Refresh List" to load packages
2. Browse the list of installed packages
3. Click "Audit AUR Packages" to check for low-trust packages (Arch only)

### 3. System Maintenance Tab

Tools for maintaining your Linux system.

**Update Section (All distros):**
- **Check for Updates**: See available package updates
- **Install Updates**: Update all packages on your system

**Cleanup Section (Arch only):**
- **Remove Orphans**: Remove orphaned packages no longer needed
- **Clean Cache**: Free up disk space by cleaning package cache

**Snapshot Section (Arch only):**
- **Create Snapshot**: Create a system snapshot before major changes
- **List Snapshots**: View available system snapshots

**Arch News Section (Arch only):**
- **Check Arch News**: Read important Arch Linux announcements

**Maintenance Log:**
- Real-time output from maintenance operations

**Usage:**
1. Choose an operation from the appropriate section
2. Confirm when prompted
3. Operations open in a terminal window for interactive commands
4. Review output in the maintenance log

### 4. Settings Tab

Configure archpkg behavior and view system information.

**User Profile:**
- **Normal Mode**: Automatic news checks, trust reviews, and snapshot creation
- **Advanced Mode**: Manual control over all operations

**Automation Settings:**
- Auto-check Arch news before updates
- Auto-review AUR package trust
- Auto-create snapshot before updates
- Enable proactive system advice

**System Information:**
- Current Linux distribution
- Distribution family (Arch, Debian, Fedora, etc.)
- Python version

**Usage:**
1. Select your preferred user mode
2. Toggle automation settings as desired
3. Click "Apply Settings" to save
4. Changes take effect immediately

## Keyboard Shortcuts

- **Enter** (in search box): Perform search
- **Ctrl+Q**: Quit application (standard Qt shortcut)

## Distribution Support

The GUI automatically detects your Linux distribution and shows relevant options:

### Supported Distributions

**Arch Family:**
- Arch Linux
- Manjaro
- EndeavourOS
- Artix
- Sources: pacman, AUR, flatpak, snap

**Debian Family:**
- Debian
- Ubuntu
- Linux Mint
- Pop!_OS
- Sources: apt, flatpak, snap

**Fedora Family:**
- Fedora
- CentOS
- RHEL
- Rocky Linux
- Sources: dnf, flatpak, snap

**openSUSE Family:**
- openSUSE Leap
- openSUSE Tumbleweed
- SUSE Linux Enterprise
- Sources: zypper, flatpak, snap

**Universal Sources:**
- Flatpak (available on all distributions)
- Snap (available on most distributions)

## Troubleshooting

### GUI Won't Launch

**Error: "PyQt5 is required"**
```bash
pip install PyQt5
```

**Error: "No module named 'archpkg.gui'"**
- Ensure you have the latest version of archpkg installed
- Try reinstalling: `pipx reinstall archpkg`

### Search Not Working

- Check your internet connection
- Try searching with a different source filter
- Check the output log for error messages

### Installation Fails

- Read the output log for specific error messages
- Ensure you have necessary permissions (sudo/root)
- For AUR packages, ensure paru or yay is installed
- Try installing from the terminal: `archpkg install <package-name>`

### Trust Scores Show "?"

- Check your internet connection
- AUR API may be temporarily unavailable
- The package may not exist in the AUR

### Terminal Commands Not Opening

The GUI needs a terminal emulator to run interactive commands. Ensure you have one installed:

```bash
# Common terminal emulators
konsole, gnome-terminal, xterm, alacritty, kitty
```

## Tips and Best Practices

1. **Before Major Updates**: Create a system snapshot (Arch)
2. **New AUR Packages**: Check trust scores before installing
3. **Regular Maintenance**: Run "Clean Cache" periodically to free disk space
4. **Stay Informed**: Check Arch news before system updates
5. **User Mode**: Use "Normal" mode for automation, "Advanced" for full control

## Advanced Features

### AUR Trust Scoring

Trust scores are calculated based on:
- **Votes** (0-30 points): Community votes indicate package popularity
- **Popularity** (0-25 points): Download/usage statistics
- **Maintainer** (±10 points): Active maintainer vs orphaned
- **Out-of-date** (-20 points): Package is flagged as outdated

### Background Monitoring (Arch - Normal Mode)

When enabled during setup, the background service monitors:
- New Arch news announcements
- Available system updates
- Low-trust AUR packages

Notifications appear every 6 hours with recommendations.

### Profile Modes

**Normal Mode:**
- Auto-checks Arch news before updates
- Blocks low-trust AUR packages
- Creates snapshots before updates
- Provides proactive system advice

**Advanced Mode:**
- Manual control over all operations
- No automatic safety checks
- Full transparency
- Recommended for experienced users

## Command Line Integration

The GUI can be launched from the command line:

```bash
# Launch GUI
archpkg gui

# Launch with debug mode
archpkg gui --debug

# Use CLI instead
archpkg search firefox
archpkg install firefox
archpkg update
archpkg cleanup orphans
```

## Comparison: CLI vs GUI

| Feature | CLI | GUI |
|---------|-----|-----|
| Package Search | ✓ | ✓ |
| Package Installation | ✓ | ✓ |
| Trust Scores | ✓ (text) | ✓ (visual) |
| System Maintenance | ✓ | ✓ |
| Settings Management | ✓ | ✓ |
| Real-time Progress | ✓ (terminal) | ✓ (progress bar) |
| Visual Feedback | - | ✓ |
| Mouse Navigation | - | ✓ |
| Keyboard Shortcuts | ✓ | ✓ |
| Script Automation | ✓ | - |
| Remote Access | ✓ (SSH) | - |

Choose CLI for:
- Remote server management
- Automation scripts
- SSH sessions
- Low resource usage

Choose GUI for:
- Desktop usage
- Visual package browsing
- Easier discovery
- Mouse-driven workflow

## Accessibility

- Keyboard navigation fully supported
- High contrast dark theme
- Clear visual indicators
- Large clickable targets
- Readable font sizes

## Privacy & Security

- No telemetry or data collection
- All operations run locally
- Package sources verified through official channels
- Trust scores help identify potentially risky AUR packages
- Open source - code is auditable

## Contributing

Found a bug or have a feature request for the GUI?

1. Check existing issues: https://github.com/AdmGenSameer/archpkg-helper/issues
2. Open a new issue with:
   - Description of the problem/request
   - Steps to reproduce (for bugs)
   - Your distribution and Python version
   - Screenshots (if relevant)

## License

The archpkg GUI is part of the archpkg-helper project and is licensed under the same terms. See LICENSE file for details.

## Credits

- PyQt5: The Qt Company
- archpkg-helper: AdmGenSameer and contributors
- Icons and themes: Qt framework defaults

---

For more information, visit: https://github.com/AdmGenSameer/archpkg-helper
