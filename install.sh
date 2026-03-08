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
        DEPS=(python3 python3-pip python3-venv pipx python3-pyqt5 "${COMMON_PKGS[@]}")
        ;;
    fedora)
        DEPS=(python3 python3-pip python3-virtualenv pipx python3-qt5 "${COMMON_PKGS[@]}")
        ;;
    arch)
        DEPS=(python python-pip python-pipx python-virtualenv python-pyqt5 base-devel "${COMMON_PKGS[@]}")
        ;;
    opensuse)
        DEPS=(python3 python3-pip python3-pipx python3-virtualenv python3-qt5 "${COMMON_PKGS[@]}")
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
# 4.5 Ensure paru is available on Arch
##############################################
if [ "$DISTRO" = "arch" ]; then
    echo "[*] Checking for paru (recommended AUR helper)…"
    if ! command -v paru >/dev/null 2>&1; then
        echo "[*] paru not found. Attempting installation from AUR…"
        if ! command -v git >/dev/null 2>&1; then
            install_pkg git
        fi

        PARU_BUILD_DIR="/tmp/paru-bin-build"
        rm -rf "$PARU_BUILD_DIR"
        git clone https://aur.archlinux.org/paru-bin.git "$PARU_BUILD_DIR" >/dev/null 2>&1 || true

        if [ -d "$PARU_BUILD_DIR" ]; then
            pushd "$PARU_BUILD_DIR" >/dev/null
            if [ -n "$SUDO" ]; then
                sudo -u "$USER" makepkg -si --noconfirm >/dev/null 2>&1 || true
            else
                makepkg -si --noconfirm >/dev/null 2>&1 || true
            fi
            popd >/dev/null
        fi

        if command -v paru >/dev/null 2>&1; then
            echo "[✔] paru installed successfully."
        else
            echo "[!] paru installation failed. Continuing, but Arch workflows may be limited."
        fi
    else
        echo "[✔] paru is already installed."
    fi
fi

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
# 8. Profile setup (normal vs advanced)
##############################################
if [ "$DISTRO" = "arch" ]; then
    echo ""
    echo "[*] Choose your archpkg profile:"
    echo "    1) normal (recommended) - archpkg handles updates/news/trust checks automatically"
    echo "    2) advanced - full manual control"
    read -r -p "Enter choice [1/2] (default: 1): " ARCHPKG_PROFILE_CHOICE

    if [ "$ARCHPKG_PROFILE_CHOICE" = "2" ]; then
        ARCHPKG_USER_MODE="advanced"
    else
        ARCHPKG_USER_MODE="normal"
    fi

    mkdir -p "$HOME/.archpkg"
    if [ "$ARCHPKG_USER_MODE" = "advanced" ]; then
        cat > "$HOME/.archpkg/config.json" <<EOF
{
  "user_mode": "advanced",
  "auto_update_enabled": false,
  "auto_update_mode": "manual",
  "update_check_interval_hours": 24,
  "background_download_enabled": true,
  "notification_enabled": true,
  "auto_handle_arch_news": false,
  "auto_review_aur_trust": false,
  "auto_snapshot_before_update": false,
  "proactive_system_advice": false
}
EOF
    else
        cat > "$HOME/.archpkg/config.json" <<EOF
{
  "user_mode": "normal",
  "auto_update_enabled": true,
  "auto_update_mode": "automatic",
  "update_check_interval_hours": 24,
  "background_download_enabled": true,
  "notification_enabled": true,
  "auto_handle_arch_news": true,
  "auto_review_aur_trust": true,
  "auto_snapshot_before_update": true,
  "proactive_system_advice": true
}
EOF
    fi

    echo "[✔] Profile configured: $ARCHPKG_USER_MODE"
fi

##############################################
# DONE
##############################################
echo "[✔] ArchPkg installation complete!"
echo ""
echo "Quick start:"
echo "    archpkg --help       # Show all CLI commands"
echo "    archpkg gui          # Launch native desktop GUI"
echo "    archpkg search <pkg> # Search for packages"
echo ""
echo "Both CLI and GUI are now available!"
