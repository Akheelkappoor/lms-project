#!/bin/bash

# Quick installer - run this directly on EC2
echo "Starting n8n installation on EC2..."

# Create the installation script directly on EC2
cat > /tmp/install-n8n.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 Installing n8n on EC2..."

# Update system
sudo apt update && sudo apt upgrade -y

# Install Node.js 18.x
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify Node.js installation
echo "Node.js version: $(node --version)"
echo "npm version: $(npm --version)"

# Install n8n globally
sudo npm install -g n8n

# Install PM2 for process management
sudo npm install -g pm2

# Create n8n user and directories
sudo useradd -m -s /bin/bash n8n || echo "User n8n already exists"
sudo mkdir -p /home/n8n/.n8n
sudo chown -R n8n:n8n /home/n8n

# Get the current instance's public IP
INSTANCE_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "Instance public IP: $INSTANCE_IP"

# Create systemd service file
sudo tee /etc/systemd/system/n8n.service > /dev/null <<EOL
[Unit]
Description=n8n workflow automation
After=network.target

[Service]
Type=simple
User=n8n
ExecStart=/usr/bin/n8n start
Restart=always
RestartSec=10
Environment=NODE_ENV=production
Environment=N8N_BASIC_AUTH_ACTIVE=true
Environment=N8N_BASIC_AUTH_USER=admin
Environment=N8N_BASIC_AUTH_PASSWORD=n8n_admin_2024
Environment=N8N_HOST=0.0.0.0
Environment=N8N_PORT=5678
Environment=N8N_PROTOCOL=http
Environment=WEBHOOK_URL=http://${INSTANCE_IP}:5678
Environment=GENERIC_TIMEZONE=UTC
Environment=N8N_LOG_LEVEL=info

[Install]
WantedBy=multi-user.target
EOL

# Reload systemd and enable n8n service
sudo systemctl daemon-reload
sudo systemctl enable n8n
sudo systemctl start n8n

# Wait a moment for service to start
sleep 5

# Check service status
sudo systemctl status n8n --no-pager

# Install and configure nginx (optional reverse proxy)
echo "Installing nginx..."
sudo apt install -y nginx

# Create nginx configuration for n8n
sudo tee /etc/nginx/sites-available/n8n > /dev/null <<EOL
server {
    listen 80;
    server_name ${INSTANCE_IP};
    
    location / {
        proxy_pass http://localhost:5678;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 86400;
    }
}
EOL

# Enable nginx site
sudo ln -sf /etc/nginx/sites-available/n8n /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

# Configure firewall
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 5678/tcp
echo "y" | sudo ufw enable

echo "✅ n8n installation completed!"
echo ""
echo "🌐 Access URLs:"
echo "  Direct: http://${INSTANCE_IP}:5678"
echo "  Via Nginx: http://${INSTANCE_IP}"
echo ""
echo "🔐 Login credentials:"
echo "  Username: admin"
echo "  Password: n8n_admin_2024"
echo ""
echo "📊 Service commands:"
echo "  Check status: sudo systemctl status n8n"
echo "  View logs: journalctl -u n8n -f"
echo "  Restart: sudo systemctl restart n8n"
echo ""
echo "⚠️  IMPORTANT: Change the default password after first login!"
echo "⚠️  Update security groups to allow HTTP (80) and custom TCP (5678) access"

EOF

# Make the script executable
chmod +x /tmp/install-n8n.sh

# Run the installation
sudo /tmp/install-n8n.sh

echo "Installation completed! Check the output above for access details."