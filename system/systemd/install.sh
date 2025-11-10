#!/bin/bash
# Installation script pour MiniBotPanel Recording Cleanup Service

set -e  # Exit on error

echo "========================================================================"
echo "MiniBotPanel - Recording Cleanup Service Installation"
echo "========================================================================"
echo ""

# Vérifier si exécuté en tant que root
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  Ce script doit être exécuté avec sudo:"
    echo "   sudo bash systemd/install.sh"
    exit 1
fi

# Chemins
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/minibot-recording-cleanup.service"
TIMER_FILE="$SCRIPT_DIR/minibot-recording-cleanup.timer"

echo "📁 Script directory: $SCRIPT_DIR"
echo ""

# Vérifier que les fichiers existent
if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ Error: Service file not found: $SERVICE_FILE"
    exit 1
fi

if [ ! -f "$TIMER_FILE" ]; then
    echo "❌ Error: Timer file not found: $TIMER_FILE"
    exit 1
fi

echo "✅ Service files found"
echo ""

# Copier les fichiers
echo "📋 Installing systemd files..."
cp "$SERVICE_FILE" /etc/systemd/system/
cp "$TIMER_FILE" /etc/systemd/system/

echo "✅ Files copied to /etc/systemd/system/"
echo ""

# Recharger systemd
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload
echo "✅ Systemd daemon reloaded"
echo ""

# Activer le timer
echo "⚙️  Enabling timer (auto-start on boot)..."
systemctl enable minibot-recording-cleanup.timer
echo "✅ Timer enabled"
echo ""

# Démarrer le timer
echo "▶️  Starting timer..."
systemctl start minibot-recording-cleanup.timer
echo "✅ Timer started"
echo ""

# Afficher status
echo "========================================================================"
echo "📊 Installation Status"
echo "========================================================================"
echo ""

echo "Timer status:"
systemctl status minibot-recording-cleanup.timer --no-pager -l
echo ""

echo "Next execution:"
systemctl list-timers minibot-recording-cleanup.timer --no-pager
echo ""

echo "========================================================================"
echo "✅ Installation completed successfully!"
echo "========================================================================"
echo ""
echo "The cleanup service will run daily at 3:00 AM."
echo ""
echo "Useful commands:"
echo "  - View timer status:        sudo systemctl status minibot-recording-cleanup.timer"
echo "  - View next execution:      sudo systemctl list-timers | grep minibot"
echo "  - Run cleanup now (test):   sudo systemctl start minibot-recording-cleanup.service"
echo "  - View logs:                sudo journalctl -u minibot-recording-cleanup.service -n 50"
echo "  - Stop timer:               sudo systemctl stop minibot-recording-cleanup.timer"
echo "  - Disable timer:            sudo systemctl disable minibot-recording-cleanup.timer"
echo ""
echo "Documentation: system/systemd/INSTALL.md"
echo ""
