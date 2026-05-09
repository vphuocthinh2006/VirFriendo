#!/bin/bash
set -e

# Download ML models from S3 if ENABLE_NLP_METADATA is set
if [ "${ENABLE_NLP_METADATA}" = "true" ] || [ "${ENABLE_VIT_GALLERY}" = "true" ]; then
  echo "Downloading ML models from S3..."
  python /app/scripts/download_models.py || echo "Model download failed - ML features disabled"
fi

# Start the app
exec uvicorn services.core.main:app --host 0.0.0.0 --port 8000
