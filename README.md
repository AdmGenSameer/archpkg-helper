# archpkg-helper

A cross-distro command-line utility that helps you search for packages and generate install commands for native package managers (pacman, AUR, apt, dnf, flatpak, snap). It aims to make discovering and installing software on Linux simpler, regardless of your distribution.

## Table of Contents

- [About](#about)
- [Features](#features)
- [Quick Start (install.sh)](#quick-start-installsh)
- [Installation (Recommended: pipx)](#installation-recommended-pipx)
- [Alternative Installation (pip)](#alternative-installation-pip)
- [Usage](#usage)
- [🔄 Auto-Update System](#🔄-auto-update-system)
- [🏗️ Architecture](#🏗️-architecture)
- [Contributing](#contributing)
- [License](#license)

## About

archpkg-helper is designed to work across Linux distributions. While originally inspired by Arch Linux, it detects your system and generates appropriate install commands for common package managers. It’s suitable for both newcomers and experienced users who want a simpler way to search and install packages.

## Features

- Search for packages and generate install commands for:
  - pacman (Arch), AUR, apt (Debian/Ubuntu), dnf (Fedora), flatpak, snap
- Cross-distro support (not limited to Arch)
- Clear, readable output and errors
- One-command setup via `install.sh`
- **Batch installation** - Install multiple packages at once with progress tracking
- **🔄 Auto-update system** with background checking, secure downloads, and user control

## Quick Start (install.sh)

Install directly using the provided installer script.

From a cloned repository:
```sh
git clone https://github.com/AdmGenSameer/archpkg-helper.git
cd archpkg-helper
bash install.sh
```

Or run directly from the web:
```sh
curl -fsSL https://raw.githubusercontent.com/AdmGenSameer/archpkg-helper/main/install.sh | bash
# or
wget -qO- https://raw.githubusercontent.com/AdmGenSameer/archpkg-helper/main/install.sh | bash
```

Notes:
- The installer ensures Python, pip, and pipx are available and installs the CLI via pipx.
- You may be prompted for sudo to install prerequisites on your distro.

## Installation (Recommended: pipx)

On Arch and many other distros, system Python may be “externally managed” (PEP 668), which prevents global pip installs. pipx installs Python CLIs into isolated environments and puts their executables on your PATH—this is the easiest, safest method.

1) Install pipx
- Arch Linux:
  ```sh
  sudo pacman -S pipx
  pipx ensurepath
  ```
- Debian/Ubuntu:
  ```sh
  sudo apt update
  sudo apt install pipx
  pipx ensurepath
  ```
- Fedora:
  ```sh
  sudo dnf install pipx
  pipx ensurepath
  ```

2) Install archpkg-helper with pipx
- Directly from GitHub:
  ```sh
  pipx install git+https://github.com/AdmGenSameer/archpkg-helper.git
  ```
- From a local clone:
  ```sh
  git clone https://github.com/AdmGenSameer/archpkg-helper.git
  cd archpkg-helper
  pipx install .
  ```

Upgrade later with:
```sh
pipx upgrade archpkg-helper
```

Ensure your shell session has pipx’s bin path in PATH (pipx prints instructions after `pipx ensurepath`, typically `~/.local/bin`).

## Alternative Installation (pip)

If you prefer pip, install in user scope to avoid system conflicts:

- From a local clone:
  ```sh
  git clone https://github.com/AdmGenSameer/archpkg-helper.git
  cd archpkg-helper
  python3 -m pip install --user .
  ```
- Directly from GitHub:
  ```sh
  python3 -m pip install --user git+https://github.com/AdmGenSameer/archpkg-helper.git
  ```

If your distro enforces PEP 668 protections for global installs, you may see errors. You can bypass with:
```sh
python3 -m pip install --break-system-packages .
```
However, using pipx is strongly recommended instead of breaking system protections.

## Usage

After installation, the CLI is available as `archpkg`.

## Web Interface

ArchPkg Helper also provides a web interface for a more user-friendly experience:

```sh
archpkg --web
```

This starts a web server at `http://localhost:5000` where you can:
- Browse a descriptive home page explaining the tool
- Search for packages using a web form
- View results with copy-to-clipboard functionality

---

### Example Commands

Here are some common commands for using the archpkg tool:

#### 1. Search for a Package

Search for a package across all supported package managers:

```sh
archpkg search firefox
```


This command will search for the `firefox` package across multiple package managers (e.g., pacman, AUR, apt).

#### 2. Install Multiple Packages (Batch Installation)

Install multiple packages at once with automatic validation and progress tracking:

```sh
archpkg install firefox vscode git
```

This command will:
- Search for each package automatically
- Select the best match for each
- Install all packages sequentially
- Show progress and a summary of successes/failures

Batch installation validates all packages first, then proceeds with installation. If any package fails validation, the entire batch is cancelled.

#### 3. Install a Package from AUR (Arch User Repository)

To install from the AUR specifically:

```sh
archpkg install vscode --source aur
```


This installs `vscode` from the AUR.

#### 4. Install a Package from Pacman

To install a package directly using pacman (e.g., on Arch Linux):

```sh
archpkg install firefox --source pacman
```


#### 5. Install from GitHub

Install software directly from GitHub repositories:

```sh
archpkg github:user/repo
```

Or using full URL:

Install software directly from GitHub repositories:

```sh
archpkg github:user/repo
```

Or using full URL:

```sh
archpkg https://github.com/user/repo
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
archpkg github:pypa/pip

# Install a Node.js application
archpkg github:microsoft/vscode

# Install a Go tool
archpkg github:golang/go
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
- flatpak (Flatpak)
- snap (Snap)

For example, to install `vscode` from the AUR:

```sh
archpkg install vscode --source aur
```


#### 2. `--help`

To view a list of available commands and options:

```sh
archpkg --help
```


#### 3. `--version`

To check the installed version of archpkg:

```sh
archpkg --version
```
---

## 🔄 Auto-Update System

archpkg-helper includes a comprehensive auto-update system that can automatically check for, download, and install package updates while maintaining security and giving you control over the process.

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
   archpkg config auto_update_enabled true
   ```

2. **Start Background Service**:
   ```sh
   archpkg service start
   ```

3. **Track Your First Package**:
   ```sh
   archpkg install firefox  # Uses --track by default
   ```

### Auto-Update Commands

#### Check for Updates
```sh
# Check all tracked packages for updates
archpkg update --check-only

# Check specific packages
archpkg update firefox vscode --check-only
```

#### Install Updates
```sh
# Install all available updates
archpkg update

# Install updates for specific packages
archpkg update firefox vscode
```

#### Manage Configuration
```sh
# View all settings
archpkg config --list

# Enable auto-updates
archpkg config auto_update_enabled true

# Set update check interval (hours)
archpkg config update_check_interval_hours 24

# Enable automatic installation (use with caution)
archpkg config auto_install_updates true
```

#### Manage Background Service
```sh
# Start the background update service
archpkg service start

# Stop the service
archpkg service stop

# Check service status
archpkg service status
```

#### View Tracked Packages
```sh
# List all tracked packages
archpkg list-installed
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

1. **Package Tracking**: When you install packages with `archpkg install`, they're automatically tracked
2. **Background Checking**: The service periodically checks for updates from the original sources
3. **Secure Downloads**: Updates are downloaded with integrity validation
4. **User Approval**: You can review updates before installation (unless auto-install is enabled)
5. **Safe Installation**: Commands are validated for safety before execution

### Examples

**Enable auto-updates for security packages**:
```sh
archpkg config auto_update_enabled true
archpkg service start
archpkg install firefox thunderbird --track
```

**Manual update workflow**:
```sh
# Check for updates
archpkg update --check-only

# Review what needs updating
archpkg list-installed

# Install specific updates
archpkg update firefox
```

**Disable auto-updates**:
```sh
archpkg service stop
archpkg config auto_update_enabled false
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
  - `flatpak`  
  - `snap`

- 🖥️ **System Detector**  
  Automatically detects your Linux distribution and selects the correct package manager.

- ⚡ **Installer Script (`install.sh`)**  
  One-line setup that ensures Python, pip, and pipx are installed before deploying `archpkg`.

This modular architecture makes the project **extensible** — new package managers can be added with minimal changes.

---

## Tips for Beginners

- **Start by Searching:** Before installing anything, try using the `archpkg search <package-name>` command to check if the package exists and where it can be installed from.

```sh
archpkg search firefox
```


This will list all available versions of Firefox across supported sources.

- **Understand Sources and Flags:** By default, archpkg will try to find packages from the most common sources. If you prefer to use a specific source (e.g., AUR or pacman), you can specify it using the `--source` flag.

```sh
archpkg install vscode --source aur
```


- **Keep It Simple with Installation:** Once you find the package you want, use the `archpkg install <package-name>` command to generate the installation command for your system.

- **Removal Commands:** Don’t forget that archpkg can also generate commands for removing installed packages. For example:

```sh
archpkg remove firefox
```


- **Auto-detect Your Package Manager:** If you’re unsure which package manager your distro uses, The archpkg-helper tool can automatically detect your system, making it easier to get started without manual configuration.

- **Handle Permission Errors with sudo:** If you encounter permission errors, try using `sudo` (superuser privileges) for commands that require administrative rights, especially when installing prerequisites or system packages.


---

## File Structure

Top-level layout of this repository:
```
archpkg-helper/
├── .github/                  # issue templates and pull request template
├── archpkg/                  # Core Python package code (CLI and logic)
├── install.sh                # One-command installer script (uses pipx)
├── pyproject.toml            # Build/metadata configuration
├── setup.py                  # Packaging configuration (entry points, deps)
├── LICENSE                   # Project license (Apache 2.0)
├── README.md                 # Project documentation (this file)
├── build/                    # Build artifacts (may appear after builds)
├── __pycache__/              # Python bytecode cache (auto-generated)
├── archpkg_helper.egg-info/  # Packaging metadata (auto-generated)
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

Report bugs or request features via the [issue tracker](https://github.com/AdmGenSameer/archpkg-helper/issues).
---

## 🛣️ Roadmap

Here’s what’s planned for future releases of **archpkg-helper**:

- 🔧 **Add support for `zypper` (openSUSE)**  
  Extend backend adapters to cover openSUSE users.

- ⚡ **Caching layer for faster searches**  
  Improve performance by reducing repeated lookups across package managers.

- 💻 **Interactive mode (`archpkg interactive`)**  
  A guided, menu-driven interface to search, choose a package source, and install/remove easily.

- 🖼️ **GUI frontend (future idea)**  
  Build a graphical user interface on top of the CLI for desktop users who prefer point-and-click.
  
---

## License

This project is licensed under the [Apache License 2.0](./LICENSE).