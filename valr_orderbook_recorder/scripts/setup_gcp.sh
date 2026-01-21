#!/bin/bash
# GCP VM Setup Script for VALR Orderbook Recorder
# Run this script on a fresh GCP VM (Ubuntu 20.04/22.04)

set -e

echo "=========================================="
echo "VALR Orderbook Recorder - GCP Setup"
echo "=========================================="

# Update system
echo "[1/5] Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Python 3.10+ and pip
echo "[2/5] Installing Python..."
sudo apt-get install -y python3 python3-pip python3-venv

# Create project directory
echo "[3/5] Setting up project directory..."
PROJECT_DIR="$HOME/valr_recorder"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Create virtual environment
echo "[4/5] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install websockets

# Create directory structure
mkdir -p data logs

echo "[5/5] Setup complete!"
echo ""
echo "Next steps:"
echo "1. Upload the project files to: $PROJECT_DIR"
echo "2. Run: cd $PROJECT_DIR && source venv/bin/activate"
echo "3. Start: python run_recorder.py"
echo ""
echo "Or use systemd service for auto-restart (see setup_service.sh)"
