import subprocess
from unittest.mock import patch
from archpkg.search_pacman import search_pacman

# Sample output from `pacman -Ss`
PACMAN_OUTPUT = """
core/pacman 6.0.2-6 [installed]
    A library-based package manager with dependency support
extra/package-query 1.9-2
    Query ALPM and AUR databases
"""

@patch('subprocess.run')
def test_search_pacman_parsing(mock_run):
    """Test that the search_pacman function correctly parses pacman output."""
    # Set up the mock to return a CompletedProcess-like object with stdout
    mock_run.return_value = subprocess.CompletedProcess(
        args=["pacman", "-Ss", "any_query"],
        returncode=0,
        stdout=PACMAN_OUTPUT
    )

    results = search_pacman("any_query")

    # Verify that subprocess.run was called correctly
    mock_run.assert_called_with(["pacman", "-Ss", "any_query"], text=True, capture_output=True)

    # Verify the parsed results
    assert len(results) == 2
    assert results[0] == ("pacman", "A library-based package manager with dependency support", "Pacman")
    assert results[1] == ("package-query", "Query ALPM and AUR databases", "Pacman")
