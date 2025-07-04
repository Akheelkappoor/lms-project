#!/bin/bash

# Activate your virtual environment
source .venv/bin/activate

# Install new package
# pip3 install -r requirements.txt

# Start Gunicorn to run your Django application
gunicorn wsgi:app -b 0.0.0.0:5002