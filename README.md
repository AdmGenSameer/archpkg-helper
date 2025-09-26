# archpkg-helper 🧰  
*A universal package helper for Linux distributions*

---

**archpkg-helper** is a cross-distro command-line utility that helps you **search for packages** and **generate install/remove commands** for native Linux package managers such as:

- `pacman` (Arch)
- `AUR`
- `apt` (Debian/Ubuntu)
- `dnf` (Fedora)
- `flatpak`
- `snap`

It aims to simplify software discovery and installation, regardless of which Linux distribution you use.

---

## 📚 Table of Contents

- [About](#about)
- [Features](#features)
- [Quick Start (install.sh)](#quick-start-installsh)
- [Installation (Recommended: pipx)](#installation-recommended-pipx)
- [Alternative Installation (pip)](#alternative-installation-pip)
- [Usage](#usage)
- [File Structure](#file-structure)
- [Contributing](#contributing)
- [License](#license)

---

## 🔍 About

**archpkg-helper** is designed to work across Linux distributions. While originally inspired by Arch Linux, it automatically detects your system and generates the appropriate commands for the package manager available.

It’s suitable for:

- 🧑‍💻 Newcomers who aren’t familiar with Linux package managers  
- 💡 Developers who work across multiple distros  
- 🧠 Experienced users looking for a more unified workflow

---

## ✨ Features

✅ Search for packages and generate install commands for:

- `pacman` (Arch)  
- `AUR` (via AUR helpers)  
- `apt` (Debian/Ubuntu)  
- `dnf` (Fedora)  
- `flatpak`  
- `snap`

✅ Cross-distro support (not limited to Arch)  
✅ Clear, readable output and helpful error messages  
✅ One-command setup via `install.sh`

---

## ⚡ Quick Start (install.sh)

Install `archpkg-helper` using the one-line installer script:

### From a cloned repository

```bash
git clone https://github.com/AdmGenSameer/archpkg-helper.git
cd archpkg-helper
bash install.sh
Or run directly from the web
bash
Copy code
curl -fsSL https://raw.githubusercontent.com/AdmGenSameer/archpkg-helper/main/install.sh | bash
# or
wget -qO- https://raw.githubusercontent.com/AdmGenSameer/archpkg-helper/main/install.sh | bash
Notes:

The installer ensures that Python, pip, and pipx are available.

You may be prompted for sudo to install missing dependencies.

📦 Installation (Recommended: pipx)
Modern Linux distros often protect system Python (via PEP 668), which makes pipx the preferred method for installing CLI tools.

🛠️ Step 1: Install pipx
<details> <summary>📦 Arch Linux</summary>
bash
Copy code
sudo pacman -S pipx
pipx ensurepath
</details> <details> <summary>📦 Debian / Ubuntu</summary>
bash
Copy code
sudo apt update
sudo apt install pipx
pipx ensurepath
</details> <details> <summary>📦 Fedora</summary>
bash
Copy code
sudo dnf install pipx
pipx ensurepath
</details>
🧰 Step 2: Install archpkg-helper
From GitHub:

bash
Copy code
pipx install git+https://github.com/AdmGenSameer/archpkg-helper.git
From a local clone:

bash
Copy code
git clone https://github.com/AdmGenSameer/archpkg-helper.git
cd archpkg-helper
pipx install .
🔄 To upgrade later:
bash
Copy code
pipx upgrade archpkg-helper
📌 After running pipx ensurepath, ensure your shell has ~/.local/bin in your PATH.

🐍 Alternative Installation (pip)
Use this only if pipx is not available. Install the tool in user scope to avoid system conflicts:

From a local clone:
bash
Copy code
git clone https://github.com/AdmGenSameer/archpkg-helper.git
cd archpkg-helper
python3 -m pip install --user .
Or directly from GitHub:
bash
Copy code
python3 -m pip install --user git+https://github.com/AdmGenSameer/archpkg-helper.git
⚠️ If your system enforces PEP 668 protections, you might see errors. To override:

bash
Copy code
python3 -m pip install --break-system-packages .
However, using pipx is strongly recommended instead of bypassing system protections.

🚀 Usage
After installation, the CLI will be available as:

bash
Copy code
archpkg
Common examples:
bash
Copy code
# 🔍 Search for a package
archpkg search <package-name>

# 📦 Get install command(s)
archpkg install <package-name>

# ❌ Get uninstall command(s)
archpkg remove <package-name>
You can also run:

bash
Copy code
archpkg --help
archpkg --version
Replace <package-name> with the software you want (e.g. vlc, neofetch, etc.).

📁 File Structure
Project layout overview:

bash
Copy code
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
📝 Some build folders appear only after running packaging/install commands.

🤝 Contributing
We welcome contributions from everyone! To contribute:

Fork the repository

Create a branch

bash
Copy code
git checkout -b feature/my-feature
Make your changes

Commit with a clear message

bash
Copy code
git commit -m "Add: my new feature"
Push to your fork

Open a Pull Request

You can also open issues for bugs or feature suggestions.

📄 License
This project is licensed under the Apache License 2.0.