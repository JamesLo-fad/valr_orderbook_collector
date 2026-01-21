#!/bin/bash
# Weekly Export to S3 Script
# Exports orderbook data to S3 and cleans up old local data

set -e

# Configuration
S3_BUCKET="valr-data"  # S3 bucket in ap-southeast-2
AWS_REGION="ap-southeast-2"
EXPORT_DIR="/opt/valr-recorder/exports"
DATA_DIR="/opt/valr-recorder/data"
LOG_FILE="/opt/valr-recorder/logs/export.log"
RETENTION_DAYS=7  # Keep last 7 days locally

# Trading pairs
PAIRS=("USDT-ZAR" "SOL-ZAR" "ETH-ZAR" "BTC-ZAR" "XRP-ZAR" "BNB-ZAR")

# Date for export filename
EXPORT_DATE=$(date +%Y%m%d)
YEAR=$(date +%Y)
MONTH=$(date +%m)

echo "=== Weekly Export Started: $(date) ===" >> $LOG_FILE

# Create export directory
mkdir -p $EXPORT_DIR

# Activate virtual environment
cd /opt/valr-recorder
source venv/bin/activate

# Export each trading pair
for pair in "${PAIRS[@]}"; do
    echo "Exporting $pair..." >> $LOG_FILE

    # Calculate date range (last 7 days)
    START_DATE=$(date -d "7 days ago" +%Y-%m-%d)
    END_DATE=$(date +%Y-%m-%d)

    # Export to CSV
    CSV_FILE="${EXPORT_DIR}/${pair,,}_${EXPORT_DATE}.csv"
    CSV_FILE=$(echo $CSV_FILE | tr '-' '_')

    python query_data.py export \
        --pair "$pair" \
        --start "$START_DATE" \
        --end "$END_DATE" \
        --output "$CSV_FILE" >> $LOG_FILE 2>&1

    if [ -f "$CSV_FILE" ]; then
        # Compress the CSV
        gzip "$CSV_FILE"
        CSV_GZ="${CSV_FILE}.gz"

        # Upload to S3
        S3_PATH="s3://${S3_BUCKET}/valr-orderbook/${YEAR}/${MONTH}/$(basename $CSV_GZ)"
        aws s3 cp "$CSV_GZ" "$S3_PATH" --region "$AWS_REGION" >> $LOG_FILE 2>&1

        if [ $? -eq 0 ]; then
            echo "✓ Uploaded $pair to $S3_PATH" >> $LOG_FILE
            rm "$CSV_GZ"
        else
            echo "✗ Failed to upload $pair" >> $LOG_FILE
        fi
    else
        echo "✗ No data exported for $pair" >> $LOG_FILE
    fi
done

# Clean up old local data (older than RETENTION_DAYS)
echo "Cleaning up old local data..." >> $LOG_FILE
CUTOFF_DATE=$(date -d "${RETENTION_DAYS} days ago" +%Y-%m-%d)

for db in $DATA_DIR/*.db; do
    if [ -f "$db" ]; then
        DB_NAME=$(basename "$db" .db)
        PAIR_NAME=$(echo $DB_NAME | sed 's/_orderbook//' | tr '_' '-' | tr '[:lower:]' '[:upper:]')

        # Delete old snapshots
        sqlite3 "$db" "DELETE FROM orderbook_snapshots WHERE timestamp < '$CUTOFF_DATE'" >> $LOG_FILE 2>&1

        # Vacuum to reclaim space
        sqlite3 "$db" "VACUUM" >> $LOG_FILE 2>&1

        echo "✓ Cleaned $PAIR_NAME (kept last $RETENTION_DAYS days)" >> $LOG_FILE
    fi
done

# Clean up export directory
rm -rf $EXPORT_DIR

echo "=== Weekly Export Completed: $(date) ===" >> $LOG_FILE
echo "" >> $LOG_FILE
