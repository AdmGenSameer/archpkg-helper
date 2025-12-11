#!/bin/bash
# Ultra-fault-tolerant ArchPkg installer
set -e

echo "[*] Starting universal installation of ArchPkg CLI..."

##############################################
# 0. Detect if running as root — disable sudo
##############################################
if [ "$(id -u)" -eq 0 ]; then
    echo "[*] Running as root → disabling all sudo usage"
    SUDO=""
else
    SUDO="sudo"
fi

##############################################
# 1. Detect distro
##############################################
if [ ! -f /etc/os-release ]; then
    echo "[!] Cannot detect distro (missing /etc/os-release). Exiting."
    exit 1
fi

. /etc/os-release
DISTRO=$ID
echo "[*] Detected Linux distro: $NAME ($DISTRO)"

case "$DISTRO" in
    # Fedora variants
    bluefin|nobara|ultramarine|silverblue|fedora*)
        DISTRO="fedora"
        echo "[*] Normalized to Fedora-based."
        ;;
    # Arch variants
    endeavouros|manjaro|archcraft|arch*)
        DISTRO="arch"
        echo "[*] Normalized to Arch-based."
        ;;
    # Debian/Ubuntu variants
    pop|pop_os|ubuntu|debian*)
        DISTRO="debian"
        echo "[*] Normalized to Debian/Ubuntu-based."
        ;;
    opensuse*|suse*)
        DISTRO="opensuse"
        echo "[*] Normalized to openSUSE-based."
        ;;
    *)
        echo "[!] Unknown distro → defaulting to Fedora-based"
        DISTRO="fedora"
        ;;
esac

##############################################
# 2. Package install helper (fault tolerant)
##############################################
install_pkg() {
    pkg="$1"
    echo "[*] Ensuring $pkg is installed…"

    case "$DISTRO" in
        debian)
            dpkg -s "$pkg" >/dev/null 2>&1 && return 0
            $SUDO apt-get update -y >/dev/null 2>&1 || true
            $SUDO apt-get install -y "$pkg" >/dev/null 2>&1 || true
            ;;
        fedora)
            rpm -q "$pkg" >/dev/null 2>&1 && return 0
            $SUDO dnf install -y "$pkg" >/dev/null 2>&1 || true
            ;;
        arch)
            pacman -Qi "$pkg" >/dev/null 2>&1 && return 0
            $SUDO pacman -Sy --noconfirm "$pkg" >/dev/null 2>&1 || true
            ;;
        opensuse)
            rpm -q "$pkg" >/dev/null 2>&1 && return 0
            $SUDO zypper install -y "$pkg" >/dev/null 2>&1 || true
            ;;
    esac
}

##############################################
# 3. Ensure Python, pip & venv exist
##############################################
fix_python() {
    echo "[*] Ensuring python3, pip and venv are available…"

    # python3
    if ! command -v python3 >/dev/null 2>&1; then
        install_pkg python3
    fi

    # pip
    if ! python3 -m pip --version >/dev/null 2>&1; then
        install_pkg python3-pip
    fi

    # venv
    if ! python3 -m venv --help >/dev/null 2>&1; then
        install_pkg python3-venv
    fi

    # final fallback
    if ! command -v python3 >/dev/null; then
        echo "[!] Python3 still missing — installer cannot continue."
        exit 1
    fi
}

fix_python

##############################################
# 4. Install pipx (with multiple fallbacks)
##############################################
echo "[*] Ensuring pipx is installed…"

install_pipx_system() {
    case "$DISTRO" in
        debian)
            install_pkg pipx
            ;;
        fedora)
            install_pkg pipx
            ;;
        arch)
            install_pkg python-pipx
            ;;
        opensuse)
            install_pkg python3-pipx
            ;;
    esac
}

if ! command -v pipx >/dev/null 2>&1; then
    echo "[*] Trying system installation of pipx…"
    install_pipx_system
fi

if ! command -v pipx >/dev/null 2>&1; then
    echo "[!] System pipx not available → falling back to pip install..."
    python3 -m pip install --user pipx >/dev/null 2>&1 || true
    export PATH="$HOME/.local/bin:$PATH"
fi

if ! command -v pipx >/dev/null 2>&1; then
    echo "[!] pipx installation failed."
    echo "    Try manually running:"
    echo "        python3 -m pip install --user pipx"
    exit 1
fi

echo "[*] pipx installed successfully."
pipx ensurepath >/dev/null 2>&1 || true

##############################################
# 5. Install or update ArchPkg CLI
##############################################
if ! command -v archpkg >/dev/null 2>&1; then
    echo "[*] Installing ArchPkg CLI..."
    pipx install git+https://github.com/AdmGenSameer/archpkg-helper.git || {
        echo "[!] pipx install failed — retrying with --force"
        pipx install --force git+https://github.com/AdmGenSameer/archpkg-helper.git
    }
else
    echo "[*] ArchPkg already installed → upgrading..."
    pipx install --force git+https://github.com/AdmGenSameer/archpkg-helper.git
fi

##############################################
# 6. Done
##############################################
echo "[✔] Installation complete! Run:  archpkg --help"
