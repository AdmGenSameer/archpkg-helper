import subprocess

def search_flatpak(query):
    """
    Searches for applications in configured Flatpak remotes (like Flathub).
    Returns a list of tuples in the format (app_id, name, 'Flatpak'), where:
        - app_id: the Flatpak application ID
        - name: the application name
        - 'Flatpak': the source identifier
    Returns an empty list on error.
    """
    try:
        result = subprocess.run(['flatpak', 'search', query], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        output = result.stdout.decode().strip().split('\n')

        packages = []
        for line in output[1:]:
            cols = line.split()
            if len(cols) >= 3:
                app_id = cols[-2]
                name = ' '.join(cols[:-2])
                packages.append((app_id, name, 'Flatpak'))
        return packages
    except Exception as e:
        return []
