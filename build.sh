#!/usr/bin/env bash
# Render build step: install dependencies, collect static files, prepare the database.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py seed_demo
