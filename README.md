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

#### 1. Search for a Package

Search for a package across all supported package managers:

```sh
archpkg search firefox
```


This command will search for the `firefox` package across multiple package managers (e.g., pacman, AUR, apt).

#### 2. Install a Package

Once you have identified a package, use the install command to generate the correct installation command for your system:

```sh
archpkg install firefox
```


This will generate an appropriate installation command (e.g., `pacman -S firefox` for Arch-based systems).

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


#### 5. Remove a Package

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

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch: `git checkout -b feature-branch`
3. Make your changes and commit: `git commit -m "Describe your changes"`
4. Push to your fork: `git push origin feature-branch`
5. Open a Pull Request

Report bugs or request features via the [issue tracker](https://github.com/AdmGenSameer/archpkg-helper/issues).

## License

This project is licensed under the [Apache License 2.0](./LICENSE).