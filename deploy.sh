#!/bin/bash
# deploy.sh — pull update + import leads baru
# Usage: bash deploy.sh

set -e

cd /root/wa-bot-klinik

echo "Pulling latest..."
git pull

echo "Importing leads..."
cd backend
source .venv/bin/activate
python -m app.cli.import_leads --csv ../data/leads_template.csv

echo "Restarting backend..."
systemctl restart wa-bot-backend

echo "Done. Bot updated and leads imported."
