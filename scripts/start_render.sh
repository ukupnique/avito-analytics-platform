#!/usr/bin/env bash
# Render запускает скрипт из корня репозитория.
set -euo pipefail

export PYTHONPATH=backend

# На бесплатном тарифе миграции выполняются перед запуском единственного экземпляра.
python -m alembic upgrade head

exec python -m gunicorn app.main:app \
  --worker-class uvicorn_worker.UvicornWorker \
  --bind "0.0.0.0:${PORT:-10000}" \
  --workers 1 \
  --access-logfile - \
  --error-logfile -
