#!/bin/bash
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
else
    # For Fedora, Ubuntu/Debian and other distros
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
    echo "[!] pipx installation failed. Please install it manually for your distribution."
    exit 1
fi

# ------------------------------
# Step 6: Install ArchPkg CLI
# ------------------------------
if ! command -v archpkg &> /dev/null; then
    echo "[*] Installing ArchPkg CLI via pipx..."
    pipx install .
else
    echo "[*] ArchPkg CLI is already installed. Use '--force' to reinstall."
fi

# ------------------------------
# Step 7: Completion message
# ------------------------------
echo "[✔] Universal installation complete! Run 'archpkg --help' to verify."

