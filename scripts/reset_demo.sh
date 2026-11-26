#!/usr/bin/env bash
# Fresh demo database: moves db.sqlite3 to a timestamped backup in the parent folder,
# then runs migrate and seed_data. Run from anywhere: bash scripts/reset_demo.sh
# Needs DEBUG=True (in .env), because seed_data refuses to run otherwise.
set -o errexit -o nounset

cd "$(dirname "$0")/.."
PY=python
[ -x .venv/bin/python ] && PY=.venv/bin/python

if [ -f db.sqlite3 ]; then
    backup="../medifind_db_backup_$(date +%Y%m%d_%H%M%S).sqlite3"
    mv db.sqlite3 "$backup"
    echo "==> Old database moved to $backup"
fi

echo "==> Creating tables (migrate)..."
"$PY" manage.py migrate --no-input
echo "==> Adding demo data (seed_data)..."
"$PY" manage.py seed_data
echo "==> Done. Start the app with: $PY manage.py runserver"
