#!/bin/bash
# Setup systemd service for auto-restart and persistence

set -e

SERVICE_NAME="valr-recorder"
PROJECT_DIR="$HOME/valr_recorder"
USER=$(whoami)

echo "Setting up systemd service: $SERVICE_NAME"

# Create service file
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=VALR Orderbook Recorder
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/run_recorder.py
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_DIR/logs/recorder.log
StandardError=append:$PROJECT_DIR/logs/recorder.log

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME

echo ""
echo "Service installed and started!"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status $SERVICE_NAME   # Check status"
echo "  sudo systemctl stop $SERVICE_NAME     # Stop service"
echo "  sudo systemctl restart $SERVICE_NAME  # Restart service"
echo "  tail -f $PROJECT_DIR/logs/recorder.log  # View logs"
