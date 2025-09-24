import subprocess

def search_flatpak(query):
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
