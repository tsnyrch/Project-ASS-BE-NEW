#!/bin/bash

# Set jumbo packets on network interface
# This script sets the MTU to 9000 to support jumbo frames
# for high-bandwidth camera operations

set -e

# Check if jumbo MTU is requested
if [ "${SET_JUMBO_MTU:-false}" = "true" ]; then
    # Attempt to find the default interface
    INTERFACE=$(ip -o -4 route show to default | awk '{print $5}')
    
    if [ -n "$INTERFACE" ]; then
        echo "Setting MTU to 9000 on interface $INTERFACE for jumbo packets..."
        # Try to set MTU, but don't fail if it doesn't work
        ip link set dev "$INTERFACE" mtu 9000 || echo "Failed to set MTU on $INTERFACE (requires root privileges)"
        
        # Verify the MTU setting
        CURRENT_MTU=$(ip link show dev "$INTERFACE" | grep -oP 'mtu\s+\K\d+')
        echo "Interface $INTERFACE now has MTU: $CURRENT_MTU"
    else
        echo "Warning: Could not determine default interface to set MTU."
    fi
else
    echo "Skipping jumbo MTU configuration (SET_JUMBO_MTU not set to true)"
fi

# Execute the command passed to the script
if [ $# -gt 0 ]; then
    echo "Executing command: $@"
    exec "$@"
fi