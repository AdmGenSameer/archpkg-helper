import requests

def search_aur(query):
    """
    Searches the Arch User Repository (AUR) for a given package.
    Returns a list of (name, description, 'AUR') tuples, or an empty list on error.
    """
    url = f"https://aur.archlinux.org/rpc/?v=5&type=search&arg={query}"
    try:
        response = requests.get(url)
        results = response.json().get("results", [])
        return [(pkg['Name'], pkg['Description'], 'AUR') for pkg in results]
    except Exception as e:
        return []
