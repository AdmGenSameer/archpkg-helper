#!/bin/bash
# Note: set -e is used but we handle critical failures explicitly with fallbacks
set -e

# ------------------------------
# Header
# ------------------------------
echo "[*] Starting universal installation of ArchPkg CLI..."

# ------------------------------
# Step 1: Detect Linux distro
# ------------------------------

if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
    echo "[*] Detected Linux distro: $NAME ($DISTRO)"

    # Map unconventional distros to their base
    case "$DISTRO" in
        bluefin|nobara|ultramarine|silverblue|fedora*)
            DISTRO="fedora"
            echo "[*] Treating $ID as Fedora-based."
            ;;
        omarchyos|endeavouros|manjaro|archcraft|arch*)
            DISTRO="arch"
            echo "[*] Treating $ID as Arch-based."
            ;;
        pop|pop_os|ubuntu|debian*)
            DISTRO="ubuntu"
            echo "[*] Treating $ID as Ubuntu/Debian-based."
            ;;
        opensuse|opensuse-tumbleweed|opensuse-leap|suse*)
            DISTRO="opensuse"
            echo "[*] Treating $ID as openSUSE-based."
            ;;
        *)
            echo "[!] Unrecognized distro: $ID. Defaulting to Fedora (dnf)."
            DISTRO="fedora"
            ;;
    esac
else
    echo "[!] Cannot detect Linux distribution. Exiting."
    exit 1
fi

# ------------------------------
# Step 2: Define essential system dependencies
# ------------------------------
if [ "$DISTRO" = "arch" ]; then
    DEPENDENCIES=(python python-pip python-pipx git curl wget)
elif [ "$DISTRO" = "opensuse" ]; then
    # openSUSE includes venv in the base python3 package
    DEPENDENCIES=(python3 python3-pip python3-pipx git curl wget)
elif [ "$DISTRO" = "fedora" ]; then
    # Fedora uses 'pipx' package name (not python3-pipx)
    DEPENDENCIES=(python3 python3-pip pipx python3-venv git curl wget)
else
    # For Ubuntu/Debian and other distros
    DEPENDENCIES=(python3 python3-pip python3-pipx python3-venv git curl wget)
fi

install_package() {
    PACKAGE=$1
    echo "[*] Installing $PACKAGE if missing..."
    case "$DISTRO" in
        ubuntu|debian)
            dpkg -s "$PACKAGE" &> /dev/null || sudo apt install -y "$PACKAGE"
            ;;
        fedora)
            rpm -q "$PACKAGE" &> /dev/null || sudo dnf install -y "$PACKAGE"
            ;;
        arch)
            pacman -Qi "$PACKAGE" &> /dev/null || sudo pacman -S --noconfirm "$PACKAGE"
            ;;
        opensuse)
            rpm -q "$PACKAGE" &> /dev/null || sudo zypper install -y "$PACKAGE"
            ;;
        *)
            echo "[!] Unsupported Linux distro: $DISTRO"
            exit 1
            ;;
    esac
}

# ------------------------------
# Step 4: Install system dependencies
# ------------------------------
echo "[*] Checking and installing system dependencies..."
for pkg in "${DEPENDENCIES[@]}"; do
    install_package "$pkg"
done

# ------------------------------
# Step 5: Ensure pipx path is configured
# ------------------------------
if command -v pipx &> /dev/null; then
    echo "[*] pipx is installed. Ensuring PATH is configured..."
    pipx ensurepath
else
    echo "[!] pipx not found after system package installation. Attempting fallback to pip install..."
    
    # Temporarily disable set -e to handle pip install failures gracefully
    set +e
    python3 -m pip install --user pipx
    PIP_INSTALL_STATUS=$?
    set -e
    
    # Check if pip install succeeded
    if [ $PIP_INSTALL_STATUS -eq 0 ]; then
        echo "[*] pipx installed successfully via pip. Ensuring PATH is configured..."
        python3 -m pipx ensurepath
        
        # Add pipx to PATH for current session
        export PATH="$HOME/.local/bin:$PATH"
        
        if command -v pipx &> /dev/null; then
            echo "[✔] pipx is now available!"
        else
            echo "[!] pipx installed but not in PATH. You may need to restart your shell or run:"
            echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
            echo "    Then run this installer again."
            exit 1
        fi
    else
        echo ""
        echo "[!] Failed to install pipx via both system package manager and pip."
        echo ""
        echo "Troubleshooting steps:"
        if [ "$DISTRO" = "fedora" ]; then
            echo "  For Fedora/RHEL-based systems:"
            echo "    1. Try: sudo dnf install -y pipx"
            echo "    2. If that fails, ensure EPEL or standard repos are enabled"
            echo "    3. Or install manually: python3 -m pip install --user pipx"
        else
            echo "  1. Install pipx manually using your package manager"
            echo "  2. Or run: python3 -m pip install --user pipx"
        fi
        echo "  3. Then run: pipx ensurepath"
        echo "  4. Restart your shell and try this installer again"
        echo ""
        exit 1
    fi
fi

# ------------------------------
# Step 6: Install ArchPkg CLI
# ------------------------------
if ! command -v archpkg &> /dev/null; then
    echo "[*] Installing ArchPkg CLI via pipx..."
    pipx install git+https://github.com/AdmGenSameer/archpkg-helper.git
else
    echo "[*] ArchPkg CLI is already installed. Upgrading to latest version..."
    pipx install --force git+https://github.com/AdmGenSameer/archpkg-helper.git
fi

# ------------------------------
# Step 7: Completion message
# ------------------------------
echo "[✔] Universal installation complete! Run 'archpkg --help' to verify."

