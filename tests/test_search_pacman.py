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

@patch('subprocess.check_output')
def test_search_pacman_parsing(mock_check_output):
    """Test that the search_pacman function correctly parses pacman output."""
    mock_check_output.return_value = PACMAN_OUTPUT

    results = search_pacman("any_query")

    # Verify that subprocess.check_output was called correctly
    mock_check_output.assert_called_with(["pacman", "-Ss", "any_query"], text=True)

    # Verify the parsed results
    assert len(results) == 2
    assert results[0] == ("pacman", "A library-based package manager with dependency support", "pacman")
    assert results[1] == ("package-query", "Query ALPM and AUR databases", "pacman")
