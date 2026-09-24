#!/usr/bin/env bash
# Render.com build script — exit on any error
set -o errexit

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Collecting static files..."
python manage.py collectstatic --no-input

echo "==> Build complete!"
