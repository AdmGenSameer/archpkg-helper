# search_snap.py
import subprocess


def search_snap(query):
    """
    Searches for packages in the Snap Store using the 'snap find' command.
    Returns a list of (name, description, 'Snap') tuples, or an empty list on error.
    """
    try:
        result = subprocess.run(["snap", "find", query], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split("\n")[1:]  # skip header
        packages = []
        for line in lines:
            parts = line.split()
            if len(parts) < 2:
                continue
            name = parts[0]
            desc = " ".join(parts[1:])
            packages.append((name.strip(), desc.strip(), "Snap"))
        return packages
    except Exception:
        return []
