# Fish completion script for archpkg
# Place this file in ~/.config/fish/completions/archpkg.fish

function __archpkg_get_completions
    set -l query (commandline -ct)
    set -l context "install"
    
    # Determine context based on command
    set -l cmd (commandline -p)
    if string match -q "*remove*" "$cmd" || string match -q "*uninstall*" "$cmd" || string match -q "*rm*" "$cmd"
        set context "remove"
    else if string match -q "*search*" "$cmd" || string match -q "*find*" "$cmd" || string match -q "*lookup*" "$cmd"
        set context "search"
    end
    
    # Get completions from archpkg
    archpkg complete "$query" --context "$context" 2>/dev/null
end

# Complete commands
complete -c archpkg -n "__fish_use_subcommand" -a "search" -d "Search for packages by name"
complete -c archpkg -n "__fish_use_subcommand" -a "suggest" -d "Get app suggestions based on purpose"
complete -c archpkg -n "__fish_use_subcommand" -a "install" -d "Install packages"
complete -c archpkg -n "__fish_use_subcommand" -a "remove" -d "Remove packages"
complete -c archpkg -n "__fish_use_subcommand" -a "uninstall" -d "Remove packages"
complete -c archpkg -n "__fish_use_subcommand" -a "complete" -d "Generate completion suggestions"
complete -c archpkg -n "__fish_use_subcommand" -a "--help" -d "Show help information"
complete -c archpkg -n "__fish_use_subcommand" -a "--version" -d "Show version information"
complete -c archpkg -n "__fish_use_subcommand" -a "--debug" -d "Enable debug logging"
complete -c archpkg -n "__fish_use_subcommand" -a "--log-info" -d "Show logging configuration"

# Complete package names for install command
complete -c archpkg -n "__fish_seen_subcommand_from install add get" -a "(__archpkg_get_completions)"

# Complete package names for remove command
complete -c archpkg -n "__fish_seen_subcommand_from remove uninstall rm" -a "(__archpkg_get_completions)"

# Complete package names for search command
complete -c archpkg -n "__fish_seen_subcommand_from search find lookup" -a "(__archpkg_get_completions)"

# Complete package names for suggest command
complete -c archpkg -n "__fish_seen_subcommand_from suggest" -a "video editing office music coding graphics gaming browsing communication development system text editing media utilities"

# Also register for common aliases
complete -c apkg -n "__fish_use_subcommand" -a "search suggest complete install remove uninstall --help --version --debug --log-info"
complete -c apkg -n "__fish_seen_subcommand_from install add get" -a "(__archpkg_get_completions)"
complete -c apkg -n "__fish_seen_subcommand_from remove uninstall rm" -a "(__archpkg_get_completions)"
complete -c apkg -n "__fish_seen_subcommand_from search find lookup" -a "(__archpkg_get_completions)"
complete -c apkg -n "__fish_seen_subcommand_from suggest" -a "video editing office music coding graphics gaming browsing communication development system text editing media utilities"

complete -c archpkg-helper -n "__fish_use_subcommand" -a "search suggest complete install remove uninstall --help --version --debug --log-info"
complete -c archpkg-helper -n "__fish_seen_subcommand_from install add get" -a "(__archpkg_get_completions)"
complete -c archpkg-helper -n "__fish_seen_subcommand_from remove uninstall rm" -a "(__archpkg_get_completions)"
complete -c archpkg-helper -n "__fish_seen_subcommand_from search find lookup" -a "(__archpkg_get_completions)"
complete -c archpkg-helper -n "__fish_seen_subcommand_from suggest" -a "video editing office music coding graphics gaming browsing communication development system text editing media utilities"
