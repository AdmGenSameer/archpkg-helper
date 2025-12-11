#!/usr/bin/env python3
"""
Web interface for archpkg-helper
"""

from flask import Flask, render_template, request, jsonify
import os
import subprocess
import logging
from archpkg.config import DISTRO_MAP
from archpkg.search_aur import search_aur
from archpkg.search_pacman import search_pacman
from archpkg.search_flatpak import search_flatpak
from archpkg.search_snap import search_snap
from archpkg.search_apt import search_apt
from archpkg.search_dnf import search_dnf
from archpkg.search_zypper import search_zypper
from archpkg.command_gen import generate_command
from archpkg.github_install import install_from_github, validate_github_url
from archpkg.installed_apps import add_installed_package, get_all_installed_packages, InstalledAppsManager, InstalledPackage
from archpkg.suggest import suggest_apps
import distro

# Set explicit template folder path
base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, 'templates')

app = Flask(__name__, template_folder=template_dir)
logger = logging.getLogger(__name__)

@app.route('/')
def home():
    """Home page with description of the tool"""
    return render_template('home.html')

@app.route('/search')
def search_page():
    """Search interface"""
    return render_template('search.html')

@app.route('/api/search')
def api_search():
    """API endpoint for package search with improved error handling and better relevance scoring"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Query parameter required'}), 400

    results = []
    unavailable_sources = []
    search_errors = {}

    # Helper function to search and collect results
    def search_and_append(search_func, source_name):
        try:
            logger.info(f"Searching {source_name} for: '{query}'")
            search_results = search_func(query)
            if search_results:
                logger.info(f"Found {len(search_results)} results from {source_name}")
            for name, desc, source in search_results:
                command = generate_command(name, source)
                results.append({
                    'name': name,
                    'description': desc or 'No description available',
                    'manager': source,
                    'command': command or 'Command not available',
                    'source_url': None  # Will be populated for GitHub fallback
                })
        except Exception as e:
            error_msg = str(e)
            logger.debug(f"{source_name} search failed: {error_msg}")
            unavailable_sources.append(source_name)
            search_errors[source_name] = error_msg

    # Detect the system and prioritize available package managers
    detected_distro = distro.id().lower()
    logger.info(f"Detected distro: {detected_distro}")

    # Search in priority order based on distro
    if 'arch' in detected_distro or 'manjaro' in detected_distro:
        search_and_append(search_pacman, 'Pacman')
        search_and_append(search_aur, 'AUR')
    elif 'debian' in detected_distro or 'ubuntu' in detected_distro:
        search_and_append(search_apt, 'APT')
    elif 'fedora' in detected_distro or 'rhel' in detected_distro:
        search_and_append(search_dnf, 'DNF')
    elif 'opensuse' in detected_distro:
        search_and_append(search_zypper, 'Zypper')
    
    # Always search Flatpak and Snap (available on most distros)
    search_and_append(search_flatpak, 'Flatpak')
    search_and_append(search_snap, 'Snap')

    # Improved relevance scoring
    def score_package(pkg):
        query_lower = query.lower()
        name_lower = pkg['name'].lower()
        
        # Exact match gets highest score
        if name_lower == query_lower:
            return 1000
        # Prefix match
        if name_lower.startswith(query_lower):
            return 900
        # Contains match
        if query_lower in name_lower:
            return 800
        # Partial word match
        query_words = set(query_lower.split())
        name_words = set(name_lower.replace('-', ' ').split())
        matching_words = len(query_words & name_words)
        return matching_words * 100
    
    # Sort by relevance score
    for result in results:
        result['score'] = score_package(result)
    results.sort(key=lambda x: (-x['score'], len(x['name'])))

    # Remove score before sending to client
    for result in results:
        del result['score']

    response_data = {
        'results': results[:50],  # Limit results
        'query': query,
        'total_found': len(results),
        'distro': detected_distro
    }
    
    # Add information about unavailable sources with helpful guidance
    if unavailable_sources:
        response_data['unavailable_sources'] = unavailable_sources
        response_data['suggestions'] = {}
        
        # Provide installation guidance for unavailable tools
        if 'Snap' in unavailable_sources:
            response_data['suggestions']['snap'] = {
                'message': 'Snap not available',
                'install_command': 'sudo apt install snapd' if 'ubuntu' in detected_distro or 'debian' in detected_distro else 'Check your distro docs',
                'help_text': 'Install Snap to access thousands of containerized packages'
            }
        
        if 'Flatpak' in unavailable_sources:
            response_data['suggestions']['flatpak'] = {
                'message': 'Flatpak not available',
                'install_command': 'sudo apt install flatpak' if 'ubuntu' in detected_distro or 'debian' in detected_distro else 'Check your distro docs',
                'help_text': 'Install Flatpak to access universal Linux applications'
            }
        
        logger.info(f"Unavailable sources: {', '.join(unavailable_sources)}")
    
    if len(results) == 0:
        response_data['message'] = "No packages found in available repositories. Try installing Snap or Flatpak, or search GitHub for source code."

    return jsonify(response_data)

@app.route('/api/install', methods=['POST'])
def api_install():
    """API endpoint for package installation"""
    data = request.get_json()
    package_name = data.get('name', '').strip()
    package_manager = data.get('manager', '').strip()
    
    if not package_name or not package_manager:
        return jsonify({'error': 'Package name and manager required'}), 400
    
    try:
        command = generate_command(package_name, package_manager)
        if not command:
            return jsonify({'error': 'Could not generate install command'}), 400
        
        # Track the package installation
        pkg = InstalledPackage(
            name=package_name,
            source=package_manager,
            install_method='web'
        )
        add_installed_package(pkg)
        
        logger.info(f"Package '{package_name}' from {package_manager} marked for installation")
        
        return jsonify({
            'success': True,
            'package': package_name,
            'manager': package_manager,
            'command': command,
            'message': f'Install command for {package_name} generated. Use: {command}'
        })
    except Exception as e:
        logger.error(f"Installation endpoint error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/github-search', methods=['GET'])
def api_github_search():
    """Search for packages on GitHub when not found in repos"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Query parameter required'}), 400
    
    try:
        # Try to fetch GitHub search results
        import requests
        headers = {'Accept': 'application/vnd.github.v3+json'}
        github_url = f"https://api.github.com/search/repositories?q={query}+in:name+language:python+language:javascript+language:rust+language:go&sort=stars&order=desc&per_page=10"
        
        logger.info(f"Searching GitHub for: {query}")
        response = requests.get(github_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            github_data = response.json()
            results = []
            for repo in github_data.get('items', [])[:10]:
                results.append({
                    'name': repo['name'],
                    'description': repo.get('description', 'No description'),
                    'url': repo['clone_url'],
                    'stars': repo['stargazers_count'],
                    'language': repo.get('language', 'Unknown'),
                    'manager': 'GitHub',
                    'source_url': repo['html_url']
                })
            
            return jsonify({
                'results': results,
                'query': query,
                'message': 'Results from GitHub. You can install from source automatically.'
            })
        else:
            return jsonify({'error': 'GitHub search rate limited'}), 429
            
    except Exception as e:
        logger.error(f"GitHub search error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/github-install', methods=['POST'])
def api_github_install():
    """Install package from GitHub repository with automatic build"""
    data = request.get_json()
    repo_url = data.get('url', '').strip()
    package_name = data.get('name', '').strip()
    
    if not repo_url:
        return jsonify({'error': 'Repository URL required'}), 400
    
    try:
        logger.info(f"Starting GitHub installation for: {repo_url}")
        
        # Validate and install from GitHub
        if validate_github_url(repo_url):
            success, message, details = install_from_github(repo_url)
            
            if success:
                # Track the installation
                pkg_name = package_name or repo_url.split('/')[-1].replace('.git', '')
                pkg = InstalledPackage(
                    name=pkg_name,
                    source='GitHub',
                    install_method='github'
                )
                add_installed_package(pkg)
                
                return jsonify({
                    'success': True,
                    'package': pkg_name,
                    'manager': 'GitHub',
                    'message': message,
                    'details': details
                })
            else:
                return jsonify({
                    'success': False,
                    'error': message,
                    'details': details
                }), 400
        else:
            return jsonify({'error': 'Invalid GitHub repository URL'}), 400
            
    except Exception as e:
        logger.error(f"GitHub installation error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/installed')
def installed_apps_page():
    """Page to manage installed packages"""
    return render_template('installed.html')

@app.route('/api/installed-packages', methods=['GET'])
def api_get_installed_packages():
    """Get list of installed packages tracked by archpkg"""
    try:
        packages = get_all_installed_packages()
        return jsonify({
            'packages': packages,
            'total': len(packages)
        })
    except Exception as e:
        logger.error(f"Error fetching installed packages: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/check-updates', methods=['POST'])
def api_check_updates():
    """Check for updates for installed packages"""
    data = request.get_json()
    package_names = data.get('packages', [])
    
    if not package_names:
        return jsonify({'error': 'Package names required'}), 400
    
    try:
        # This would integrate with the update manager
        # For now, we return a basic response
        return jsonify({
            'message': 'Update check started',
            'packages': package_names,
            'updates_available': []
        })
    except Exception as e:
        logger.error(f"Update check error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)