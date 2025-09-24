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

Examples:
```sh
# Search for a package across supported sources
archpkg search <package-name>

# Generate install command(s) for a package
archpkg install <package-name>

# Generate removal command(s) for a package
archpkg remove <package-name>
```

Additional:
```sh
archpkg --help
archpkg --version
```

Replace `<package-name>` with the package you want to manage.

## File Structure

Top-level layout of this repository:
```
archpkg-helper/
├── src/
│   └── archpkg/            # Core Python package code (CLI and logic)
├── install.sh              # One-command installer script (uses pipx)
├── pyproject.toml          # Build/metadata configuration
├── setup.py                # Packaging configuration (entry points, deps)
├── LICENSE                 # Project license (Apache 2.0)
└── README.md               # Project documentation (this file)
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
