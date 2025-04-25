#!/bin/bash

# This script sets up the database and creates an admin user

echo "====================================================="
echo "Setting up the database and creating admin user..."
echo "====================================================="

# Check if poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "Error: Poetry is not installed. Please install it first."
    exit 1
fi

echo "1. Running database migrations..."
poetry run alembic upgrade head

if [ $? -ne 0 ]; then
    echo "Error: Failed to run migrations. Make sure your database is running."
    exit 1
fi

echo "2. Creating admin user..."
poetry run python create_admin.py

if [ $? -ne 0 ]; then
    echo "Error: Failed to create admin user."
    exit 1
fi

echo "====================================================="
echo "Setup complete! You can now run the application with:"
echo "make startp  # For local development with Poetry"
echo "make startd  # For Docker development with tracing"
echo "====================================================="
echo "Admin credentials:"
echo "Username: admin"
echo "Password: admin123"
echo "====================================================="