#!/bin/bash
# Installation script for archpkg autocomplete
# This script installs shell completion for archpkg

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHPKG_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo -e "${BLUE}Installing archpkg autocomplete...${NC}"

# Function to install bash completion
install_bash() {
    echo -e "${YELLOW}Installing bash completion...${NC}"
    
    # Create completion directory if it doesn't exist
    mkdir -p ~/.local/share/bash-completion/completions
    
    # Copy bash completion script
    cp "$SCRIPT_DIR/archpkg.bash" ~/.local/share/bash-completion/completions/archpkg
    
    # Add to .bashrc if not already present
    if ! grep -q "archpkg completion" ~/.bashrc 2>/dev/null; then
        echo "" >> ~/.bashrc
        echo "# archpkg completion" >> ~/.bashrc
        echo "if [ -f ~/.local/share/bash-completion/completions/archpkg ]; then" >> ~/.bashrc
        echo "    source ~/.local/share/bash-completion/completions/archpkg" >> ~/.bashrc
        echo "fi" >> ~/.bashrc
    fi
    
    echo -e "${GREEN}Bash completion installed successfully!${NC}"
    echo -e "${YELLOW}Note: You may need to restart your terminal or run 'source ~/.bashrc'${NC}"
}

# Function to install zsh completion
install_zsh() {
    echo -e "${YELLOW}Installing zsh completion...${NC}"
    
    # Create completion directory if it doesn't exist
    mkdir -p ~/.zsh/completions
    
    # Copy zsh completion script
    cp "$SCRIPT_DIR/_archpkg" ~/.zsh/completions/
    
    # Add to .zshrc if not already present
    if ! grep -q "archpkg completion" ~/.zshrc 2>/dev/null; then
        echo "" >> ~/.zshrc
        echo "# archpkg completion" >> ~/.zshrc
        echo "fpath=(~/.zsh/completions \$fpath)" >> ~/.zshrc
        echo "autoload -U compinit && compinit" >> ~/.zshrc
    fi
    
    echo -e "${GREEN}Zsh completion installed successfully!${NC}"
    echo -e "${YELLOW}Note: You may need to restart your terminal or run 'source ~/.zshrc'${NC}"
}

# Function to install fish completion
install_fish() {
    echo -e "${YELLOW}Installing fish completion...${NC}"
    
    # Create completion directory if it doesn't exist
    mkdir -p ~/.config/fish/completions
    
    # Copy fish completion script
    cp "$SCRIPT_DIR/archpkg.fish" ~/.config/fish/completions/
    
    echo -e "${GREEN}Fish completion installed successfully!${NC}"
    echo -e "${YELLOW}Note: You may need to restart your terminal${NC}"
}

# Function to detect shell
detect_shell() {
    if [ -n "$ZSH_VERSION" ]; then
        echo "zsh"
    elif [ -n "$BASH_VERSION" ]; then
        echo "bash"
    elif [ -n "$FISH_VERSION" ]; then
        echo "fish"
    else
        # Try to detect from parent process
        local parent_shell=$(ps -p $PPID -o comm= 2>/dev/null || echo "")
        case "$parent_shell" in
            *zsh*) echo "zsh" ;;
            *bash*) echo "bash" ;;
            *fish*) echo "fish" ;;
            *) echo "unknown" ;;
        esac
    fi
}

# Main installation logic
main() {
    local shell=$(detect_shell)
    
    echo -e "${BLUE}Detected shell: $shell${NC}"
    
    case "$shell" in
        "bash")
            install_bash
            ;;
        "zsh")
            install_zsh
            ;;
        "fish")
            install_fish
            ;;
        *)
            echo -e "${YELLOW}Unknown shell detected. Installing for all supported shells...${NC}"
            install_bash
            install_zsh
            install_fish
            ;;
    esac
    
    echo -e "${GREEN}Installation complete!${NC}"
    echo -e "${BLUE}Usage examples:${NC}"
    echo -e "  archpkg install <TAB>  # Complete package names"
    echo -e "  archpkg remove <TAB>   # Complete installed packages"
    echo -e "  archpkg search <TAB>   # Complete search terms"
    echo -e "  archpkg suggest <TAB>  # Complete purpose categories"
}

# Check if archpkg is installed
if ! command -v archpkg &> /dev/null; then
    echo -e "${RED}Error: archpkg is not installed or not in PATH${NC}"
    echo -e "${YELLOW}Please install archpkg first:${NC}"
    echo -e "  pip install archpkg-helper"
    echo -e "  # or"
    echo -e "  pipx install archpkg-helper"
    exit 1
fi

# Run main function
main "$@"
