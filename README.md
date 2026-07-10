---

<h2 align="center">🎯 Open Source Programmes ⭐</h2>
<p align="center">
  <b>This project is now OFFICIALLY accepted for:</b>
</p>

<div align="center">
  
![GSSoC Banner](assets/gssoc.png)

</div>


# Arjax

A cross-distro command-line utility that helps you search for packages and generate install commands for native package managers (pacman, AUR, apt, dnf, flatpak, snap). It aims to make discovering and installing software on Linux simpler, regardless of your distribution.

## Table of Contents

- [About](#about)
- [Features](#features)
- [Quick Start (install.sh)](#quick-start-installsh)
- [Installation (Recommended: install.sh)](#installation-recommended-installsh)
- [Alternative Installation (venv)](#alternative-installation-venv)
- [Usage](#usage)
- [🔄 Auto-Update System](#🔄-auto-update-system)
- [🏗️ Architecture](#🏗️-architecture)
- [Contributing](#contributing)
- [License](#license)

## About

Arjax is designed to work across Linux distributions. While originally inspired by Arch Linux, it detects your system and generates appropriate install commands for common package managers. It’s suitable for both newcomers and experienced users who want a simpler way to search and install packages.

## Features

- **Native Desktop GUI**: Professional PyQt5-based graphical interface for package management
  - Cross-distro support (Arch, Debian, Ubuntu, Kali, Mint, Fedora, openSUSE, etc.)
  - Search, install, and remove packages with visual feedback
  - Real-time trust scores for AUR packages
  - System maintenance tools (updates, cleanup, snapshots)
  - Settings management with user profiles
  - Dark theme professional design
- **Purpose-based App Suggestions**: Get app recommendations based on what you want to do (e.g., "video editing", "office work", "programming")
- **Intelligent Query Matching**: Natural language processing to understand user intent (e.g., "apps to edit videos" → video editing)
- Search for packages and generate install commands for:
  - pacman (Arch), AUR, apt (Debian/Ubuntu), dnf (Fedora), zypper (openSUSE), flatpak, snap
- Cross-distro support (not limited to Arch)
- Clear, readable output and errors
- One-command setup via `install.sh`
- **Batch installation** - Install multiple packages at once with progress tracking
- **🔄 Auto-update system** with background checking, secure downloads, and user control
- **🧰 Arch maintenance commands** for orphan cleanup, cache cleanup, snapshot management, and Arch news via `paru`

## Quick Start (install.sh)

Install directly using the provided installer script.

From a cloned repository:
```sh
git clone https://github.com/AdmGenSameer/arjax.git
cd arjax
bash install.sh
```

Or run directly from the web:
```sh
curl -fsSL https://raw.githubusercontent.com/AdmGenSameer/arjax/main/install.sh | bash
# or
wget -qO- https://raw.githubusercontent.com/AdmGenSameer/arjax/main/install.sh | bash
```

Notes:
  - The installer creates a private virtual environment, installs Arjax there, and adds a launcher to `~/.local/bin`
  - Installs both CLI and GUI automatically
  - On Arch-based systems, installer asks for a profile:
  - `normal` (recommended): automatic advice + news/trust-aware updates
  - `advanced`: manual control

## Installation (Recommended: install.sh)

The installer now follows one path on every supported distro:

1) It creates a private virtual environment under `~/.local/share/arjax`
2) It installs Arjax into that environment
3) It installs PyQt5 for the GUI
4) It drops a launcher in `~/.local/bin/arjax`
5) It updates common shell startup files so `arjax` is available in new shells
6) On graphical systems, it creates a desktop entry in `~/.local/share/applications`

From a cloned repository:
```sh
git clone https://github.com/AdmGenSameer/arjax.git
cd arjax
bash install.sh
```

Or run it from the repository contents you already have:
```sh
bash install.sh
```

## Alternative Installation (venv)

If you prefer to manage the environment yourself:

```sh
git clone https://github.com/AdmGenSameer/arjax.git
cd arjax
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install .
.venv/bin/pip install PyQt5
```

Then launch:
```sh
.venv/bin/arjax gui
```

If you still want a pipx-managed install, `pipx install .` works from a local clone.

## Usage

After installation, the CLI is available as `arjax`.

## Native Desktop GUI

Arjax provides a professional native desktop application for graphical package management:

```sh
# Launch from command line
arjax gui

# Or find it in your application menu
# Look for "Arjax" in System/Package Manager category
```

On graphical systems, the GUI appears in your desktop environment's application menu (GNOME Activities, KDE Application Menu, XFCE Application Finder, etc.) after installation. On CLI-only systems, the installer skips the menu entry and leaves the `arjax` command-line launcher available.

**GUI Features:**
- **Search & Install Tab**: Search packages across all sources with real-time trust scores
  - Visual trust indicators (color-coded)
  - Package details panel
  - One-click install/remove
  - Live output log
- **Installed Packages Tab**: View all installed packages
  - Refresh package lists
  - AUR trust audit (Arch only)
- **System Maintenance Tab**: System management tools
  - Check and install updates
  - Clean orphaned packages (Arch)
  - Clean package cache (Arch)
  - Create/list system snapshots (Arch)
  - Check Arch news
- **Settings Tab**: Configure user profiles and automation
  - Normal vs Advanced mode
  - Automation preferences
  - System information

**Notes:**
- PyQt5 is automatically installed when using `install.sh`
- Both CLI and GUI are available immediately after installation
- For manual venv installs: `pip install PyQt5`
- If GUI dependencies are ever missing, run `arjax add gui`

The GUI works on all distributions and automatically adapts to your system's package manager.

---

### Example Commands

Here are some common commands for using the Arjax tool:

#### 1. Purpose-based App Suggestions (NEW!)

Get app recommendations based on what you want to do:

```sh
# Get video editing apps
arjax suggest "video editing"

# Get office applications
arjax suggest "office"

# Get programming tools
arjax suggest "coding"

# Natural language queries work too!
arjax suggest "apps to edit videos"
arjax suggest "programming tools"
arjax suggest "photo editing"

# List all available purposes
arjax suggest --list
```

#### 2. Search for a Package

Search for a package across all supported package managers:

```sh
arjax search firefox
```

Sort AUR results with Paru-style fields:

```sh
arjax search firefox --aur-sortby popularity
```


This command will search for the `firefox` package across multiple package managers (e.g., pacman, AUR, apt).

#### 3. Arch Linux Maintenance Commands (paru-powered)

```sh
# Show Arch news (no updates)
arjax update --news-only

# Create snapshot before updates
arjax update --snapshot

# Find orphaned packages without removing
arjax cleanup orphans --dry-run

# Remove orphaned packages
arjax cleanup orphans

# Clean package cache
arjax cleanup cache

# Snapshot management
arjax snapshot create --comment "Before full update"
arjax snapshot list

# Audit trust scores of installed AUR packages
arjax audit                    # Show only low-trust packages
arjax audit --verbose          # Show detailed info for all packages
arjax audit --all              # Show trust scores for all AUR packages
arjax audit --threshold 60     # Custom threshold for warnings
```

**Trust Score Features:**
- 🔍 **Search Results**: AUR packages now show trust scores (0-100) in search results with color coding
- 🛡️ **Trust Audit**: Check all installed AUR packages for trust issues (low votes, unmaintained, out-of-date)
- 📊 **Automatic Checks**: Normal mode automatically reviews AUR package trust before installation
- 🔔 **Background Monitoring**: Optional systemd service checks system health every 6 hours (normal mode only)

#### 4. Profile / Abstraction Mode

```sh
# Run onboarding anytime
arjax setup

# Force a profile directly
arjax setup --mode normal
arjax setup --mode advanced
```

- `normal` profile (recommended): arjax handles Arch news checks, AUR trust review, and safer update defaults for you.
- `advanced` profile: keeps actions manual and transparent.

#### 5. Background Monitoring Service (Arch Linux - Normal Mode)

The background monitoring service can be enabled during `arjax setup` on Arch Linux. It runs every 6 hours to check for:
- New Arch news announcements
- Available system updates
- Low-trust AUR packages

Manual service management:
```sh
# Check service status
systemctl --user status arjax-monitor.timer

# View recent logs
journalctl --user -u arjax-monitor.service -n 50

# Stop the service
systemctl --user stop arjax-monitor.timer

# Restart the service
systemctl --user start arjax-monitor.timer

# Run a check immediately
python3 -m arjax.monitor --once
```

The service sends desktop notifications when action is recommended (e.g., new Arch news, updates available, low-trust packages detected).

#### 2. Install Multiple Packages (Batch Installation)
#### 3. Install a Package

Install multiple packages at once with automatic validation and progress tracking:

```sh
arjax install firefox vscode git
```

This command will:
- Search for each package automatically
- Select the best match for each
- Install all packages sequentially
- Show progress and a summary of successes/failures

Batch installation validates all packages first, then proceeds with installation. If any package fails validation, the entire batch is cancelled.

#### 4. Install a Package from AUR (Arch User Repository)

To install from the AUR specifically:

```sh
arjax install vscode --source aur
```


This installs `vscode` from the AUR.

#### 5. Install a Package from Pacman

To install a package directly using pacman (e.g., on Arch Linux):

```sh
arjax install firefox --source pacman
```


#### 5. Install from GitHub
#### 6. Remove a Package

Install software directly from GitHub repositories:

```sh
arjax github:user/repo
```

Or using full URL:

Install software directly from GitHub repositories:

```sh
arjax github:user/repo
```

Or using full URL:

```sh
arjax https://github.com/user/repo
```

This feature will:
- Clone the specified GitHub repository
- Auto-detect the project type (Python, Node.js, CMake, etc.)
- Build and install the software automatically
- Clean up temporary files afterwards

**Supported project types:**
- Python (setup.py, pyproject.toml)
- Node.js (package.json)
- CMake (CMakeLists.txt)
- Makefile projects
- Go (go.mod)
- Rust (Cargo.toml)

**Examples:**
```sh
# Install a Python CLI tool
arjax github:pypa/pip

# Install a Node.js application
arjax github:microsoft/vscode

# Install a Go tool
arjax github:golang/go
```

**Note:** GitPython is recommended for better performance, but the tool will fallback to using git subprocess if not available.

---

### Optional Flags

#### 1. `--source <source>`

You can specify the package manager source using the `--source` flag. Supported sources include:

- pacman (Arch Linux)
- aur (AUR)
- apt (Debian/Ubuntu)
- dnf (Fedora)
- zypper (openSUSE)
- flatpak (Flatpak)
- snap (Snap)

For example, to install `vscode` from the AUR:

```sh
arjax install vscode --source aur
```


#### 2. `--help`

To view a list of available commands and options:

```sh
arjax --help
```


#### 3. `--version`

To check the installed version of arjax:

```sh
arjax --version
```
---

## 🔄 Auto-Update System

arjax includes a comprehensive auto-update system that can automatically check for, download, and install package updates while maintaining security and giving you control over the process.

### Features

- **Automatic Update Checking**: Background service that periodically checks for package updates
- **Secure Downloads**: Resumable downloads with integrity validation
- **User Control**: Choose between automatic installation or manual approval
- **Package Tracking**: Track installed packages and their update status
- **Security Validations**: Checksum validation and command safety checks
- **Atomic Operations**: Safe configuration and data management

### Quick Start

1. **Enable Auto-Updates**:
   ```sh
   arjax config auto_update_enabled true
   ```

2. **Start Background Service**:
   ```sh
   arjax service start
   ```

3. **Track Your First Package**:
   ```sh
   arjax install firefox  # Uses --track by default
   ```

### Auto-Update Commands

#### Check for Updates
```sh
# Check all tracked packages for updates
arjax update --check-only

# Check specific packages
arjax update firefox vscode --check-only
```

#### Install Updates
```sh
# Install all available updates
arjax update

# Install updates for specific packages
arjax update firefox vscode
```

#### Manage Configuration
```sh
# View all settings
arjax config --list

# Enable auto-updates
arjax config auto_update_enabled true

# Set update check interval (hours)
arjax config update_check_interval_hours 24

# Enable automatic installation (use with caution)
arjax config auto_install_updates true
```

#### Manage Background Service
```sh
# Start the background update service
arjax service start

# Stop the service
arjax service stop

# Check service status
arjax service status
```

#### View Tracked Packages
```sh
# List all tracked packages
arjax list-installed
```

### Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| `auto_update_enabled` | Enable/disable automatic update checking | `false` |
| `auto_install_updates` | Automatically install updates when found | `false` |
| `update_check_interval_hours` | Hours between update checks | `24` |
| `max_concurrent_downloads` | Maximum simultaneous downloads | `3` |

### Security Features

- **Checksum Validation**: Downloaded packages are validated against known checksums
- **Command Safety**: Installation commands are checked for dangerous patterns
- **Source Validation**: Only trusted package sources are allowed
- **Atomic Operations**: Configuration changes are atomic to prevent corruption

### How It Works

1. **Package Tracking**: When you install packages with `arjax install`, they're automatically tracked
2. **Background Checking**: The service periodically checks for updates from the original sources
3. **Secure Downloads**: Updates are downloaded with integrity validation
4. **User Approval**: You can review updates before installation (unless auto-install is enabled)
5. **Safe Installation**: Commands are validated for safety before execution

### Examples

**Enable auto-updates for security packages**:
```sh
arjax config auto_update_enabled true
arjax service start
arjax install firefox thunderbird --track
```

**Manual update workflow**:
```sh
# Check for updates
arjax update --check-only

# Review what needs updating
arjax list-installed

# Install specific updates
arjax update firefox
```

**Disable auto-updates**:
```sh
arjax service stop
arjax config auto_update_enabled false
```

---

## 🏗️ Architecture

The tool is structured as a **modular Python CLI** with:

- 📝 **Command Parser**  
  Handles subcommands like `search`, `install`, `remove`.

- 🔌 **Backend Adapters**  
  Provides an abstraction layer for each package manager:  
  - `pacman` (Arch Linux)  
  - `aur` (Arch User Repository)  
  - `apt` (Debian/Ubuntu)  
  - `dnf` (Fedora)  
  - `zypper` (openSUSE)  
  - `flatpak`  
  - `snap`

- 🖥️ **System Detector**  
  Automatically detects your Linux distribution and selects the correct package manager.

- ⚡ **Installer Script (`install.sh`)**  
  One-line setup that ensures Python, pip, and pipx are installed before deploying `arjax`.

This modular architecture makes the project **extensible** — new package managers can be added with minimal changes.

---

## Tips for Beginners

- **Start by Searching:** Before installing anything, try using the `arjax search <package-name>` command to check if the package exists and where it can be installed from.

```sh
arjax search firefox
```


This will list all available versions of Firefox across supported sources.

- **Understand Sources and Flags:** By default, arjax will try to find packages from the most common sources. If you prefer to use a specific source (e.g., AUR or pacman), you can specify it using the `--source` flag.

```sh
arjax install vscode --source aur
```


- **Keep It Simple with Installation:** Once you find the package you want, use the `arjax install <package-name>` command to generate the installation command for your system.

- **Removal Commands:** Don’t forget that arjax can also generate commands for removing installed packages. For example:

```sh
arjax remove firefox
```


- **Auto-detect Your Package Manager:** If you’re unsure which package manager your distro uses, The arjax tool can automatically detect your system, making it easier to get started without manual configuration.

- **Handle Permission Errors with sudo:** If you encounter permission errors, try using `sudo` (superuser privileges) for commands that require administrative rights, especially when installing prerequisites or system packages.


---

## File Structure

Top-level layout of this repository:
```
arjax/
├── .github/                  # issue templates and pull request template
├── arjax/                  # Core Python package code (CLI and logic)
│   ├── suggest.py            # Purpose-based app suggestions module
│   ├── cli.py                # Main CLI interface
│   └── ...                   # Other modules
├── data/                     # Data files for suggestions
│   └── purpose_mapping.yaml  # Purpose-to-apps mapping (community-driven)
├── install.sh                # One-command installer script (uses pipx)
├── pyproject.toml            # Build/metadata configuration
├── setup.py                  # Packaging configuration (entry points, deps)
├── LICENSE                   # Project license (Apache 2.0)
├── README.md                 # Project documentation (this file)
├── build/                    # Build artifacts (may appear after builds)
├── __pycache__/              # Python bytecode cache (auto-generated)
├── arjax.egg-info/  # Packaging metadata (auto-generated)
└── archpy.egg-info/          # Packaging metadata (auto-generated)
```

Some metadata/build directories are generated during packaging and may not be present in fresh clones.

## Notes

  - The installer ensures Python, pip, and pipx are available.
  - You may be prompted for sudo.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch: `git checkout -b feature-branch`
3. Make your changes and commit: `git commit -m "Describe your changes"`
4. Push to your fork: `git push origin feature-branch`
5. Open a Pull Request

Report bugs or request features via the [issue tracker](https://github.com/AdmGenSameer/arjax/issues).

### Contributing to Purpose Mappings

The purpose-based suggestions are powered by a community-driven mapping file at `data/purpose_mapping.yaml`. You can help improve the suggestions by:

1. **Adding new purposes**: Add new categories of applications (e.g., "security", "education", "gaming")
2. **Adding more apps**: Suggest additional applications for existing purposes
3. **Improving descriptions**: Add better descriptions for applications
4. **Adding synonyms**: Help improve the natural language processing by adding more phrase mappings

To contribute:
1. Edit `data/purpose_mapping.yaml` to add your suggestions
2. Test your changes with `python -m arjax.cli suggest "your-purpose"`
3. Submit a Pull Request with your improvements

Example contribution:
```yaml
# Add to data/purpose_mapping.yaml
security:
  - firejail
  - tor
  - keepassxc
  - veracrypt
  - wireshark
```
---

## 🛣️ Roadmap

Here’s what’s planned for future releases of **arjax**:

- ✅ **Add support for `zypper` (openSUSE)** - COMPLETED  
  Extended backend adapters to cover openSUSE users.

- ⚡ **Caching layer for faster searches**  
  Improve performance by reducing repeated lookups across package managers.

- 💻 **Interactive mode (`arjax interactive`)**  
  A guided, menu-driven interface to search, choose a package source, and install/remove easily.

- 🖼️ **GUI frontend (future idea)**  
  Build a graphical user interface on top of the CLI for desktop users who prefer point-and-click.
  
---
<h2 align="center">💬 Join Our Community on Discord</h2>


<p align="center">
  <a href="https://discord.gg/bN7ycNdCR">
    <img src="assets/joinDiscordIcon.png" alt="Admin Discord" width="500"/>
  </a>
</p>


## License

This project is licensed under the [Apache License 2.0](./LICENSE).
