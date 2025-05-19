#!/bin/bash

set -e

# Activate our virtual environment
. /opt/pysetup/.venv/bin/activate

# Set Python path to include the project root
export PYTHONPATH="${PYTHONPATH:-/home/appuser}"

# Print environment information
echo "=== Environment Information ==="
echo "PYTHONPATH: $PYTHONPATH"
echo "Python version: $(python3 --version)"
echo "Working directory: $(pwd)"
echo "=== End Environment Information ==="

# Set jumbo packets on network interface if needed
if [ "${SET_JUMBO_MTU:-false}" = "true" ]; then
    # Attempt to find the default interface
    INTERFACE=$(ip -o -4 route show to default | awk '{print $5}')
    if [ -n "$INTERFACE" ]; then
        echo "Attempting to set MTU to 9000 on interface $INTERFACE..."
        # Try to set MTU, but don't fail if it doesn't work
        ip link set dev "$INTERFACE" mtu 9000 || echo "Failed to set MTU on $INTERFACE"
        
        # Verify the MTU setting
        CURRENT_MTU=$(ip link show dev "$INTERFACE" | grep -oP 'mtu\s+\K\d+')
        echo "Interface $INTERFACE now has MTU: $CURRENT_MTU"
    else
        echo "Warning: Could not determine default interface to set MTU."
    fi
else
    echo "Skipping jumbo MTU configuration (SET_JUMBO_MTU not set to true)"
fi

# Check if we're in development mode with auto-reload
if [ "${APP_RELOAD:-false}" = "true" ]; then
    echo "Starting application in development mode with auto-reload..."
    exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8009 --reload
else
    echo "Starting application in production mode..."
    # Evaluating passed command:
    exec "$@"
fi