# S3 Weekly Export Setup Guide

Simple guide to set up weekly automatic export to S3 with local data cleanup.

---

## Overview

**What this does:**
- Exports data to S3 every week (compressed CSV files)
- Keeps last 7 days of data locally
- Deletes older data to save disk space
- Organizes S3 files by year/month for easy access

**Storage usage:**
- Local: ~350 MB (7 days of data)
- S3: ~100 MB per week (compressed)
- Annual S3 cost: ~$1.50/year

---

## Step 1: ✅ S3 Bucket Already Created

Your S3 bucket is already set up:
- **Bucket name**: `valr-data`
- **Region**: `ap-southeast-2` (Asia Pacific - Sydney)
- **ARN**: `arn:aws:s3:::valr-data`

The export script has been configured to use this bucket.

---

## Step 2: Create IAM Role for EC2

**Your EC2 Instance**: `i-08090f49dc147f9fc` (ap-southeast-2)

**Option A: Using AWS Console**

1. Go to IAM → Roles → Create Role
2. Select "AWS Service" → "EC2"
3. Create a new policy with this JSON:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::valr-data/*",
        "arn:aws:s3:::valr-data"
      ]
    }
  ]
}
```

4. Name the role: `valr-recorder-s3-access`
5. Attach role to EC2 instance: `i-08090f49dc147f9fc`

**Option B: Using AWS CLI**

```bash
# Create trust policy
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
    --role-name valr-recorder-s3-access \
    --assume-role-policy-document file://trust-policy.json

# Create and attach policy
cat > s3-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::valr-data/*",
        "arn:aws:s3:::valr-data"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
    --role-name valr-recorder-s3-access \
    --policy-name S3Access \
    --policy-document file://s3-policy.json

# Create instance profile
aws iam create-instance-profile \
    --instance-profile-name valr-recorder-s3-profile

# Add role to instance profile
aws iam add-role-to-instance-profile \
    --instance-profile-name valr-recorder-s3-profile \
    --role-name valr-recorder-s3-access

# Attach to EC2 instance
aws ec2 associate-iam-instance-profile \
    --instance-id i-08090f49dc147f9fc \
    --iam-instance-profile Name=valr-recorder-s3-profile \
    --region ap-southeast-2
```

---

## Step 3: Deploy Export Script on EC2

```bash
# SSH to your EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Navigate to project directory
cd /opt/valr-recorder

# Create exports directory
mkdir -p exports

# The export script is already configured with:
# - S3_BUCKET="valr-data"
# - AWS_REGION="ap-southeast-2"
# No need to edit the script!

# Make script executable
chmod +x export_to_s3.sh

# Install AWS CLI if not already installed
sudo apt install awscli -y

# Test AWS access (should work after IAM role is attached)
aws s3 ls s3://valr-data --region ap-southeast-2
```

---

## Step 4: Test the Export Script

```bash
# Run manually first to test
cd /opt/valr-recorder
./export_to_s3.sh

# Check the log
tail -f logs/export.log

# Verify files in S3
aws s3 ls s3://valr-data/valr-orderbook/ --recursive --region ap-southeast-2

# Check local disk usage
df -h /opt/valr-recorder
du -sh data/*.db
```

---

## Step 5: Schedule Weekly Export

```bash
# Edit crontab
crontab -e

# Add this line (runs every Sunday at 2 AM)
0 2 * * 0 /opt/valr-recorder/export_to_s3.sh

# Verify cron job
crontab -l
```

---

## How to Access Your Data

### Method 1: Download Specific Week

```bash
# List available files
aws s3 ls s3://valr-data/valr-orderbook/2025/01/ --region ap-southeast-2

# Download specific file
aws s3 cp s3://valr-data/valr-orderbook/2025/01/btc_zar_20250122.csv.gz ./ --region ap-southeast-2

# Decompress
gunzip btc_zar_20250122.csv.gz

# Query with Python
python3 << EOF
import pandas as pd
df = pd.read_csv('btc_zar_20250122.csv')

# SQL-like queries
print(df.query('mid_price > 1000000').head())
print(df.groupby('trading_pair')['spread'].mean())
EOF
```

### Method 2: Batch Download All Data

```bash
# Download all data
aws s3 sync s3://valr-data/valr-orderbook/ ./all-data/ --region ap-southeast-2

# Decompress all files
find ./all-data -name "*.gz" -exec gunzip {} \;

# Now you have all CSV files locally
ls -lh ./all-data/**/*.csv
```

### Method 3: Query with pandas (SQL-like)

```python
import pandas as pd
import glob

