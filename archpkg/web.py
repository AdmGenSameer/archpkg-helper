#!/usr/bin/env python3
"""
Web interface for archpkg-helper
"""

from flask import Flask, render_template, request, jsonify
import os
from archpkg.config import DISTRO_MAP
from archpkg.search_aur import search_aur
from archpkg.search_pacman import search_pacman
from archpkg.search_flatpak import search_flatpak
from archpkg.search_snap import search_snap
from archpkg.search_apt import search_apt
from archpkg.search_dnf import search_dnf
from archpkg.command_gen import generate_command

# Set explicit template folder path
base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, 'templates')

app = Flask(__name__, template_folder=template_dir)

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
    """API endpoint for package search"""
    import logging
    logger = logging.getLogger(__name__)
    
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Query parameter required'}), 400

    results = []
    unavailable_sources = []

    # Helper function to search and collect results
    def search_and_append(search_func, source_name):
        try:
            search_results = search_func(query)
            for name, desc, source in search_results:
                command = generate_command(name, source)
                results.append({
                    'name': name,
                    'description': desc or 'No description available',
                    'manager': source,
                    'command': command or 'Command not available'
                })
        except Exception as e:
            logger.debug(f"{source_name} search failed in web API: {e}")
            unavailable_sources.append(source_name)

    # Search across all package managers
    search_and_append(search_pacman, 'Pacman')
    search_and_append(search_aur, 'AUR')
    search_and_append(search_flatpak, 'Flatpak')
    search_and_append(search_snap, 'Snap')
    search_and_append(search_apt, 'APT')
    search_and_append(search_dnf, 'DNF')

    # Sort by relevance (simple: prefer exact matches, then shorter names)
    results.sort(key=lambda x: (x['name'].lower().find(query.lower()), len(x['name'])))

    response_data = {
        'results': results[:50],  # Limit results
        'query': query
    }
    
    # Add gentle message about unavailable sources if any
    if unavailable_sources and len(results) == 0:
        response_data['message'] = f"No results found. Some sources were unavailable: {', '.join(unavailable_sources)}"
    elif unavailable_sources:
        response_data['info'] = f"Note: Some sources unavailable: {', '.join(unavailable_sources)}"

    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True)