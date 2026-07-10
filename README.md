---

<h2 align="center">🎯 Open Source Programmes ⭐</h2>
<p align="center">
  <b>This project is now OFFICIALLY accepted for:</b>
</p>

<div align="center">
  
![GSSoC Banner](assets/gssoc.png)

</div>


# Arjax

**Arjax** is a cross-distribution package discovery and installation tool for Linux. It separates package search from installation and uses a **provider-based architecture** to install software from native repositories, vendor installers, GitHub releases, Flatpak, Snap, and AppImages through declarative YAML recipes.

## Table of Contents

- [About](#about)
- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
  - [Search](#search)
  - [Install](#install)
  - [How Installation Works](#how-installation-works)
  - [Provider Priority](#provider-priority)
  - [Debug / Verbose Mode](#debug--verbose-mode)
  - [Other Commands](#other-commands)
- [Recipes](#recipes)
- [Adding a New Package](#adding-a-new-package)
- [🏗️ Architecture](#️-architecture)
- [🔄 Auto-Update System](#-auto-update-system)
- [File Structure](#file-structure)
- [Contributing](#contributing)
- [🛣️ Roadmap](#️-roadmap)
- [License](#license)

---

## About

Arjax works across Linux distributions. It detects your system automatically and chooses the best available installation method. Search is always **read-only** — it only displays results. The `install` command drives a separate pipeline that resolves the package through a prioritised provider chain, checks dependencies, and performs the installation with step-by-step progress output.

---

## Features

### Installation Engine
- **Provider-based installation engine** — tries providers in priority order, falls back automatically
- **Declarative YAML recipes** — add new packages by writing a recipe file, no Python required
- **Native repository installation** — pacman, AUR (via paru), apt, dnf, zypper
- **Vendor installer support** — custom package-manager mappings per recipe
- **GitHub release installation** — download and install AppImage or source releases
- **Flatpak support** — install from Flathub or any configured remote
- **Snap support** — install from the Snap Store
- **AppImage support** — download, mark executable, and link to `~/.local/bin`
- **Step-based progress output** — resolving, selecting, checking dependencies, installing — with exact timings
- **Spinner + status indicators** — green ✓ success, yellow ⚠ warning, red ✗ failure, cyan ℹ info
- **Download progress bar** — byte-level progress for GitHub/AppImage downloads
- **Installation summary** — package, provider, total time, status

### Search
- Cross-distro package search: pacman, AUR, apt, dnf, zypper, Flatpak, Snap
- Intelligent query matching and normalisation
- AUR trust scores (votes, popularity, age)
- Search is separated from installation — results are read-only

### GUI & Tools
- **Native Desktop GUI** — professional PyQt5 interface with dark theme
- **Purpose-based suggestions** — `arjax suggest "video editing"` recommends apps by use case
- **Batch installation** — install multiple packages with progress tracking
- **Auto-update system** — background checking, secure downloads, user approval
- **Arch maintenance** — orphan cleanup, cache cleanup, snapshot management, Arch news

---

## Quick Start

```sh
git clone https://github.com/AdmGenSameer/arjax.git
cd arjax
bash install.sh
```

Or directly from the web:

```sh
curl -fsSL https://raw.githubusercontent.com/AdmGenSameer/arjax/main/install.sh | bash
```

---

## Installation

The installer creates a private virtual environment, installs Arjax and its GUI dependencies, drops a launcher in `~/.local/bin`, and registers a desktop entry on graphical systems.

### Recommended: install.sh

```sh
git clone https://github.com/AdmGenSameer/arjax.git
cd arjax
bash install.sh
```

### Alternative: manual venv

```sh
git clone https://github.com/AdmGenSameer/arjax.git
cd arjax
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install .
.venv/bin/pip install PyQt5
```

---

## Usage

### Search

Search is **read-only**. It displays available packages but does not install anything.

```sh
# Basic search
arjax search firefox

# Multi-word search
arjax search visual studio code

# Sort AUR results
arjax search neovim --aur-sortby popularity

# Limit results
arjax search git --limit 10

# Skip cache
arjax search brave --no-cache
```

### Install

`install` is the separate command that drives the provider engine.

```sh
# Install using the default provider chain
arjax install brave

# Install using a specific provider
arjax install vscode --provider vendor
arjax install signal --provider flatpak
arjax install helix --provider github

# Debug mode: prints the exact command being executed
arjax install brave --debug
```

> **Note:** `search` and `install` are intentionally separate. Searching never modifies your system.

### How Installation Works

When you run `arjax install <package>`:

```
User
  │
  ▼
arjax install <package>
  │
  ▼
Recipe lookup (arjax/recipes/<package>.yaml)
  │
  ▼
InstallationOrchestrator
  │
  ▼
ProviderManager (tries providers in priority order)
  │
  ├── repository   → native PM (pacman/apt/dnf/zypper)
  ├── vendor       → recipe-specified package manager / URL
  ├── github       → GitHub release download
  ├── flatpak      → Flatpak install
  ├── snap         → Snap install
  └── appimage     → download AppImage → ~/.local/bin
```

The first provider that **succeeds** is used. Skipped and failed providers are reported in the terminal output.

**Example terminal output:**

```
╭────────────────── Arjax ──────────────────╮
│ Package : brave                           │
│ Action  : Install                         │
╰───────────────────────────────────────────╯

▶ Resolving package...
✓ Found recipe: brave

▶ Selecting provider...
  repository   ...... selected
  vendor       ...... queued (fallback)
  github       ...... queued (fallback)
  flatpak      ...... not supported
  snap         ...... not supported
  appimage     ...... not supported

▶ Checking dependencies for repository...
✓ Dependencies ready

▶ Running installation via repository...
✓ Successfully installed brave via repository

Installation Complete
───────────────────────────────────────
Resolving recipe.......... 210 ms
Selecting provider........ 2 ms
Checking dependencies..... 8 ms
Installing............... 14.32 s
Total.................... 14.55 s
───────────────────────────────────────
Package : brave
Provider: repository
Time    : 14.55 s
Status  : Success
```

### Provider Priority

Providers are tried in this order. The first one that **supports** the package and **succeeds** is used:

| Priority | Provider     | Description |
|----------|--------------|-------------|
| 1        | `repository` | Native package manager (pacman, apt, dnf, zypper) |
| 2        | `vendor`     | Vendor-specified package manager or custom mapping |
| 3        | `github`     | GitHub release (AppImage or source build) |
| 4        | `flatpak`    | Flatpak (requires Flatpak installed) |
| 5        | `snap`       | Snap (requires snapd installed) |
| 6        | `appimage`   | Direct AppImage download |

You can force a specific provider with `--provider <name>`.

### Debug / Verbose Mode

```sh
arjax install <package> --debug
```

In debug mode, arjax prints the exact command being run, e.g.:

```
$ paru -S brave-bin
```

### Other Commands

```sh
# Purpose-based app suggestions
arjax suggest "video editing"
arjax suggest coding
arjax suggest --list           # list all available purposes

# GUI
arjax gui                      # launch the desktop GUI

# Updates
arjax update                   # install all tracked updates
arjax update --check-only      # check without installing

# Configuration
arjax config --list
arjax config auto_update_enabled true

# Background service
arjax service start
arjax service stop
arjax service status

# Tracked packages
arjax list-installed

# Arch maintenance
arjax cleanup orphans
arjax cleanup cache
arjax snapshot create --comment "Before update"
arjax snapshot list
arjax update --news-only

# Self-upgrade
arjax upgrade
```

---

## Recipes

Packages are described using **declarative YAML recipes** stored in `arjax/recipes/`. A recipe declares available providers and their metadata. **Recipes contain no executable code** — they are pure data.

### Recipe structure

```yaml
name: brave
description: Brave Browser - privacy-focused web browser

providers:
  repository:
    package: brave-bin
    package_manager: pacman   # optional override

  vendor:
    package: brave-browser
    package_manager: apt      # for Debian-based systems

  flatpak:
    flatpak_id: com.brave.Browser

  github:
    github_repo: brave/brave-browser
    github_install_type: source
```

Each provider block is optional. At runtime, `ProviderManager` checks which providers a recipe declares support for, then tries them in priority order.

### Example recipes

```
arjax/recipes/
├── brave.yaml
├── docker.yaml
└── vscode.yaml
```

---

## Adding a New Package

Most new packages can be supported **without writing any Python code**. Just add a recipe file.

1. Create `arjax/recipes/<package>.yaml`
2. Declare which providers it supports and any metadata they need
3. Test: `arjax install <package>`

Example — adding Signal:

```yaml
name: signal
description: Signal - private messenger

providers:
  flatpak:
    flatpak_id: org.signal.Signal

  snap:
    snap_id: signal-desktop
```

If the package is in the native repo without special naming, no recipe is needed at all — the `repository` provider falls back to the package name you typed.

---

## 🏗️ Architecture

```
arjax/
├── interfaces/
│   ├── cli.py           # Typer CLI entrypoint
│   └── gui.py           # PyQt5 GUI entrypoint
│
├── installation/
│   ├── orchestrator.py  # Step-based install flow + rich output
│   ├── providers.py     # All provider implementations + ProviderManager
│   ├── recipes.py       # YAML recipe loading
│   └── models.py        # ProviderResult, Recipe, ProviderConfig dataclasses
│
├── search/
│   ├── aur.py           # AUR search
│   ├── pacman.py        # pacman search
│   ├── apt.py           # apt-cache search
│   ├── dnf.py           # dnf search
│   ├── zypper.py        # zypper search
│   ├── flatpak.py       # Flatpak search
│   ├── snap.py          # Snap search
│   └── ranking.py       # Scoring and deduplication
│
├── package_management/
│   ├── command_gen.py   # Install command generation
│   ├── installed.py     # Installed package tracking
│   ├── update.py        # Update logic
│   └── snapshot.py      # Snapshot management
│
├── integrations/
│   ├── github.py        # GitHub release/source installer
│   ├── cache.py         # Search result caching
│   ├── security.py      # AUR trust scoring
│   └── pkgs_org.py      # Cross-distro package lookup
│
├── intelligence/
│   ├── advisor.py       # AI-assisted package advice
│   └── suggest.py       # Purpose-based app suggestions
│
├── config/
│   ├── base.py          # Distro detection and constants
│   ├── manager.py       # User config (~/.arjax/)
│   └── logging.py       # Centralised logging
│
├── recipes/
│   ├── brave.yaml
│   ├── docker.yaml
│   └── vscode.yaml
│
└── system/
    └── monitor.py       # Background monitoring service
```

### Key design decisions

- **Search is read-only.** The `search` command never modifies your system.
- **Installation is independent.** `install` goes through `InstallationOrchestrator` → `ProviderManager` → individual providers.
- **Recipes are data, not code.** They describe packages declaratively. The engine decides what to do.
- **Providers are independent.** Each provider (`RepositoryProvider`, `FlatpakProvider`, etc.) implements a clean interface and can be tested in isolation.

---

## 🔄 Auto-Update System

Arjax includes a background update system with secure downloads, integrity validation, and user approval.

### Commands

```sh
# Enable auto-updates
arjax config auto_update_enabled true

# Start background service
arjax service start

# Check for updates
arjax update --check-only

# Install all updates
arjax update

# View tracked packages
arjax list-installed
```

### Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `auto_update_enabled` | Enable update checking | `false` |
| `auto_install_updates` | Install without prompting | `false` |
| `update_check_interval_hours` | Hours between checks | `24` |
| `max_concurrent_downloads` | Max simultaneous downloads | `3` |

---

## File Structure

```
arjax/
├── .github/                   # Issue templates, PR template
├── arjax/                     # Core Python package
│   ├── installation/          # Provider-based install engine
│   │   ├── orchestrator.py    # Step-based install flow
│   │   ├── providers.py       # Provider implementations
│   │   ├── recipes.py         # YAML recipe loader
│   │   └── models.py          # Data models
│   ├── interfaces/            # CLI and GUI entrypoints
│   ├── search/                # Per-PM search backends
│   ├── package_management/    # Command generation and tracking
│   ├── integrations/          # GitHub, cache, security, pkgs.org
│   ├── intelligence/          # Suggestions and AI advisor
│   ├── config/                # Logging, user config, distro detection
│   ├── recipes/               # YAML recipe files
│   └── system/                # Background monitor
├── tests/                     # Unit tests
├── systemd/                   # Systemd service and timer
├── data/                      # purpose_mapping.yaml
├── assets/                    # Images for README
├── install.sh                 # One-command installer
├── pyproject.toml             # Build metadata
└── README.md
```

---

## Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-branch`
3. Make your changes and commit: `git commit -m "Describe your changes"`
4. Push to your fork: `git push origin feature-branch`
5. Open a Pull Request

Report bugs or request features via the [issue tracker](https://github.com/AdmGenSameer/arjax/issues).

### Adding packages via recipes

The easiest contribution is adding YAML recipes for packages not yet supported. See [Adding a New Package](#adding-a-new-package) for the format.

### Contributing to purpose mappings

The purpose-based suggestions are powered by `data/purpose_mapping.yaml`. To contribute:

1. Edit the file to add new purposes, apps, or synonyms
2. Test with `arjax suggest "your-purpose"`
3. Submit a Pull Request

---

## 🛣️ Roadmap

- ✅ Provider-based installation engine
- ✅ Declarative YAML recipe system
- ✅ Step-based progress output with timers
- ✅ Spinner and rich terminal output
- ✅ GitHub release / AppImage download with progress bar
- ✅ openSUSE (zypper) support
- ✅ Native desktop GUI (PyQt5)
- ✅ Auto-update system
- ⏳ More YAML recipes for popular packages
- ⏳ Community-maintained recipe repository
- ⏳ Plugin/provider SDK for third-party providers
- ⏳ Automatic recipe updates from a central registry
- ⏳ Interactive TUI mode (`arjax interactive`)

---

<h2 align="center">💬 Join Our Community on Discord</h2>

<p align="center">
  <a href="https://discord.gg/bN7ycNdCR">
    <img src="assets/joinDiscordIcon.png" alt="Admin Discord" width="500"/>
  </a>
</p>

---

## License

This project is licensed under the [Apache License 2.0](./LICENSE).
