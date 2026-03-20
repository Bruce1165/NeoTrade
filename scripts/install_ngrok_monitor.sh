#!/bin/bash
# Ngrok Monitor Installation Script
# Sets up LaunchAgent for automatic monitoring

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
WORKSPACE="/Users/mac/.openclaw/workspace-neo"
SCRIPT_DIR="$WORKSPACE/scripts"
PLIST_SOURCE="$SCRIPT_DIR/com.neo.ngrok-monitor.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.neo.ngrok-monitor.plist"
LOG_DIR="$WORKSPACE/logs"
ALERT_DIR="$WORKSPACE/alerts"

echo "========================================"
echo "Ngrok Monitor Installation"
echo "========================================"
echo ""

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${RED}Error: This script is for macOS only${NC}"
    exit 1
fi

# Create directories
echo "Creating directories..."
mkdir -p "$LOG_DIR"
mkdir -p "$ALERT_DIR"

# Check Python3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 not found${NC}"
    exit 1
fi

# Check required Python packages
echo "Checking Python dependencies..."
python3 -c "import psutil, requests" 2>/dev/null || {
    echo "Installing required packages..."
    pip3 install psutil requests
}

# Check if monitor script exists
if [[ ! -f "$SCRIPT_DIR/ngrok_monitor.py" ]]; then
    echo -e "${RED}Error: ngrok_monitor.py not found at $SCRIPT_DIR/${NC}"
    exit 1
fi

# Make scripts executable
echo "Setting permissions..."
chmod +x "$SCRIPT_DIR/ngrok_monitor.py"

# Unload existing service if present
echo "Checking for existing service..."
if launchctl list | grep -q "com.neo.ngrok-monitor"; then
    echo "Unloading existing service..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    sleep 1
fi

# Copy plist file
echo "Installing LaunchAgent..."
cp "$PLIST_SOURCE" "$PLIST_DEST"

# Load the service
echo "Loading LaunchAgent..."
launchctl load "$PLIST_DEST"

# Start the service
echo "Starting service..."
launchctl start com.neo.ngrok-monitor

# Wait a moment and check status
sleep 2

echo ""
echo "========================================"
echo -e "${GREEN}Installation Complete!${NC}"
echo "========================================"
echo ""
echo "Service: com.neo.ngrok-monitor"
echo "Status: $(launchctl list | grep com.neo.ngrok-monitor | awk '{print $1}' | grep -q '^-' && echo 'Running' || echo 'Check with: launchctl list | grep ngrok')"
echo ""
echo "Commands:"
echo "  Check status:  launchctl list | grep ngrok-monitor"
echo "  View logs:     tail -f $LOG_DIR/ngrok_monitor.log"
echo "  Stop service:  launchctl stop com.neo.ngrok-monitor"
echo "  Start service: launchctl start com.neo.ngrok-monitor"
echo "  Uninstall:     launchctl unload $PLIST_DEST && rm $PLIST_DEST"
echo ""
echo "Configuration:"
echo "  Flask Port:    5003"
echo "  Domain:        chariest-nancy-nonincidentally.ngrok-free.dev"
echo "  Check Interval: 60 seconds"
echo ""
echo "Test the monitor:"
echo "  $SCRIPT_DIR/ngrok_monitor.py --status"
echo ""

# Show current status
echo "Current status:"
python3 "$SCRIPT_DIR/ngrok_monitor.py" --status || true
