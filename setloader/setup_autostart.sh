#!/bin/bash
# Setup script to enable SetLoader auto-start on macOS

echo "🚀 Setting up SetLoader auto-start..."

# Create logs directory
mkdir -p /usr/local/src/setloader/logs

# Copy the plist file to LaunchDaemons
echo "📋 Installing launchd service..."
sudo cp /usr/local/src/setloader/setloader.plist /Library/LaunchDaemons/

# Set proper permissions
sudo chown root:wheel /Library/LaunchDaemons/setloader.plist
sudo chmod 644 /Library/LaunchDaemons/setloader.plist

# Load the service
echo "🔄 Loading service..."
sudo launchctl load /Library/LaunchDaemons/setloader.plist

# Enable the service
echo "✅ Enabling service..."
sudo launchctl enable system/com.setloader.app

echo ""
echo "✅ SetLoader auto-start setup complete!"
echo ""
echo "📋 Service Status:"
sudo launchctl list | grep setloader || echo "Service not running yet"
echo ""
echo "📝 Logs will be written to:"
echo "   - /usr/local/src/setloader/logs/setloader.log"
echo "   - /usr/local/src/setloader/logs/setloader-error.log"
echo ""
echo "🔧 Management Commands:"
echo "   Start:   sudo launchctl start com.setloader.app"
echo "   Stop:    sudo launchctl stop com.setloader.app"
echo "   Restart: sudo launchctl unload /Library/LaunchDaemons/setloader.plist && sudo launchctl load /Library/LaunchDaemons/setloader.plist"
echo "   Remove:  sudo launchctl unload /Library/LaunchDaemons/setloader.plist && sudo rm /Library/LaunchDaemons/setloader.plist"

