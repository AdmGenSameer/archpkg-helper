#!/bin/bash

echo "[*] Starting universal installation of ArchPkg CLI..."

# Detect platform
OS="$(uname -s)"

# -----------------------
# Linux
# -----------------------
if [[ "$OS" == "Linux" ]]; then
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        distro=$ID
    else
        echo "[!] Cannot detect Linux distribution."
        exit 1
    fi

    echo "[*] Detected Linux distro: $distro"

    case "$distro" in
        arch)
            echo "[*] Installing dependencies for Arch Linux..."
            sudo pacman -Sy --needed --noconfirm python python-pip git
            ;;
        ubuntu|debian)
            echo "[*] Installing dependencies for Ubuntu/Debian..."
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip git
            ;;
        fedora)
            echo "[*] Installing dependencies for Fedora..."
            sudo dnf install -y python3 python3-pip git
            ;;
        opensuse*|sles)
            echo "[*] Installing dependencies for openSUSE/SLES..."
            sudo zypper install -y python3 python3-pip git
            ;;
        alpine)
            echo "[*] Installing dependencies for Alpine Linux..."
            sudo apk add --no-cache python3 py3-pip git
            ;;
        *)
            echo "[!] Unsupported distro: $distro"
            echo ">>> Please install python3, pip, and git manually."
            exit 1
            ;;
    esac
fi

# -----------------------
# macOS
# -----------------------
if [[ "$OS" == "Darwin" ]]; then
    echo "[*] Detected macOS"
    if ! command -v brew &> /dev/null; then
        echo "[!] Homebrew not found. Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install python3 git
    echo "[*] Installing pip..."
    python3 -m ensurepip --upgrade
fi

# -----------------------
# Windows (Git Bash / WSL)
# -----------------------
if [[ "$OS" == "MINGW"* || "$OS" == "MSYS"* || "$OS" == "CYGWIN"* ]]; then
    echo "[*] Detected Windows"
    if command -v winget &> /dev/null; then
        echo "[*] Installing using winget..."
        winget install -e --id Python.Python.3
        winget install -e --id Git.Git
    elif command -v choco &> /dev/null; then
        echo "[*] Installing using Chocolatey..."
        choco install -y python git
    else
        echo "[!] No package manager found. Please install Python3, pip, and Git manually from:"
        echo "    - https://www.python.org/downloads/"
        echo "    - https://git-scm.com/downloads"
        exit 1
    fi
fi

echo "[*] Installation complete. You can now run ArchPkg CLI."

