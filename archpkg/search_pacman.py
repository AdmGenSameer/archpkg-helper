# search_pacman.py

import subprocess

def search_pacman(query):
    """
    Searches official Arch Linux repositories using the 'pacman -Ss' command.
    Returns a list of (name, description, 'pacman') tuples, or an empty list on error.
    """
    try:
        output = subprocess.check_output(["pacman", "-Ss", query], text=True)
    except subprocess.CalledProcessError:
        return []

    results = []
    lines = output.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if "/" in line:
            # Example: extra/firefox 115.0.1-1
            parts = line.split()
            if len(parts) >= 2:
                pkg_full = parts[0]  # 'extra/firefox'
                pkg_name = pkg_full.split("/")[-1]
                desc = lines[i + 1].strip() if i + 1 < len(lines) else ""
                results.append((pkg_name, desc, "pacman"))
            i += 2
        else:
            i += 1
    return results
