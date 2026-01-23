# Service Management & Verification Guide

Complete guide for managing the VALR orderbook recorder systemd service and verifying data collection.

---

## Table of Contents

1. [Understanding Systemd Services](#understanding-systemd-services)
2. [Service Management Commands](#service-management-commands)
3. [Verifying Data Collection](#verifying-data-collection)
4. [Troubleshooting Service Issues](#troubleshooting-service-issues)
5. [Common Scenarios](#common-scenarios)

---

## Understanding Systemd Services

### What is Systemd?

Systemd is Linux's system and service manager. When you run your application as a systemd service:

✅ **Runs in background** - Independent of your SSH session
✅ **Survives logout** - Keeps running when you disconnect
✅ **Auto-starts on boot** - Starts automatically when EC2 reboots
✅ **Auto-restarts on failure** - Automatically recovers from crashes
✅ **Centralized logging** - All logs managed by systemd journal

### Service vs Manual Execution

**Manual execution** (foreground):
```bash
python run_multi_pair_recorder.py
# Stops when you logout or press Ctrl+C
```

**Systemd service** (background):
```bash
sudo systemctl start valr-recorder
# Keeps running after logout, survives reboots
```

---

## Service Management Commands

### Basic Service Control

#### Start the Service
```bash
sudo systemctl start valr-recorder
```
**What it does:** Starts the data collection service
**Expected result:** Service begins running in background
**When to use:** After creating/editing service file, or after stopping it

#### Stop the Service
```bash
sudo systemctl stop valr-recorder
```
**What it does:** Gracefully stops the service (sends SIGTERM)
**Expected result:** Service stops within 90 seconds (may take time to close WebSocket connections)
**When to use:** Before editing code, or to temporarily pause collection

**Note:** If it hangs, press Ctrl+C and use force kill:
```bash
sudo systemctl kill valr-recorder
```

#### Restart the Service
```bash
sudo systemctl restart valr-recorder
```
**What it does:** Stops then starts the service
**Expected result:** Service restarts with fresh connections
**When to use:** After updating code or configuration

#### Check Service Status
```bash
sudo systemctl status valr-recorder
```
**What it shows:**
- ✅ **Active: active (running)** - Service is running correctly
- ❌ **Active: failed** - Service crashed or failed to start
- ⏸️ **Active: inactive (dead)** - Service is stopped

**How to exit:** Press `q` to quit the status view

**Example output:**
```
● valr-recorder.service - VALR Orderbook Recorder - Multi-Pair
     Loaded: loaded (/etc/systemd/system/valr-recorder.service; enabled)
     Active: active (running) since Fri 2026-01-23 07:34:40 UTC; 13min ago
   Main PID: 582 (python)
      Tasks: 3
     Memory: 61.7M
        CPU: 1min 25.933s
```

**What to look for:**
- `Active: active (running)` ✅ Good!
- `Main PID: 582` - Process ID (should stay constant)
- `Memory: 61.7M` - Memory usage (normal: 50-100MB)
- `enabled` - Will auto-start on boot

### Advanced Service Management

#### Enable Auto-Start on Boot
```bash
sudo systemctl enable valr-recorder
```
**What it does:** Service will automatically start when EC2 boots
**Expected result:** `Created symlink...` message
**When to use:** During initial setup (only need to do once)

#### Disable Auto-Start
```bash
sudo systemctl disable valr-recorder
```
**What it does:** Service won't auto-start on boot
**When to use:** If you want manual control over when service runs

#### Reload Service Configuration
```bash
sudo systemctl daemon-reload
```
**What it does:** Reloads systemd configuration after editing service file
**Expected result:** No output (silent success)
**When to use:** **Always** after editing `/etc/systemd/system/valr-recorder.service`

---

## Verifying Data Collection

### Method 1: Check Statistics (Recommended)

```bash
cd ~/valr_orderbook_collector
source .venv/bin/activate
python query_data.py stats --all
```

**What it shows:**
- Number of snapshots collected per trading pair
- Database file sizes
- First and last snapshot timestamps
- Date range of collected data

**Example output:**
```
USDT-ZAR:
  Snapshots: 1,200
  Size: 0.29 MB
  First: 2026-01-23T07:42:08.638331
  Last: 2026-01-23T07:44:27.629907
```

**How to verify it's working:**
1. Run the command
2. Wait 30-60 seconds
3. Run it again
4. ✅ Snapshot counts should increase
5. ✅ "Last" timestamp should be more recent

**If snapshot counts don't increase:** Service is not collecting data (see troubleshooting)

### Method 2: Watch Database Files Grow

```bash
watch -n 5 'ls -lh ~/valr_orderbook_collector/data/*.db'
```

**What it does:** Updates every 5 seconds showing database file sizes
**What to look for:** File sizes should gradually increase
**How to exit:** Press Ctrl+C

**Example output:**
```
-rw-r--r-- 1 ubuntu ubuntu  24K Jan 23 07:44 bnb_zar_orderbook.db
-rw-r--r-- 1 ubuntu ubuntu 604K Jan 23 07:44 btc_zar_orderbook.db
-rw-r--r-- 1 ubuntu ubuntu 476K Jan 23 07:44 eth_zar_orderbook.db
```

### Method 3: Monitor Application Logs

```bash
tail -f ~/valr_orderbook_collector/logs/service.log
```

**What it shows:** Real-time application logs
**What to look for:**
- ✅ `Connected to VALR WebSocket`
- ✅ `Subscribed to FULL_ORDERBOOK_UPDATE`
- ✅ `Progress: X snapshots | Elapsed: ...`

**How to exit:** Press Ctrl+C

**Filter for progress updates only:**
```bash
tail -f ~/valr_orderbook_collector/logs/service.log | grep "Progress"
```

### Method 4: Check System Logs

```bash
sudo journalctl -u valr-recorder -f
```

**What it shows:** Systemd journal logs (system-level)
**What to look for:**
- ✅ `Started valr-recorder.service`
- ❌ `Failed with result 'exit-code'`
- ❌ `Main process exited, code=exited, status=209`

**How to exit:** Press Ctrl+C

**View last 50 lines:**
```bash
sudo journalctl -u valr-recorder -n 50
```

**View logs since specific time:**
```bash
sudo journalctl -u valr-recorder --since "10 minutes ago"
```

### Method 5: Check Process is Running

```bash
ps aux | grep run_multi_pair_recorder
```

**What it shows:** Running Python processes
**Expected output:**
```
ubuntu    582  1.2  2.8  python run_multi_pair_recorder.py
```

**What to look for:**
- ✅ Should show one process
- ❌ If no output: Service is not running

---

## Troubleshooting Service Issues

### Issue 1: Service Shows "Active" but No Data Collected

**Symptoms:**
- `systemctl status` shows "active (running)"
- But `query_data.py stats --all` shows no new snapshots

**Diagnosis:**
```bash
# Check if process is actually running
ps aux | grep run_multi_pair_recorder

# Check application logs for errors
tail -50 ~/valr_orderbook_collector/logs/service.log
tail -50 ~/valr_orderbook_collector/logs/service-error.log
```

**Common causes:**
1. **Wrong working directory in service file**
2. **Missing virtual environment**
3. **WebSocket connection failed**

**Solution:**
```bash
# Verify service file paths
sudo cat /etc/systemd/system/valr-recorder.service

# Should show:
# WorkingDirectory=/home/ubuntu/valr_orderbook_collector
# ExecStart=/home/ubuntu/valr_orderbook_collector/.venv/bin/python run_multi_pair_recorder.py
```

### Issue 2: Service Fails to Start (Exit Code 209)

**Symptoms:**
```
Main process exited, code=exited, status=209/STDOUT
Failed to set up standard output: No such file or directory
```

**Cause:** Log directory doesn't exist

**Solution:**
```bash
mkdir -p ~/valr_orderbook_collector/logs
sudo systemctl restart valr-recorder
```

### Issue 3: Service Won't Stop (Hangs)

**Symptoms:**
- `sudo systemctl stop valr-recorder` hangs for 90+ seconds
- Eventually times out and force kills

**Cause:** Python script doesn't handle SIGTERM gracefully

**Solution:**
```bash
# Press Ctrl+C to cancel the stop command

# Force kill the service
sudo systemctl kill valr-recorder

# Verify it stopped
sudo systemctl status valr-recorder
```

### Issue 4: Wrong Path in Service File

**Symptoms:**
```
Failed to execute command: No such file or directory
```

**Diagnosis:**
```bash
# Check what paths are in service file
sudo cat /etc/systemd/system/valr-recorder.service | grep Directory
sudo cat /etc/systemd/system/valr-recorder.service | grep ExecStart

# Check where your code actually is
ls -la ~/valr_orderbook_collector/
ls -la ~/valr_orderbook_collector/.venv/bin/python
```

**Solution:**
```bash
# Edit service file
sudo nano /etc/systemd/system/valr-recorder.service

# Update paths to match your actual location:
# WorkingDirectory=/home/ubuntu/valr_orderbook_collector
# Environment="PATH=/home/ubuntu/valr_orderbook_collector/.venv/bin"
# ExecStart=/home/ubuntu/valr_orderbook_collector/.venv/bin/python run_multi_pair_recorder.py
# StandardOutput=append:/home/ubuntu/valr_orderbook_collector/logs/service.log
# StandardError=append:/home/ubuntu/valr_orderbook_collector/logs/service-error.log

# Save: Ctrl+X, Y, Enter

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart valr-recorder
```

---

## Common Scenarios

### Scenario 1: First Time Setup

```bash
# 1. Create service file
sudo nano /etc/systemd/system/valr-recorder.service
# (paste service configuration)

# 2. Reload systemd
sudo systemctl daemon-reload

# 3. Enable auto-start
sudo systemctl enable valr-recorder

# 4. Start service
sudo systemctl start valr-recorder

# 5. Verify it's running
sudo systemctl status valr-recorder

# 6. Check data collection
cd ~/valr_orderbook_collector
source .venv/bin/activate
python query_data.py stats --all
```

### Scenario 2: After Code Update

```bash
# 1. Stop service
sudo systemctl stop valr-recorder

# 2. Update code (git pull, edit files, etc.)
cd ~/valr_orderbook_collector
git pull

# 3. Update dependencies if needed
source .venv/bin/activate
pip install -r requirements.txt

# 4. Restart service
sudo systemctl start valr-recorder

# 5. Verify it's working
sudo journalctl -u valr-recorder -f
# Press Ctrl+C after seeing "Connected to VALR WebSocket"
```

### Scenario 3: After EC2 Reboot

```bash
# SSH back into EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# 1. Check if service auto-started
sudo systemctl status valr-recorder

# 2. If not running, start it
sudo systemctl start valr-recorder

# 3. Verify data collection resumed
cd ~/valr_orderbook_collector
source .venv/bin/activate
python query_data.py stats --all
```

### Scenario 4: Verifying Background Operation

```bash
# 1. Check service is running
sudo systemctl status valr-recorder

# 2. Note current snapshot counts
python query_data.py stats --all

# 3. Logout
exit

# 4. Wait 5 minutes

# 5. SSH back in
ssh -i your-key.pem ubuntu@your-ec2-ip

# 6. Verify service still running
sudo systemctl status valr-recorder

# 7. Verify snapshots increased
cd ~/valr_orderbook_collector
source .venv/bin/activate
python query_data.py stats --all
# Snapshot counts should be higher than before!
```

### Scenario 5: Checking Service Health Daily

```bash
# Quick health check script
cd ~/valr_orderbook_collector
source .venv/bin/activate

echo "=== Service Status ==="
sudo systemctl status valr-recorder | grep "Active:"

echo -e "\n=== Data Collection Stats ==="
python query_data.py stats --all

echo -e "\n=== Disk Usage ==="
df -h ~ | grep -E "Filesystem|/$"
du -sh data/

echo -e "\n=== Recent Errors ==="
sudo journalctl -u valr-recorder --since "24 hours ago" | grep -i error | tail -5
```

---

## Quick Reference

### Essential Commands

```bash
# Service control
sudo systemctl start valr-recorder       # Start service
sudo systemctl stop valr-recorder        # Stop service
sudo systemctl restart valr-recorder     # Restart service
sudo systemctl status valr-recorder      # Check status (press 'q' to exit)

# After editing service file
sudo systemctl daemon-reload             # Reload configuration
sudo systemctl restart valr-recorder     # Apply changes

# View logs
sudo journalctl -u valr-recorder -f      # Live system logs (Ctrl+C to exit)
tail -f ~/valr_orderbook_collector/logs/service.log  # Live app logs (Ctrl+C to exit)

# Verify data collection
cd ~/valr_orderbook_collector
source .venv/bin/activate
python query_data.py stats --all         # Check snapshot counts
```

### Service File Location

```
/etc/systemd/system/valr-recorder.service
```

### Log File Locations

```
~/valr_orderbook_collector/logs/service.log        # Application output
~/valr_orderbook_collector/logs/service-error.log  # Application errors
sudo journalctl -u valr-recorder                   # System logs
```

---

## Understanding Service States

| State | Meaning | What to Do |
|-------|---------|------------|
| `active (running)` | ✅ Service is running | Verify data collection with `query_data.py` |
| `active (exited)` | ⚠️ Service started but exited | Check logs for errors |
| `inactive (dead)` | ⏸️ Service is stopped | Start with `systemctl start` |
| `failed` | ❌ Service crashed | Check logs, fix issue, restart |
| `activating (auto-restart)` | 🔄 Service is restarting | Wait or check logs for errors |

---

**You're now ready to manage and monitor your VALR orderbook recorder service!** 🚀

For deployment instructions, see [AWS_DEPLOYMENT_GUIDE.md](AWS_DEPLOYMENT_GUIDE.md)
For S3 export setup, see [S3_EXPORT_GUIDE.md](S3_EXPORT_GUIDE.md)
