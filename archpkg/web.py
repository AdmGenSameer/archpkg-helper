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

app = Flask(__name__)

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
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Query parameter required'}), 400

    results = []

    # Search across all package managers
    try:
        pacman_results = search_pacman(query)
        for name, desc, source in pacman_results:
            command = generate_command(name, source)
            results.append({
                'name': name,
                'description': desc or 'No description available',
                'manager': source,
                'command': command or 'Command not available'
            })
    except Exception:
        pass

    try:
        aur_results = search_aur(query)
        for name, desc, source in aur_results:
            command = generate_command(name, source)
            results.append({
                'name': name,
                'description': desc or 'No description available',
                'manager': source,
                'command': command or 'Command not available'
            })
    except Exception:
        pass

    try:
        flatpak_results = search_flatpak(query)
        for name, desc, source in flatpak_results:
            command = generate_command(name, source)
            results.append({
                'name': name,
                'description': desc or 'No description available',
                'manager': source,
                'command': command or 'Command not available'
            })
    except Exception:
        pass

    try:
        snap_results = search_snap(query)
        for name, desc, source in snap_results:
            command = generate_command(name, source)
            results.append({
                'name': name,
                'description': desc or 'No description available',
                'manager': source,
                'command': command or 'Command not available'
            })
    except Exception:
        pass

    try:
        apt_results = search_apt(query)
        for name, desc, source in apt_results:
            command = generate_command(name, source)
            results.append({
                'name': name,
                'description': desc or 'No description available',
                'manager': source,
                'command': command or 'Command not available'
            })
    except Exception:
        pass

    try:
        dnf_results = search_dnf(query)
        for name, desc, source in dnf_results:
            command = generate_command(name, source)
            results.append({
                'name': name,
                'description': desc or 'No description available',
                'manager': source,
                'command': command or 'Command not available'
            })
    except Exception:
        pass

    # Sort by relevance (simple: prefer exact matches, then shorter names)
    results.sort(key=lambda x: (x['name'].lower().find(query.lower()), len(x['name'])))

    return jsonify({'results': results[:50]})  # Limit results

if __name__ == '__main__':
    app.run(debug=True)