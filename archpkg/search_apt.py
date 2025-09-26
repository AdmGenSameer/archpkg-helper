# search_apt.py
import subprocess

def search_apt(query):
    """
    Searches APT repositories for a package by executing the 'apt-cache search' command.
    Returns a list of (name, description, 'APT') tuples, or an empty list on error.
    """
    try:
        result = subprocess.run(["apt-cache", "search", query], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split("\n")
        packages = []
        for line in lines:
            if ' - ' in line:
                name, desc = line.split(" - ", 1)
                packages.append((name.strip(), desc.strip(), "APT"))
        return packages
    except Exception:
        return []