web: gunicorn app_new:app --bind 0.0.0.0:$PORT --workers 1 --worker-class sync --threads 1 --timeout 120 --log-level debug --access-logfile - --error-logfile -
