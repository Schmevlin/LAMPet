#!/bin/bash

# set -e

echo "Stopping services..."
sudo systemctl stop lampi_app.service
sudo systemctl stop lampi_service.service

# echo "Starting lampi_service.py..."
# python3 lamp_service.py &
# SERVICE_PID=$!

# echo "Waiting for lampi_service.py to be ready..."

# # wait until process exists and is stable
# sleep 1

# echo "Starting main.py..."
# python3 main.py &
# MAIN_PID=$!

# echo "Done"