import requests

def search_aur(query):
    url = f"https://aur.archlinux.org/rpc/?v=5&type=search&arg={query}"
    try:
        response = requests.get(url)
        results = response.json().get("results", [])
        return [(pkg['Name'], pkg['Description'], 'AUR') for pkg in results]
    except Exception as e:
        return []
