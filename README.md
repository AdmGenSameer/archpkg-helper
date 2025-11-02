---

<h2 align="center">🎯 Open Source Programmes ⭐</h2>
<p align="center">
  <b>This project is now OFFICIALLY accepted for:</b>
</p>

<div align="center">
  
![GSSoC Banner](assets/gssoc.png)

</div>


# archpkg-helper

A cross-distro command-line utility that helps you search for packages and generate install commands for native package managers (pacman, AUR, apt, dnf, flatpak, snap). It aims to make discovering and installing software on Linux simpler, regardless of your distribution.

## Table of Contents

- [About](#about)
- [Features](#features)
- [Quick Start (install.sh)](#quick-start-installsh)
- [Installation (Recommended: pipx)](#installation-recommended-pipx)
- [Alternative Installation (pip)](#alternative-installation-pip)
- [Usage](#usage)
- [File Structure](#file-structure)
- [Contributing](#contributing)
- [License](#license)

## About

archpkg-helper is designed to work across Linux distributions. While originally inspired by Arch Linux, it detects your system and generates appropriate install commands for common package managers. It’s suitable for both newcomers and experienced users who want a simpler way to search and install packages.

## Features

- **Intelligent Autocomplete**: Smart inline suggestions for package names with trie-based search, alias mapping, and frequency-based ranking
- **Purpose-based App Suggestions**: Get app recommendations based on what you want to do (e.g., "video editing", "office work", "programming")
- **Intelligent Query Matching**: Natural language processing to understand user intent (e.g., "apps to edit videos" → video editing)
- **Multi-shell Support**: Works seamlessly with bash, zsh, and fish shells
- Search for packages and generate install commands for:
  - pacman (Arch), AUR, apt (Debian/Ubuntu), dnf (Fedora), flatpak, snap
- Cross-distro support (not limited to Arch)
- Clear, readable output and errors
- One-command setup via `install.sh`

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

---

### Example Commands

Here are some common commands for using the archpkg tool:

#### 1. Intelligent Autocomplete (NEW!)

Get smart inline suggestions as you type:

```sh
# Type and press Tab for suggestions
archpkg install vs<TAB>
# Shows: visual-studio-code, vscodium, vscode-insiders

archpkg install chr<TAB>
# Shows: chromium, google-chrome

# Abbreviation matching works too!
archpkg install vsc<TAB>
# Shows: visual-studio-code

# Context-aware suggestions
archpkg remove <TAB>  # Shows recently used packages first
archpkg install <TAB> # Shows available packages
```

**Setup autocomplete:**
```sh
# Automatic setup for your shell
./scripts/autocomplete/install_completion.sh

# Or see docs/AUTOCOMPLETE.md for manual setup
```

#### 2. Purpose-based App Suggestions

Get app recommendations based on what you want to do:

```sh
# Get video editing apps
archpkg suggest "video editing"

# Get office applications
archpkg suggest "office"

# Get programming tools
archpkg suggest "coding"

# Natural language queries work too!
archpkg suggest "apps to edit videos"
archpkg suggest "programming tools"
archpkg suggest "photo editing"

# List all available purposes
archpkg suggest --list
```

#### 3. Search for a Package

Search for a package across all supported package managers:

```sh
archpkg search firefox
```


This command will search for the `firefox` package across multiple package managers (e.g., pacman, AUR, apt).

#### 4. Install a Package

Once you have identified a package, use the install command to generate the correct installation command for your system:

```sh
archpkg install firefox
```


This will generate an appropriate installation command (e.g., `pacman -S firefox` for Arch-based systems).

#### 5. Install a Package from AUR (Arch User Repository)

To install from the AUR specifically:

```sh
archpkg install vscode --source aur
```


This installs `vscode` from the AUR.

#### 6. Install a Package from Pacman

To install a package directly using pacman (e.g., on Arch Linux):

```sh
archpkg install firefox --source pacman
```


#### 7. Remove a Package

To generate commands to remove a package:

```sh
archpkg remove firefox
```


This will generate the command necessary to uninstall `firefox` from your system.

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
│   ├── suggest.py            # Purpose-based app suggestions module
│   ├── completion.py         # Intelligent autocomplete backend
│   ├── cli.py                # Main CLI interface
│   └── ...                   # Other modules
├── data/                     # Data files for suggestions
│   └── purpose_mapping.yaml  # Purpose-to-apps mapping (community-driven)
├── scripts/                  # Utility scripts
│   ├── autocomplete/         # Shell completion scripts
│   │   ├── archpkg.bash      # Bash completion script
│   │   ├── _archpkg          # Zsh completion script
│   │   ├── archpkg.fish      # Fish completion script
│   │   └── install_completion.sh  # Auto-installation script
│   └── test_completion.py    # Test script for autocomplete
├── docs/                     # Documentation
│   └── AUTOCOMPLETE.md       # Detailed autocomplete documentation
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

### Contributing to Purpose Mappings

The purpose-based suggestions are powered by a community-driven mapping file at `data/purpose_mapping.yaml`. You can help improve the suggestions by:

1. **Adding new purposes**: Add new categories of applications (e.g., "security", "education", "gaming")
2. **Adding more apps**: Suggest additional applications for existing purposes
3. **Improving descriptions**: Add better descriptions for applications
4. **Adding synonyms**: Help improve the natural language processing by adding more phrase mappings

To contribute:
1. Edit `data/purpose_mapping.yaml` to add your suggestions
2. Test your changes with `python -m archpkg.cli suggest "your-purpose"`
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
<h2 align="center">💬 Join Our Community on Discord</h2>


<p align="center">
  <a href="https://discord.gg/bN7ycNdCR">
    <img src="assets/joinDiscordIcon.png" alt="Admin Discord" width="500"/>
  </a>
</p>


## License

This project is licensed under the [Apache License 2.0](./LICENSE).
