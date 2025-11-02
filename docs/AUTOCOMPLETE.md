# Archpkg Autocomplete Documentation

This document describes the autocomplete functionality for archpkg, which provides intelligent inline suggestions for package names as you type.

## Features

- **Trie-based prefix search**: Fast O(k) lookup where k is the input length
- **Abbreviation matching**: Type `vsc` to find `visual-studio-code`
- **Alias mapping**: Common shortcuts like `chrome` → `google-chrome`
- **Frequency-based ranking**: Recently used packages appear first
- **Context-aware suggestions**: Different suggestions for install vs remove
- **Multi-shell support**: Works with bash, zsh, and fish
- **Smart scoring**: Combines multiple factors for optimal ranking

## Quick Start

### Automatic Installation

Run the installation script to automatically set up autocomplete for your shell:

```bash
# Navigate to the archpkg-helper directory
cd archpkg-helper

./scripts/autocomplete/install_completion.sh
```

### Manual Installation

#### Bash

1. Copy the completion script:
   ```bash
   mkdir -p ~/.local/share/bash-completion/completions
   cp scripts/autocomplete/archpkg.bash ~/.local/share/bash-completion/completions/archpkg
   ```

2. Add to your `~/.bashrc`:
   ```bash
   if [ -f ~/.local/share/bash-completion/completions/archpkg ]; then
       source ~/.local/share/bash-completion/completions/archpkg
   fi
   ```

3. Reload your shell:
   ```bash
   source ~/.bashrc
   ```

#### Zsh

1. Copy the completion script:
   ```bash
   mkdir -p ~/.zsh/completions
   cp scripts/autocomplete/_archpkg ~/.zsh/completions/
   ```

2. Add to your `~/.zshrc`:
   ```zsh
   fpath=(~/.zsh/completions $fpath)
   autoload -U compinit && compinit
   ```

3. Reload your shell:
   ```zsh
   source ~/.zshrc
   ```

#### Fish

1. Copy the completion script:
   ```bash
   mkdir -p ~/.config/fish/completions
   cp scripts/autocomplete/archpkg.fish ~/.config/fish/completions/
   ```

2. Restart your terminal

## Usage Examples

### Basic Package Completion

```bash
archpkg install vs<TAB>

archpkg install chr<TAB>

archpkg install gim<TAB>
# Shows: gimp
```

### Abbreviation Matching

```bash
archpkg install vsc<TAB>

archpkg install ff<TAB>

archpkg install nvim<TAB>
```

### Context-Aware Completion

```bash
archpkg install <TAB>  
archpkg remove <TAB>   
archpkg search <TAB>   
```

### Purpose-Based Suggestions

```bash
archpkg suggest <TAB>

archpkg suggest video<TAB>
```

## Advanced Features

### Alias Mapping

The system includes built-in aliases for common package names:

| Alias | Resolves to |
|-------|-------------|
| `vscode` | `visual-studio-code` |
| `chrome` | `google-chrome` |
| `ff` | `firefox` |
| `nvim` | `neovim` |
| `node` | `nodejs` |
| `libre` | `libreoffice-fresh` |
| `gimp` | `gimp` |
| `steam` | `steam` |

### Frequency Tracking

The system learns from your usage patterns:

- Recently used packages appear first in suggestions
- Frequently installed packages get higher scores
- Usage data is cached in `~/.cache/archpkg/frequency_cache.json`

### Smart Scoring Algorithm

Completions are ranked using multiple factors:

1. **Exact match**: 100 points
2. **Prefix match**: 80 points
3. **Substring match**: 60 points
4. **Abbreviation match**: 70 points
5. **Description match**: 20 points
6. **Word boundary matches**: 10 points each
7. **Frequency bonus**: Up to 20 points
8. **Recent usage bonus**: Up to 10 points
9. **Source priority**: pacman (10), aur (8), flatpak (6), snap (4)
10. **Context bonus**: +15 for recent packages in remove context

## Configuration

### Custom Aliases

You can extend the alias mapping by modifying the `_load_alias_mappings()` method in `completion.py`:

```python
self.alias_map = {
    # Add your custom aliases here
    'myalias': 'actual-package-name',
    'short': 'very-long-package-name',
}
```

### Cache Management

The completion system uses several cache files:

- `~/.cache/archpkg/frequency_cache.json`: Package usage frequency
- `~/.cache/archpkg/`: Directory for other cache files

To clear the cache:
```bash
rm -rf ~/.cache/archpkg/
```

## Troubleshooting

### Completion Not Working

1. **Check if archpkg is in PATH**:
   ```bash
   which archpkg
   ```

2. **Test completion manually**:
   ```bash
   archpkg complete "firefox"
   ```

3. **Check shell configuration**:
   - Bash: Ensure completion script is sourced
   - Zsh: Ensure fpath includes completion directory
   - Fish: Ensure completion file is in correct location

4. **Enable debug mode**:
   ```bash
   archpkg --debug complete "test"
   ```

### Performance Issues

If completion is slow:

1. **Clear the cache**:
   ```bash
   rm -rf ~/.cache/archpkg/
   ```

2. **Check system resources**:
   - Ensure sufficient memory
   - Check disk space

3. **Reduce completion limit**:
   ```bash
   # In shell completion scripts, reduce --limit parameter
   archpkg complete "$query" --limit 5
   ```

### Shell-Specific Issues

#### Bash
- Ensure `bash-completion` package is installed
- Check that completion script is executable
- Verify sourcing in `.bashrc`

#### Zsh
- Ensure `compinit` is called
- Check that completion directory is in `fpath`
- Verify completion script naming (`_archpkg`)

#### Fish
- Ensure completion file is in `~/.config/fish/completions/`
- Check file permissions
- Restart fish shell

## API Reference

### Command Line Interface

```bash
archpkg complete <query> [--context <context>] [--limit <number>]
```

**Parameters:**
- `query`: The text to complete
- `--context`: Completion context (`install`, `remove`, `search`)
- `--limit`: Maximum number of suggestions (default: 10)

**Output:** Newline-separated list of package names

### Python API

```python
from archpkg.completion import complete_packages, get_completion_backend

completions = complete_packages("firefox", "install", 5)

backend = get_completion_backend()
results = backend.get_completions("firefox", "install", 5)
```

## Contributing

### Adding New Packages

To add new packages to the completion system:

1. **Update static data** in `completion.py`:
   ```python
   def _get_static_package_data(self) -> Dict[str, Dict]:
       return {
           'new-package': {
               'description': 'Package description',
               'source': 'pacman'  # or 'aur', 'flatpak', etc.
           },
       }
   ```

2. **Add aliases** if needed:
   ```python
   self.alias_map = {
       # Add new aliases
       'alias': 'new-package',
   }
   ```

### Improving Scoring

To modify the scoring algorithm, edit the `_calculate_score()` method in `completion.py`.

### Adding New Shells

To add support for a new shell:

1. Create a completion script in `scripts/autocomplete/`
2. Update the installation script
3. Add documentation

## License

This autocomplete system is part of archpkg-helper and follows the same license terms.
