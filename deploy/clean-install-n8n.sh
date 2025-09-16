#!/bin/bash

# Clean installation script with space checks
set -e

echo "🧹 Checking and cleaning disk space before n8n installation..."

# Function to check available space
check_space() {
    local available=$(df / | awk 'NR==2 {print $4}')
    local available_gb=$((available / 1024 / 1024))
    echo "Available space: ${available_gb}GB"
    
    if [ $available_gb -lt 5 ]; then
        echo "❌ Insufficient space! Need at least 5GB. Current: ${available_gb}GB"
        return 1
    fi
    echo "✅ Sufficient space available"
    return 0
}

# Clean up space first
echo "🧹 Cleaning up existing files..."
sudo apt clean
sudo apt autoremove -y
sudo npm cache clean --force 2>/dev/null || true
sudo journalctl --vacuum-time=7d
sudo docker system prune -af 2>/dev/null || true

# Remove any failed n8n installation
sudo systemctl stop n8n 2>/dev/null || true
sudo systemctl disable n8n 2>/dev/null || true
sudo rm -f /etc/systemd/system/n8n.service
sudo userdel -r n8n 2>/dev/null || true
sudo npm uninstall -g n8n 2>/dev/null || true

echo "🔍 Checking available disk space..."
check_space || exit 1

echo "🚀 Starting clean n8n installation..."

# Update system
sudo apt update

# Install Node.js (lighter approach)
if ! command -v node &> /dev/null; then
    echo "📦 Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt-get install -y nodejs
else
    echo "✅ Node.js already installed: $(node --version)"
fi

# Check space before n8n installation
check_space || exit 1

# Install n8n with limited cache
echo "📦 Installing n8n (this may take a few minutes)..."
sudo npm install -g n8n --no-optional --prefer-offline

# Verify installation
if ! command -v n8n &> /dev/null; then
    echo "❌ n8n installation failed"
    exit 1
fi

echo "✅ n8n installed successfully: $(n8n --version)"

# Create n8n user and directories
echo "👤 Creating n8n user..."
sudo useradd -m -s /bin/bash n8n 2>/dev/null || echo "User n8n already exists"
sudo mkdir -p /home/n8n/.n8n
sudo chown -R n8n:n8n /home/n8n

# Get instance IP
INSTANCE_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "localhost")
echo "🌐 Instance IP: $INSTANCE_IP"

# Create systemd service
echo "⚙️  Creating systemd service..."
sudo tee /etc/systemd/system/n8n.service > /dev/null <<EOF
[Unit]
Description=n8n workflow automation
After=network.target

[Service]
Type=simple
User=n8n
ExecStart=$(which n8n) start
Restart=always
RestartSec=10
Environment=NODE_ENV=production
Environment=N8N_BASIC_AUTH_ACTIVE=true
Environment=N8N_BASIC_AUTH_USER=admin
Environment=N8N_BASIC_AUTH_PASSWORD=n8n_secure_2024
Environment=N8N_HOST=0.0.0.0
Environment=N8N_PORT=5678
Environment=N8N_PROTOCOL=http
Environment=WEBHOOK_URL=http://${INSTANCE_IP}:5678
Environment=GENERIC_TIMEZONE=UTC

[Install]
WantedBy=multi-user.target
EOF

# Start n8n service
echo "🔄 Starting n8n service..."
sudo systemctl daemon-reload
sudo systemctl enable n8n
sudo systemctl start n8n

# Wait and check status
sleep 5
if sudo systemctl is-active --quiet n8n; then
    echo "✅ n8n service is running"
else
    echo "❌ n8n service failed to start"
    sudo journalctl -u n8n --no-pager -l
    exit 1
fi

# Configure firewall
echo "🔥 Configuring firewall..."
sudo ufw allow 5678/tcp 2>/dev/null || true

# Final status check
echo ""
echo "🎉 Installation completed successfully!"
echo ""
echo "🌐 Access n8n at: http://${INSTANCE_IP}:5678"
echo "🔐 Username: admin"
echo "🔐 Password: n8n_secure_2024"
echo ""
echo "📊 Service status:"
sudo systemctl status n8n --no-pager -l
echo ""
echo "💾 Current disk usage:"
df -h /
echo ""
echo "⚠️  Remember to:"
echo "   1. Change the default password after first login"
echo "   2. Update your Security Group to allow port 5678"
echo "   3. Consider setting up SSL for production use"