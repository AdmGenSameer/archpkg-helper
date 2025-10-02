#!/bin/bash
set -e  # Stop on any error

echo "[*] Starting universal installation of ArchPkg CLI..."

# -----------------------
# Detect OS
# -----------------------
OS="$(uname -s)"
ARCH="$(uname -m)"
echo "[*] Detected OS: $OS"
echo "[*] Detected Architecture: $ARCH"

# -----------------------
# Function to detect python
# -----------------------
detect_python() {
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN=python3
        PIP_BIN=pip3
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN=python
        PIP_BIN=pip
    else
        echo "[!] Python not found. Please install Python 3."
        exit 1
    fi
    echo "[*] Using Python: $($PYTHON_BIN --version)"
    echo "[*] Using Pip: $($PIP_BIN --version)"
}

# -----------------------
# Linux Installer
# -----------------------
install_linux() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        DISTRO=$ID
    else
        echo "[!] Cannot detect Linux distribution."
        exit 1
    fi

    echo "[*] Detected Linux distro: $DISTRO"

    case "$DISTRO" in
        ubuntu|debian)
            sudo apt update && sudo apt install -y git python3 python3-pip
            ;;
        fedora)
            sudo dnf install -y git python3 python3-pip
            ;;
        arch)
            sudo pacman -Syu --noconfirm git python python-pip
            ;;
        *)
            echo "[*] Unknown distro. Attempting generic package manager..."
            if command -v apt >/dev/null 2>&1; then
                sudo apt update && sudo apt install -y git python3 python3-pip
            elif command -v dnf >/dev/null 2>&1; then
                sudo dnf install -y git python3 python3-pip
            elif command -v pacman >/dev/null 2>&1; then
                sudo pacman -Syu --noconfirm git python python-pip
            else
                echo "[!] No supported package manager found. Install git and python manually."
                exit 1
            fi
            ;;
    esac
}

# -----------------------
# macOS Installer
# -----------------------
install_macos() {
    if ! command -v brew >/dev/null 2>&1; then
        echo "[*] Homebrew not found. Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install git python3
}

# -----------------------
# Windows Installer (Git Bash/WSL)
# -----------------------
install_windows() {
    echo "[*] Windows detected. Make sure Git Bash or WSL is used."
    if ! command -v git >/dev/null 2>&1; then
        echo "[!] Git not found. Please install Git: https://git-scm.com/download/win"
    fi
    if ! command -v python >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
        echo "[!] Python not found. Please install Python: https://www.python.org/downloads/windows/"
    fi
}

# -----------------------
# Run appropriate installer
# -----------------------
case "$OS" in
    Linux)
        install_linux
        ;;
    Darwin)
        install_macos
        ;;
    MINGW*|MSYS*|CYGWIN*)
        install_windows
        ;;
    *)
        echo "[!] Unsupported OS: $OS"
        exit 1
        ;;
esac

# -----------------------
# Detect Python and Pip
# -----------------------
detect_python

# -----------------------
# Python dependencies
# -----------------------
packages=("requests" "rich" "ty")  # Add more here
for pkg in "${packages[@]}"; do
    echo "[*] Installing Python package: $pkg"
    if ! $PIP_BIN install "$pkg"; then
        echo "[!] Failed to install $pkg from PyPI."
        echo "    You can try installing it manually from GitHub if available:"
        echo "    pip install git+https://github.com/<username>/$pkg.git"
    fi
done

echo "[*] ArchPkg CLI installation completed successfully!"

