#!/bin/bash
# service-manager.sh
# Helper script to install and manage archpkg background monitor service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

SERVICE_FILE="archpkg-monitor.service"
TIMER_FILE="archpkg-monitor.timer"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${CYAN}${1}${NC}"
}

print_success() {
    echo -e "${GREEN}${1}${NC}"
}

print_error() {
    echo -e "${RED}${1}${NC}"
}

print_warning() {
    echo -e "${YELLOW}${1}${NC}"
}

install_service() {
    print_info "Installing archpkg monitor service..."
    
    # Create systemd user directory if it doesn't exist
    mkdir -p "$SYSTEMD_USER_DIR"
    
    # Copy service files
    cp "$SCRIPT_DIR/$SERVICE_FILE" "$SYSTEMD_USER_DIR/"
    cp "$SCRIPT_DIR/$TIMER_FILE" "$SYSTEMD_USER_DIR/"
    
    print_success "Service files installed to $SYSTEMD_USER_DIR"
    
    # Reload systemd
    systemctl --user daemon-reload
    
    print_success "Systemd user daemon reloaded"
}

enable_service() {
    print_info "Enabling archpkg monitor timer..."
    
    systemctl --user enable archpkg-monitor.timer
    systemctl --user start archpkg-monitor.timer
    
    print_success "archpkg monitor timer enabled and started"
    print_info "The monitor will run every 6 hours and 5 minutes after boot"
}

disable_service() {
    print_info "Disabling archpkg monitor timer..."
    
    systemctl --user stop archpkg-monitor.timer 2>/dev/null || true
    systemctl --user disable archpkg-monitor.timer 2>/dev/null || true
    
    print_success "archpkg monitor timer stopped and disabled"
}

uninstall_service() {
    print_info "Uninstalling archpkg monitor service..."
    
    # Stop and disable first
    disable_service
    
    # Remove service files
    rm -f "$SYSTEMD_USER_DIR/$SERVICE_FILE"
    rm -f "$SYSTEMD_USER_DIR/$TIMER_FILE"
    
    # Reload systemd
    systemctl --user daemon-reload
    
    print_success "Service files removed"
}

status_service() {
    print_info "archpkg monitor timer status:"
    systemctl --user status archpkg-monitor.timer --no-pager || true
    
    echo ""
    print_info "archpkg monitor service status:"
    systemctl --user status archpkg-monitor.service --no-pager || true
    
    echo ""
    print_info "Recent timer activations:"
    systemctl --user list-timers archpkg-monitor.timer --no-pager || true
}

run_once() {
    print_info "Running monitor check once..."
    python3 -m archpkg.monitor --once
    print_success "Monitor check complete"
}

show_logs() {
    print_info "Recent monitor logs:"
    journalctl --user -u archpkg-monitor.service -n 50 --no-pager
}

show_help() {
    echo "archpkg monitor service manager"
    echo ""
    echo "Usage: $0 {install|enable|disable|uninstall|status|run-once|logs|help}"
    echo ""
    echo "Commands:"
    echo "  install     Install service files to systemd user directory"
    echo "  enable      Enable and start the monitor timer"
    echo "  disable     Stop and disable the monitor timer"
    echo "  uninstall   Remove service files"
    echo "  status      Show service and timer status"
    echo "  run-once    Run a monitor check immediately"
    echo "  logs        Show recent monitor logs"
    echo "  help        Show this help message"
    echo ""
    echo "Typical usage:"
    echo "  1. Install service:  $0 install"
    echo "  2. Enable timer:     $0 enable"
    echo "  3. Check status:     $0 status"
}

# Main logic
case "${1:-}" in
    install)
        install_service
        ;;
    enable)
        enable_service
        ;;
    disable)
        disable_service
        ;;
    uninstall)
        uninstall_service
        ;;
    status)
        status_service
        ;;
    run-once)
        run_once
        ;;
    logs)
        show_logs
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: ${1:-}"
        echo ""
        show_help
        exit 1
        ;;
esac
