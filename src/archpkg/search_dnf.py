# search_dnf.py
import subprocess

def search_dnf(query):
    try:
        result = subprocess.run(["dnf", "search", query], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split("\n")
        packages = []
        for line in lines:
            if line.startswith(" ") and ":" in line:
                name, desc = line.strip().split(":", 1)
                packages.append((name.strip(), desc.strip(), "DNF"))
        return packages
    except Exception:
        return []
