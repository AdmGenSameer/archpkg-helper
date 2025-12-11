#!/bin/bash
# Ultra-fault-tolerant ArchPkg installer
set -e

echo "[*] Starting universal installation of ArchPkg CLI..."

##############################################
# 0. Detect if running as root — disable sudo
##############################################
if [ "$(id -u)" -eq 0 ]; then
    echo "[*] Running as root → disabling sudo"
    SUDO=""
else
    SUDO="sudo"
fi

##############################################
# 1. Detect distro
##############################################
if [ ! -f /etc/os-release ]; then
    echo "[!] Cannot detect distro. Exiting."
    exit 1
fi

. /etc/os-release
DISTRO=$ID
echo "[*] Detected Linux distro: $NAME ($DISTRO)"

case "$DISTRO" in
    bluefin|nobara|ultramarine|silverblue|fedora*)
        DISTRO="fedora"
        echo "[*] Normalized to Fedora-based."
        ;;
    endeavouros|manjaro|archcraft|arch*)
        DISTRO="arch"
        echo "[*] Normalized to Arch-based."
        ;;
    pop|pop_os|ubuntu|debian*)
        DISTRO="debian"
        echo "[*] Normalized to Debian/Ubuntu-based."
        ;;
    opensuse*|suse*)
        DISTRO="opensuse"
        echo "[*] Normalized to openSUSE-based."
        ;;
    *)
        echo "[!] Unknown distro → defaulting to Fedora"
        DISTRO="fedora"
        ;;
esac

##############################################
# 2. Select dependency packages
##############################################
# Minimal set needed everywhere
COMMON_PKGS=(git curl wget ca-certificates)

case "$DISTRO" in
    debian)
        DEPS=(python3 python3-pip python3-venv pipx "${COMMON_PKGS[@]}")
        ;;
    fedora)
        DEPS=(python3 python3-pip python3-virtualenv pipx "${COMMON_PKGS[@]}")
        ;;
    arch)
        DEPS=(python python-pip python-pipx python-virtualenv "${COMMON_PKGS[@]}")
        ;;
    opensuse)
        DEPS=(python3 python3-pip python3-pipx python3-virtualenv "${COMMON_PKGS[@]}")
        ;;
esac

##############################################
# 3. Fault-tolerant package installer
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
# 4. Install all required packages
##############################################
echo "[*] Installing system dependencies…"

for pkg in "${DEPS[@]}"; do
    install_pkg "$pkg"
done

##############################################
# 5. Ensure python, pip, venv work
##############################################
echo "[*] Validating Python environment…"

if ! command -v python3 >/dev/null; then
    echo "[!] python3 missing — installer cannot continue."
    exit 1
fi

if ! python3 -m pip --version >/dev/null 2>&1; then
    echo "[!] pip missing — attempting install"
    install_pkg python3-pip
fi

# venv must work
python3 -m venv /tmp/testvenv >/dev/null 2>&1 || install_pkg python3-venv || true

##############################################
# 6. Ensure pipx exists
##############################################
echo "[*] Ensuring pipx is installed…"

if ! command -v pipx >/dev/null 2>&1; then
    echo "[*] pipx missing → installing with pip fallback…"
    python3 -m pip install --user pipx >/dev/null 2>&1 || true
    export PATH="$HOME/.local/bin:$PATH"
fi

if ! command -v pipx >/dev/null; then
    echo "[!] pipx installation failed — cannot continue."
    exit 1
fi

pipx ensurepath >/dev/null 2>&1 || true

##############################################
# 7. Install ArchPkg (now git exists)
##############################################
echo "[*] Installing ArchPkg CLI…"

if ! pipx install git+https://github.com/AdmGenSameer/archpkg-helper.git; then
    echo "[!] pipx install failed → retrying with --force"
    pipx install --force git+https://github.com/AdmGenSameer/archpkg-helper.git
fi

##############################################
# DONE
##############################################
echo "[✔] ArchPkg installation complete!"
echo "    Run: archpkg --help"
