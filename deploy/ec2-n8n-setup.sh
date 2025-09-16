#!/bin/bash

# Update system
sudo apt update && sudo apt upgrade -y

# Install Node.js (required for n8n)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install n8n globally
sudo npm install -g n8n

# Install PM2 for process management
sudo npm install -g pm2

# Create n8n user and directories
sudo useradd -m -s /bin/bash n8n
sudo mkdir -p /home/n8n/.n8n
sudo chown -R n8n:n8n /home/n8n

# Create systemd service file
sudo tee /etc/systemd/system/n8n.service > /dev/null <<EOF
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
Environment=N8N_BASIC_AUTH_PASSWORD=change_this_password
Environment=N8N_HOST=0.0.0.0
Environment=N8N_PORT=5678
Environment=N8N_PROTOCOL=https
Environment=WEBHOOK_URL=https://n8n.lms-i2global.com
Environment=DB_TYPE=postgresdb
Environment=DB_POSTGRESDB_HOST=lms.c9c8kyy28xrq.ap-south-1.rds.amazonaws.com
Environment=DB_POSTGRESDB_PORT=5432
Environment=DB_POSTGRESDB_DATABASE=postgres
Environment=DB_POSTGRESDB_USER=LMS_database
Environment=DB_POSTGRESDB_PASSWORD=pkczZdj8vo6FjWEa4SWF
Environment=DB_POSTGRESDB_SSL=require

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
sudo systemctl enable n8n
sudo systemctl start n8n

# Install nginx for reverse proxy (optional)
sudo apt install -y nginx

# Create nginx configuration
sudo tee /etc/nginx/sites-available/n8n > /dev/null <<EOF
server {
    listen 80;
    server_name n8n.lms-i2global.com;
    
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
    }
}
EOF

# Enable nginx site
sudo ln -s /etc/nginx/sites-available/n8n /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Open firewall ports
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 5678
sudo ufw --force enable

echo "n8n installation completed!"
echo "Access n8n at: https://n8n.lms-i2global.com"
echo "Default credentials: admin / change_this_password"