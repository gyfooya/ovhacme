#!/bin/bash
# Installation script for OVH Let's Encrypt systemd service

set -e

echo "=============================================="
echo "Installing OVH Let's Encrypt Systemd Service"
echo "=============================================="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Copy service and timer files
echo "📋 Copying service files to /etc/systemd/system/..."
cp ovh-letsencrypt.service /etc/systemd/system/
cp ovh-letsencrypt.timer /etc/systemd/system/

# Set proper permissions
echo "🔒 Setting permissions..."
chmod 644 /etc/systemd/system/ovh-letsencrypt.service
chmod 644 /etc/systemd/system/ovh-letsencrypt.timer

# Reload systemd
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

# Enable the timer (not the service directly)
echo "✅ Enabling timer..."
systemctl enable ovh-letsencrypt.timer

# Start the timer
echo "▶️  Starting timer..."
systemctl start ovh-letsencrypt.timer

echo
echo "✅ Installation complete!"
echo
echo "Service status:"
systemctl status ovh-letsencrypt.timer --no-pager
echo
echo "Next scheduled run:"
systemctl list-timers ovh-letsencrypt.timer --no-pager
echo
echo "Useful commands:"
echo "  sudo systemctl status ovh-letsencrypt.timer   # Check timer status"
echo "  sudo systemctl start ovh-letsencrypt.service  # Run renewal now"
echo "  sudo journalctl -u ovh-letsencrypt -f         # View logs"
echo "  sudo systemctl list-timers                    # See all timers"
