#!/bin/bash
# Bash completion script for archpkg
# Source this file in your ~/.bashrc or ~/.bash_profile

_archpkg_complete() {
    local cur prev words cword
    _init_completion -s || return

    # Get the current word being completed
    local current_word="${COMP_WORDS[COMP_CWORD]}"
    
    # Get the command context (install, remove, etc.)
    local context="install"
    if [[ ${#COMP_WORDS[@]} -ge 2 ]]; then
        case "${COMP_WORDS[1]}" in
            "remove"|"uninstall"|"rm")
                context="remove"
                ;;
            "search"|"find"|"lookup")
                context="search"
                ;;
            "install"|"add"|"get")
                context="install"
                ;;
        esac
    fi

    # If we're completing a package name (not a command)
    if [[ ${#COMP_WORDS[@]} -ge 2 && "${COMP_WORDS[1]}" != "--complete" ]]; then
        # Get completions from archpkg
        local completions
        completions=$(archpkg complete "$current_word" --context "$context" 2>/dev/null)
        
        if [[ -n "$completions" ]]; then
            COMPREPLY=($(compgen -W "$completions" -- "$current_word"))
        else
            # Fallback to basic completion
            COMPREPLY=()
        fi
    else
        # Complete commands
        local commands="search suggest complete install remove uninstall --help --version --debug --log-info"
        COMPREPLY=($(compgen -W "$commands" -- "$current_word"))
    fi
}

# Register the completion function
complete -F _archpkg_complete archpkg

# Also register for common aliases
complete -F _archpkg_complete apkg
complete -F _archpkg_complete archpkg-helper
