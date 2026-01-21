# VALR Orderbook Recorder - Deployment Checklist

Quick checklist for deploying to EC2 with S3 weekly export.

---

## Your Configuration

- **EC2 Instance**: `i-08090f49dc147f9fc` (ap-southeast-2)
- **S3 Bucket**: `valr-data` (ap-southeast-2)
- **Storage**: 8 GiB gp3 (sufficient for 7 days local retention)
- **Trading Pairs**: USDT-ZAR, SOL-ZAR, ETH-ZAR, BTC-ZAR, XRP-ZAR, BNB-ZAR

---

## Pre-Deployment (Local)

- [x] S3 bucket created: `valr-data`
- [x] Export script configured with bucket name and region
- [ ] Code pushed to GitHub: https://github.com/JamesLo-fad/valr_orderbook_collector.git

---

## Step 1: IAM Role Setup

Attach IAM role to EC2 instance for S3 access.

**Quick CLI Command:**
```bash
# See S3_EXPORT_GUIDE.md Step 2 for detailed instructions
aws ec2 associate-iam-instance-profile \
    --instance-id i-08090f49dc147f9fc \
    --iam-instance-profile Name=valr-recorder-s3-profile \
    --region ap-southeast-2
```

**Or use AWS Console:**
1. IAM → Roles → Create Role → EC2
2. Create policy with S3 access to `valr-data` bucket
3. Attach to instance `i-08090f49dc147f9fc`

📖 **Detailed instructions**: See `S3_EXPORT_GUIDE.md` Step 2

**Verify:**
```bash
aws ec2 describe-instances \
    --instance-ids i-08090f49dc147f9fc \
    --region ap-southeast-2 \
    --query 'Reservations[0].Instances[0].IamInstanceProfile'
```

---

## Step 2: Deploy to EC2

```bash
# SSH to EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Clone repository
cd /opt
sudo git clone https://github.com/JamesLo-fad/valr_orderbook_collector.git valr-recorder
sudo chown -R ubuntu:ubuntu valr-recorder
cd valr-recorder

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create directories
mkdir -p data logs exports

# Test AWS S3 access
aws s3 ls s3://valr-data --region ap-southeast-2
# Should list bucket contents (empty is OK)
```

---

## Step 3: Set Up Systemd Service

Create systemd service for automatic startup and restart.

📖 **Detailed instructions**: See `AWS_DEPLOYMENT_GUIDE.md` Section 4

**Quick setup:**
```bash
sudo nano /etc/systemd/system/valr-recorder.service
```

Paste this content:
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

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable valr-recorder
sudo systemctl start valr-recorder
sudo systemctl status valr-recorder
```

---

## Step 4: Test Export Script

Test S3 export before scheduling.

📖 **Detailed instructions**: See `S3_EXPORT_GUIDE.md` Step 4

```bash
cd /opt/valr-recorder
chmod +x export_to_s3.sh

# Run manual test
./export_to_s3.sh

# Check logs and S3
tail -f logs/export.log
aws s3 ls s3://valr-data/valr-orderbook/ --recursive --region ap-southeast-2
```

---

## Step 5: Schedule Weekly Export

Set up cron job for automatic weekly export.

📖 **Detailed instructions**: See `S3_EXPORT_GUIDE.md` Step 5

```bash
crontab -e

# Add this line (runs every Sunday at 2 AM)
0 2 * * 0 /opt/valr-recorder/export_to_s3.sh

# Verify
crontab -l
```

---

## Step 6: Monitoring

### Daily Checks (First Week)

```bash
# Check service status
sudo systemctl status valr-recorder

# Check data collection
python query_data.py stats --all

# Check disk usage
df -h /opt/valr-recorder
du -sh data/*.db
```

### Weekly Checks

```bash
# Verify S3 exports
aws s3 ls s3://valr-data/valr-orderbook/ --recursive --region ap-southeast-2

# Check export logs
tail -50 logs/export.log

# Verify local data retention (should be ~7 days)
for db in data/*.db; do
    echo "=== $(basename $db) ==="
    sqlite3 "$db" "SELECT
        MIN(timestamp) as first_snapshot,
        MAX(timestamp) as last_snapshot,
        COUNT(*) as total_snapshots
    FROM orderbook_snapshots"
done
```

---

## Storage Estimates

**Current Configuration:**
- Local retention: 7 days
- 6 trading pairs
- ~1 KB per snapshot
- Estimated: ~3.5 GB for 7 days

**If disk fills up:**
```bash
# Check actual usage
du -sh data/*.db

# Reduce retention to 3 days if needed
nano export_to_s3.sh
# Change: RETENTION_DAYS=3

# Run cleanup manually
./export_to_s3.sh
```

---

## Data Access

📖 **Detailed instructions**: See `S3_EXPORT_GUIDE.md` - "How to Access Your Data"

### Download Specific Week
```bash
aws s3 cp s3://valr-data/valr-orderbook/2025/01/btc_zar_20250122.csv.gz ./ --region ap-southeast-2
gunzip btc_zar_20250122.csv.gz
```

### Batch Download All Data
```bash
aws s3 sync s3://valr-data/valr-orderbook/ ./all-data/ --region ap-southeast-2
find ./all-data -name "*.gz" -exec gunzip {} \;
```

### Query with pandas (SQL-like)
```python
import pandas as pd
df = pd.read_csv('btc_zar_20250122.csv')
result = df.query('mid_price > 1000000')
daily_avg = df.groupby('trading_pair')['spread'].mean()
```

---

## Troubleshooting

📖 **Detailed troubleshooting**: See `AWS_DEPLOYMENT_GUIDE.md` Section 10

### Service not starting
```bash
sudo journalctl -u valr-recorder -n 50
tail -f logs/service-error.log
```

### Export failing
```bash
aws sts get-caller-identity --region ap-southeast-2
aws s3 ls s3://valr-data/ --region ap-southeast-2
bash -x export_to_s3.sh
```

### Disk filling up
```bash
du -sh data/*.db
nano export_to_s3.sh  # Change RETENTION_DAYS=3
./export_to_s3.sh
```

---

## Cost Estimate

- **EC2 t3.small**: ~$15/month (24/7)
- **S3 Storage**: ~$0.12/month (5 GB/year)
- **Data Transfer**: Free (within same region)
- **Total**: ~$15.12/month

---

## Next Steps After Deployment

1. Monitor for 24 hours to ensure stable data collection
2. Wait 7 days for first weekly export
3. Verify S3 export works correctly
4. Set up CloudWatch alarms (optional)
5. Document any custom configurations

---

## Quick Reference

**Service Commands:**
```bash
sudo systemctl start valr-recorder    # Start service
sudo systemctl stop valr-recorder     # Stop service
sudo systemctl restart valr-recorder  # Restart service
sudo systemctl status valr-recorder   # Check status
```

**Log Files:**
- Service logs: `/opt/valr-recorder/logs/service.log`
- Export logs: `/opt/valr-recorder/logs/export.log`
- Error logs: `/opt/valr-recorder/logs/service-error.log`

**Data Locations:**
- Local databases: `/opt/valr-recorder/data/*.db`
- S3 exports: `s3://valr-data/valr-orderbook/YYYY/MM/`

---

## Support

- Full deployment guide: `AWS_DEPLOYMENT_GUIDE.md`
- S3 export details: `S3_EXPORT_GUIDE.md`
- GitHub: https://github.com/JamesLo-fad/valr_orderbook_collector
