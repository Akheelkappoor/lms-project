#!/bin/bash

# Minimal n8n installation for low-disk systems
set -e

echo "🚀 Minimal n8n installation for limited disk space..."

# More aggressive cleanup first
sudo apt clean
sudo apt autoremove --purge -y
sudo rm -rf /var/cache/apt/archives/*
sudo rm -rf /tmp/*
sudo rm -rf /var/tmp/*
sudo journalctl --vacuum-size=10M
sudo find /var/log -name "*.log" -delete 2>/dev/null || true

# Remove any existing failed installations
sudo systemctl stop n8n 2>/dev/null || true
sudo npm uninstall -g n8n 2>/dev/null || true
sudo userdel -r n8n 2>/dev/null || true

echo "📦 Installing n8n with minimal footprint..."

# Install n8n with minimal dependencies
sudo npm install -g n8n --no-optional --no-audit --no-fund --prefer-offline --cache /tmp/npm-cache

# Create minimal user setup
sudo useradd -m -s /bin/bash n8n
sudo mkdir -p /home/n8n/.n8n

# Get IP
INSTANCE_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)

# Create minimal service file
sudo tee /etc/systemd/system/n8n.service > /dev/null <<EOF
[Unit]
Description=n8n
After=network.target

[Service]
Type=simple
User=n8n
ExecStart=$(which n8n) start
Restart=always
Environment=N8N_BASIC_AUTH_ACTIVE=true
Environment=N8N_BASIC_AUTH_USER=admin
Environment=N8N_BASIC_AUTH_PASSWORD=admin123
Environment=N8N_HOST=0.0.0.0
Environment=N8N_PORT=5678

[Install]
WantedBy=multi-user.target
EOF

# Start service
sudo systemctl daemon-reload
sudo systemctl enable n8n
sudo systemctl start n8n

echo "✅ Minimal n8n installation complete!"
echo "🌐 Access: http://${INSTANCE_IP}:5678"
echo "🔐 admin/admin123"

# Clean up after installation
sudo rm -rf /tmp/npm-cache
sudo npm cache clean --force

df -h