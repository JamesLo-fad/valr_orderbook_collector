# AWS EC2 Deployment Guide for VALR Orderbook Recorder

Complete guide for deploying the VALR orderbook recorder to AWS EC2 for 24/7 data collection.

---

## Table of Contents

1. [Pre-Deployment Planning](#pre-deployment-planning)
2. [Deployment Steps](#deployment-steps)
3. [Monitoring and Maintenance](#monitoring-and-maintenance)
4. [Critical Things to Be Aware Of](#critical-things-to-be-aware-of)
5. [Troubleshooting Guide](#troubleshooting-guide)
6. [Quick Start Deployment Script](#quick-start-deployment-script)
7. [Summary Checklist](#summary-checklist)

---

## Pre-Deployment Planning

### EC2 Instance Recommendations

**Instance Type:**
- **Recommended:** `t3.small` (2 vCPU, 2GB RAM) - $15-20/month
- **Minimum:** `t3.micro` (2 vCPU, 1GB RAM) - $7-10/month
- **Why:** 6 concurrent WebSocket connections + SQLite writes are lightweight

**Storage:**
- **Recommended:** 100GB EBS gp3 volume (~$8/month)
- **Estimation:** 6 pairs × 90 days ≈ 30-50GB + logs + OS
- **Growth rate:** ~10-20GB per month for 6 pairs

**Operating System:**
- Ubuntu 22.04 LTS or Amazon Linux 2023

**Region:**
- Choose closest to VALR servers (likely South Africa or Europe)

**Monthly Cost Estimate:**
- t3.small instance: ~$15
- 100GB EBS gp3: ~$8
- Data transfer: ~$1-2
- **Total: ~$25-30/month**

---

## Deployment Steps

### Step 1: Launch EC2 Instance

**1. Security Group Configuration:**

```
Inbound Rules:
- SSH (22) from your IP only

Outbound Rules:
- HTTPS (443) to 0.0.0.0/0 (for VALR WebSocket: wss://api.valr.com)
- HTTP (80) to 0.0.0.0/0 (for system updates)
```

**2. Create and download SSH key pair**

**3. Allocate Elastic IP** (optional but recommended for stable access)

### Step 2: Connect and Setup System

```bash
# Connect to EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.10+ and dependencies
sudo apt install -y python3 python3-pip python3-venv git

# Install system monitoring tools
sudo apt install -y htop iotop
```

### Step 3: Deploy Application

```bash
# Create application directory
sudo mkdir -p /opt/valr-recorder
sudo chown ubuntu:ubuntu /opt/valr-recorder
cd /opt/valr-recorder

# Upload your code (choose one method):

# Method 1: SCP from local machine
# scp -i your-key.pem -r /path/to/valr-orderbook-recorder/* ubuntu@your-ec2-ip:/opt/valr-recorder/

# Method 2: Git clone (if you have a repo)
# git clone https://github.com/your-repo/valr-orderbook-recorder.git .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p data logs

# Test the application
python run_multi_pair_recorder.py --help
```

### Step 4: Create Systemd Service (Recommended)

Create service file:

```bash
sudo nano /etc/systemd/system/valr-recorder.service
```

Add this configuration:

```ini
[Unit]
Description=VALR Orderbook Recorder - Multi-Pair
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/valr-recorder
Environment="PATH=/opt/valr-recorder/venv/bin"
ExecStart=/opt/valr-recorder/venv/bin/python run_multi_pair_recorder.py
Restart=always
RestartSec=10
StandardOutput=append:/opt/valr-recorder/logs/service.log
StandardError=append:/opt/valr-recorder/logs/service-error.log

# Resource limits
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable valr-recorder

# Start the service
sudo systemctl start valr-recorder

# Check status
sudo systemctl status valr-recorder

# View logs
sudo journalctl -u valr-recorder -f
```

### Step 5: Configure Log Rotation

Create log rotation config:

```bash
sudo nano /etc/logrotate.d/valr-recorder
```

Add:

```
/opt/valr-recorder/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 ubuntu ubuntu
    sharedscripts
    postrotate
        systemctl reload valr-recorder > /dev/null 2>&1 || true
    endscript
}
```

Test log rotation:

```bash
sudo logrotate -f /etc/logrotate.d/valr-recorder
```

---

## Monitoring and Maintenance

### Create Health Check Script

Create the script:

```bash
nano /opt/valr-recorder/health_check.sh
```

Add this content:

```bash
#!/bin/bash
# Health check script for VALR recorder

LOG_FILE="/opt/valr-recorder/logs/health_check.log"
DATA_DIR="/opt/valr-recorder/data"

echo "=== Health Check $(date) ===" >> $LOG_FILE

# Check if service is running
if systemctl is-active --quiet valr-recorder; then
    echo "✓ Service is running" >> $LOG_FILE
else
    echo "✗ Service is NOT running" >> $LOG_FILE
    sudo systemctl restart valr-recorder
fi

# Check disk space
DISK_USAGE=$(df -h /opt/valr-recorder | awk 'NR==2 {print $5}' | sed 's/%//')
echo "Disk usage: ${DISK_USAGE}%" >> $LOG_FILE

if [ $DISK_USAGE -gt 80 ]; then
    echo "⚠ WARNING: Disk usage above 80%" >> $LOG_FILE
fi

# Check database files
DB_COUNT=$(ls -1 $DATA_DIR/*.db 2>/dev/null | wc -l)
echo "Database files: $DB_COUNT" >> $LOG_FILE

# Check recent snapshots (last 5 minutes)
for db in $DATA_DIR/*.db; do
    if [ -f "$db" ]; then
        RECENT_COUNT=$(sqlite3 "$db" "SELECT COUNT(*) FROM orderbook_snapshots WHERE timestamp > datetime('now', '-5 minutes')" 2>/dev/null)
        echo "$(basename $db): $RECENT_COUNT snapshots in last 5 min" >> $LOG_FILE
    fi
done

echo "" >> $LOG_FILE
```

Make executable and schedule:

```bash
chmod +x /opt/valr-recorder/health_check.sh

# Run health check every 5 minutes
crontab -e
# Add this line: */5 * * * * /opt/valr-recorder/health_check.sh
```

### Create Backup Script

Create the script:

```bash
nano /opt/valr-recorder/backup.sh
```

Add this content:

```bash
#!/bin/bash
# Backup script for VALR recorder databases

BACKUP_DIR="/opt/valr-recorder/backups"
DATA_DIR="/opt/valr-recorder/data"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup all databases
for db in $DATA_DIR/*.db; do
    if [ -f "$db" ]; then
        DB_NAME=$(basename "$db" .db)
        echo "Backing up $DB_NAME..."
        sqlite3 "$db" ".backup '$BACKUP_DIR/${DB_NAME}_${DATE}.db'"
        gzip "$BACKUP_DIR/${DB_NAME}_${DATE}.db"
    fi
done

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.db.gz" -mtime +7 -delete

echo "Backup completed: $(date)"
```

Make executable and schedule:

```bash
chmod +x /opt/valr-recorder/backup.sh

# Daily backup at 2 AM
crontab -e
# Add this line: 0 2 * * * /opt/valr-recorder/backup.sh >> /opt/valr-recorder/logs/backup.log 2>&1
```

---

## Critical Things to Be Aware Of

### 1. Disk Space Management ⚠️ CRITICAL

**Problem:** Databases grow continuously and can fill disk

**Monitor disk usage:**
```bash
# Check disk space
df -h /opt/valr-recorder

# Check database sizes
du -sh /opt/valr-recorder/data/*.db

# Check total data directory size
du -sh /opt/valr-recorder/data/
```

**Best Practices:**
- Monitor daily via health check script
- Export old data to S3 monthly
- Set up CloudWatch alarm for disk space > 80%
- Consider increasing EBS volume if needed

### 2. Network Stability ⚠️ IMPORTANT

**Problem:** WebSocket disconnections lose data

**Solutions:**
- Code has auto-reconnect (5 sec retry) built-in
- Monitor connection logs for frequent disconnects
- Choose EC2 region with stable connection to VALR

**Test connectivity:**
```bash
# Test WebSocket connection
python3 -c "import websockets, asyncio; asyncio.run(websockets.connect('wss://api.valr.com/ws/trade'))"
```

### 3. Process Management ⚠️ CRITICAL

**Problem:** Process crashes = no data collection

**Solutions:**
- Use systemd (auto-restart on failure)
- Monitor with health check script
- Set up alerts for service down

**Useful commands:**
```bash
# Check service status
sudo systemctl status valr-recorder

# View real-time logs
sudo journalctl -u valr-recorder -f

# Restart service
sudo systemctl restart valr-recorder

# Check if process is running
ps aux | grep run_multi_pair_recorder
```

### 4. Data Backup ⚠️ IMPORTANT

**Problem:** Data loss if EC2 fails

**Option 1: EBS Snapshots**
```bash
# Create snapshot via AWS CLI
aws ec2 create-snapshot \
  --volume-id vol-xxxxx \
  --description "VALR recorder backup $(date +%Y%m%d)"
```

**Option 2: S3 Backup**
```bash
# Install AWS CLI
sudo apt install awscli

# Configure credentials
aws configure

# Sync to S3 daily
aws s3 sync /opt/valr-recorder/data/ s3://your-bucket/valr-backups/
```

### 5. Security ⚠️ CRITICAL

**Security Checklist:**
- ✅ SSH key authentication only (disable password)
- ✅ Security group: SSH from your IP only
- ✅ Keep system updated
- ✅ Enable automatic security updates
- ✅ Use IAM roles instead of access keys

**Enable automatic security updates:**
```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 6. Time Zone ⏰

**Important:** Database uses UTC timestamps

```bash
# Check system timezone
timedatectl

# Set to UTC (recommended)
sudo timedatectl set-timezone UTC
```

### 7. Python Environment 🐍

**Always use virtual environment:**
```bash
# Activate before any operations
source /opt/valr-recorder/venv/bin/activate

# Check Python version
python --version  # Should be 3.10+
```

### 8. Log Management 📝

**Problem:** Logs fill disk

**Solution:** Log rotation (already configured)

**Monitor log sizes:**
```bash
du -sh /opt/valr-recorder/logs/*
```

### 9. Database Performance 🚀

**SQLite optimization:**
```bash
# Enable WAL mode for better concurrency
sqlite3 /opt/valr-recorder/data/btc_zar_orderbook.db "PRAGMA journal_mode=WAL;"

# Vacuum databases monthly to reclaim space
sqlite3 /opt/valr-recorder/data/btc_zar_orderbook.db "VACUUM;"
```

### 10. Cost Optimization 💰

**Optimization tips:**
- Use Reserved Instances (1-year): Save 30-40%
- Use Savings Plans: Flexible savings
- Monitor with AWS Cost Explorer
- Set up billing alerts

---

## Troubleshooting Guide

### Service Won't Start

```bash
# Check logs for errors
sudo journalctl -u valr-recorder -n 50

# Check if port is in use
sudo netstat -tulpn | grep python

# Test manually
cd /opt/valr-recorder
source venv/bin/activate
python run_multi_pair_recorder.py

# Check permissions
ls -la /opt/valr-recorder/
```

### No Data Being Collected

```bash
# Check database
python query_data.py stats --all

# Check WebSocket connectivity
curl -I https://api.valr.com

# Check service logs
tail -f /opt/valr-recorder/logs/multi_recorder_*.log

# Check if databases are being written
watch -n 5 'ls -lh /opt/valr-recorder/data/*.db'
```

### Disk Full

```bash
# Find large files
du -sh /opt/valr-recorder/* | sort -h

# Export old data
python query_data.py export --pair BTC-ZAR --output old_data.csv
# Then delete old snapshots from database

# Increase EBS volume
aws ec2 modify-volume --volume-id vol-xxxxx --size 200

# After increasing, extend filesystem
sudo growpart /dev/xvda 1
sudo resize2fs /dev/xvda1
```

### High CPU Usage

```bash
# Check processes
htop

# Check number of connections
netstat -an | grep ESTABLISHED | wc -l

# Reduce pairs if needed
sudo systemctl stop valr-recorder
# Edit configuration to reduce pairs
sudo systemctl start valr-recorder
```

### WebSocket Connection Issues

```bash
# Check network connectivity
ping api.valr.com

# Check DNS resolution
nslookup api.valr.com

# Test WebSocket manually
python3 -c "import websockets, asyncio; asyncio.run(websockets.connect('wss://api.valr.com/ws/trade'))"

# Check firewall rules
sudo iptables -L -n
```

### Database Locked Errors

```bash
# Check for multiple processes accessing database
lsof /opt/valr-recorder/data/*.db

# Enable WAL mode
sqlite3 /opt/valr-recorder/data/btc_zar_orderbook.db "PRAGMA journal_mode=WAL;"

# Check database integrity
sqlite3 /opt/valr-recorder/data/btc_zar_orderbook.db "PRAGMA integrity_check;"
```

---

## Quick Start Deployment Script

Save this as `deploy.sh` and run on your EC2 instance:

```bash
#!/bin/bash
set -e

echo "=== VALR Orderbook Recorder Deployment ==="

# Install system dependencies
echo "Installing system dependencies..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git sqlite3

# Create application directory
echo "Creating application directory..."
sudo mkdir -p /opt/valr-recorder
sudo chown $USER:$USER /opt/valr-recorder
cd /opt/valr-recorder

# Setup Python environment
echo "Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install websockets

# Create directories
mkdir -p data logs backups

# Create systemd service
echo "Creating systemd service..."
sudo tee /etc/systemd/system/valr-recorder.service > /dev/null <<EOF
[Unit]
Description=VALR Orderbook Recorder
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/valr-recorder
Environment="PATH=/opt/valr-recorder/venv/bin"
ExecStart=/opt/valr-recorder/venv/bin/python run_multi_pair_recorder.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
echo "Enabling and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable valr-recorder
sudo systemctl start valr-recorder

echo ""
echo "✓ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Check status: sudo systemctl status valr-recorder"
echo "2. View logs: sudo journalctl -u valr-recorder -f"
echo "3. Check data: python query_data.py stats --all"
```

---

## Summary Checklist

Before going live, verify:

- [ ] EC2 instance launched with appropriate size (t3.small recommended)
- [ ] Security group configured (SSH + HTTPS outbound)
- [ ] Elastic IP allocated (optional but recommended)
- [ ] Code deployed to `/opt/valr-recorder`
- [ ] Virtual environment created and dependencies installed
- [ ] Systemd service configured and running
- [ ] Log rotation configured
- [ ] Health check script created and scheduled (every 5 minutes)
- [ ] Backup script created and scheduled (daily at 2 AM)
- [ ] Disk space monitoring enabled
- [ ] Tested data collection: `python query_data.py stats --all`
- [ ] Verified all 6 trading pairs are collecting data
- [ ] Set timezone to UTC
- [ ] Enabled automatic security updates
- [ ] Documented EC2 instance details (IP, volume ID, etc.)

**Post-Deployment Monitoring (First 24 Hours):**

- [ ] Check service status every hour
- [ ] Monitor disk space growth rate
- [ ] Verify WebSocket connections are stable
- [ ] Check database snapshot counts are increasing
- [ ] Review logs for any errors or warnings
- [ ] Test manual restart: `sudo systemctl restart valr-recorder`
- [ ] Verify service auto-starts after reboot

---

## Quick Reference Commands

```bash
# Service management
sudo systemctl status valr-recorder      # Check status
sudo systemctl restart valr-recorder     # Restart service
sudo systemctl stop valr-recorder        # Stop service
sudo systemctl start valr-recorder       # Start service
sudo journalctl -u valr-recorder -f      # View live logs

# Data queries
python query_data.py stats --all         # Show all stats
python query_data.py stats --pair BTC-ZAR  # Show specific pair
python query_data.py export --pair BTC-ZAR --output data.csv  # Export data

# System monitoring
df -h                                    # Check disk space
htop                                     # Check CPU/memory
du -sh /opt/valr-recorder/data/*.db      # Check database sizes
tail -f /opt/valr-recorder/logs/*.log    # View application logs

# Database operations
sqlite3 /opt/valr-recorder/data/btc_zar_orderbook.db "SELECT COUNT(*) FROM orderbook_snapshots;"
sqlite3 /opt/valr-recorder/data/btc_zar_orderbook.db "PRAGMA journal_mode=WAL;"
```

---

**You're ready to collect orderbook data 24/7 on AWS EC2!** 🚀

For questions or issues, refer to the [Troubleshooting Guide](#troubleshooting-guide) above.
