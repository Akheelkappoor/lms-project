# n8n LMS AI Analytics Deployment Guide

## Prerequisites
- AWS EC2 instance (t3.medium recommended)
- Security Group allowing ports 22, 80, and 5678
- Your LMS PostgreSQL database accessible from EC2

## Step 1: Launch EC2 Instance

1. Create EC2 instance with Ubuntu 20.04 LTS
2. Configure Security Group:
   - SSH (22) - Your IP
   - HTTP (80) - 0.0.0.0/0
   - Custom TCP (5678) - 0.0.0.0/0

## Step 2: Deploy n8n

1. SSH into your EC2 instance:
```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
```

2. Upload and run setup script:
```bash
# Copy the setup script to EC2
scp -i your-key.pem ec2-n8n-setup.sh ubuntu@your-ec2-ip:~/

# Make it executable and run
chmod +x ec2-n8n-setup.sh
sudo ./ec2-n8n-setup.sh
```

3. Update configuration with your details:
```bash
sudo nano /etc/systemd/system/n8n.service
# Update passwords, IP addresses, etc.

sudo systemctl daemon-reload
sudo systemctl restart n8n
```

## Step 3: Set up Database Schema

1. Connect to your PostgreSQL database and run:
```sql
-- Run the contents of ai-reports-schema.sql
```

## Step 4: Configure n8n Workflows

1. Access n8n at `http://your-ec2-ip:5678`
2. Login with credentials from setup
3. Import the workflow from `ai-analysis-workflow.json`
4. Configure database credentials:
   - Go to Settings > Credentials
   - Add new PostgreSQL credential with your database details

## Step 5: Set up Analysis Endpoints

The workflow provides two trigger methods:

### Manual Trigger
- Use for on-demand analysis
- Click "Execute Workflow" in n8n interface

### Webhook Trigger
- Accessible at: `http://your-ec2-ip:5678/webhook/ai-analysis-webhook`
- Use POST request to trigger analysis programmatically

Example curl command:
```bash
curl -X POST http://your-ec2-ip:5678/webhook/ai-analysis-webhook \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Step 6: Integration with Your LMS

Add this function to your LMS application to trigger analysis:

```javascript
// JavaScript example
async function triggerAIAnalysis() {
  try {
    const response = await fetch('http://your-ec2-ip:5678/webhook/ai-analysis-webhook', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({})
    });
    
    const result = await response.json();
    console.log('Analysis triggered:', result);
    return result;
  } catch (error) {
    console.error('Error triggering analysis:', error);
  }
}
```

## Step 7: Monitoring and Maintenance

1. Check n8n status:
```bash
sudo systemctl status n8n
```

2. View logs:
```bash
journalctl -u n8n -f
```

3. Set up automated analysis (optional):
   - Use n8n's Cron node to schedule regular analysis
   - Example: Daily at 2 AM

## AI Analysis Features

The workflow provides:

### User Analytics
- Total users and engagement metrics
- User segmentation (high/low engagers)
- Completion rates and patterns
- Retention insights

### Course Analytics  
- Course performance metrics
- Category analysis
- Top performers and underperformers
- Rating analysis

### AI Insights
- Automated pattern detection
- Performance recommendations
- Engagement improvement suggestions
- Platform health assessment

### Report Storage
- All reports stored in `ai_analysis_reports` table
- JSONB format for flexible querying
- Timestamped with metadata

## Security Considerations

1. Change default passwords in setup script
2. Use SSL certificates for production (Let's Encrypt)
3. Restrict EC2 security group access
4. Regularly update n8n and system packages
5. Monitor database access logs

## Scaling Options

- Use RDS proxy for database connections
- Deploy behind Application Load Balancer
- Use Auto Scaling Groups for high availability
- Consider n8n Enterprise for advanced features

## Troubleshooting

Common issues:
- Database connection: Check security groups and credentials
- n8n not starting: Check logs with `journalctl -u n8n`
- Workflow errors: Enable debug mode in n8n settings
- Performance issues: Monitor EC2 resource usage