# Load all CSV files
all_files = glob.glob("./all-data/**/*.csv", recursive=True)
df = pd.concat([pd.read_csv(f) for f in all_files])

# SQL-like queries
result = df.query('trading_pair == "BTC-ZAR" and mid_price > 1000000')

# Aggregations
daily_avg = df.groupby([pd.to_datetime(df['timestamp']).dt.date, 'trading_pair']).agg({
    'mid_price': 'mean',
    'spread': 'mean',
    'bid_depth': 'sum'
})

print(daily_avg)
```

---

## S3 File Structure

```
s3://your-bucket/valr-orderbook/
├── 2025/
│   ├── 01/
│   │   ├── btc_zar_20250115.csv.gz
│   │   ├── btc_zar_20250122.csv.gz
│   │   ├── eth_zar_20250115.csv.gz
│   │   ├── eth_zar_20250122.csv.gz
│   │   ├── usdt_zar_20250115.csv.gz
│   │   └── ... (6 pairs × 4 weeks = 24 files/month)
│   └── 02/
│       └── ...
```

---

## Monitoring and Maintenance

### Check Export Status

```bash
# View export log
tail -50 /opt/valr-recorder/logs/export.log

# Check last export date
ls -lt /opt/valr-recorder/logs/export.log

# Verify S3 uploads
aws s3 ls s3://valr-data/valr-orderbook/ --recursive --region ap-southeast-2 | tail -20
```

### Check Disk Usage

```bash
# Check overall disk usage
df -h

# Check database sizes
du -sh /opt/valr-recorder/data/*.db

# Check how many days of data
for db in /opt/valr-recorder/data/*.db; do
    echo "=== $(basename $db) ==="
    sqlite3 "$db" "SELECT
        MIN(timestamp) as first_snapshot,
        MAX(timestamp) as last_snapshot,
        COUNT(*) as total_snapshots
    FROM orderbook_snapshots"
done
```

### Manual Cleanup (if needed)

```bash
# Delete data older than 7 days
CUTOFF_DATE=$(date -d "7 days ago" +%Y-%m-%d)

for db in /opt/valr-recorder/data/*.db; do
    sqlite3 "$db" "DELETE FROM orderbook_snapshots WHERE timestamp < '$CUTOFF_DATE'"
    sqlite3 "$db" "VACUUM"
done
```

---

## Cost Estimate

**S3 Storage:**
- Weekly export: ~100 MB compressed
- Annual data: 100 MB × 52 weeks = 5.2 GB
- Cost: 5.2 GB × $0.023/GB/month = **$0.12/month** or **$1.44/year**

**Data Transfer:**
- Upload to S3: Free (within same region)
- Download from S3: First 100 GB/month free

**Total: ~$1.50/year** (almost free!)

---

## Troubleshooting

### Export script fails

```bash
# Check AWS credentials
aws sts get-caller-identity --region ap-southeast-2

# Check S3 access
aws s3 ls s3://valr-data/ --region ap-southeast-2

# Run script manually with verbose output
bash -x /opt/valr-recorder/export_to_s3.sh
```

### Disk still filling up

```bash
# Check actual data growth
du -sh /opt/valr-recorder/data/*.db

# Reduce retention to 7 days
# Edit export_to_s3.sh: RETENTION_DAYS=7

# Run cleanup manually
./export_to_s3.sh
```

### Cannot download from S3

```bash
# Check IAM permissions
aws s3 ls s3://valr-data/ --region ap-southeast-2

# Use AWS Console to download
# Go to S3 → valr-data bucket → Download files
```

---

## Summary

✅ **Simple**: One script, runs weekly automatically
✅ **Cheap**: ~$1.50/year for S3 storage
✅ **SQL-like access**: Use pandas to query CSV files
✅ **Batch download**: Download all data with one command
✅ **Safe**: Keeps 7 days locally, everything in S3

**Next steps:**
1. Create S3 bucket
2. Attach IAM role to EC2
3. Deploy and test export script
4. Schedule weekly cron job
5. Done!
