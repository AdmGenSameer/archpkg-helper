def generate_command(pkg_name, source):
    if source == 'Pacman':
        return f"sudo pacman -S {pkg_name}"
    elif source == 'AUR':
        return f"yay -S {pkg_name}"
    elif source == 'Flatpak':
        return f"flatpak install flathub {pkg_name}"
    return ""
