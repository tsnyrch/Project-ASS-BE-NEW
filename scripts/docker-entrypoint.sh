#!/bin/bash

set -e

# Activate our virtual environment
. /opt/pysetup/.venv/bin/activate

# Set jumbo packets on network interface if needed
if [ "${SET_JUMBO_MTU:-false}" = "true" ]; then
    # Attempt to find the default interface
    INTERFACE=$(ip -o -4 route show to default | awk '{print $5}')
    if [ -n "$INTERFACE" ]; then
        echo "Attempting to set MTU to 9000 on interface $INTERFACE..."
        # Try to set MTU, but don't fail if it doesn't work
        ip link set dev "$INTERFACE" mtu 9000 || echo "Failed to set MTU on $INTERFACE"
        echo "MTU set on $INTERFACE."
    else
        echo "Warning: Could not determine default interface to set MTU."
    fi
fi

# Evaluating passed command:
exec "$@"