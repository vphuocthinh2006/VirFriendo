"""Download ML model files from S3 at container startup (if not already present)."""
import os
import sys
from pathlib import Path

import boto3
from loguru import logger

S3_BUCKET = os.environ.get("S3_MEDIA_BUCKET", "virfriendo-media-ap-southeast-1")
S3_MODEL_PREFIX = "models/"
LOCAL_MODEL_DIR = Path("/app/data/models")

REQUIRED_FILES = [
    "intent_emotion_model.pth",
    "id_to_label.txt",
    "best_vit_model.pth",
    "gallery_embeddings.npy",
    "class_names.pkl",
    "class_centroids.npy",
]


def download_models():
    LOCAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "ap-southeast-1"))

    for fname in REQUIRED_FILES:
        local_path = LOCAL_MODEL_DIR / fname
        if local_path.exists() and local_path.stat().st_size > 0:
            logger.info("Model already exists: {}", fname)
            continue

        s3_key = S3_MODEL_PREFIX + fname
        logger.info("Downloading s3://{}/{} → {}", S3_BUCKET, s3_key, local_path)
        try:
            s3.download_file(S3_BUCKET, s3_key, str(local_path))
            size_mb = local_path.stat().st_size / (1024 * 1024)
            logger.info("Downloaded {} ({:.1f} MB)", fname, size_mb)
        except Exception as e:
            logger.error("Failed to download {}: {}", fname, e)
            # Don't crash — ML features will just be disabled
            continue

    logger.info("Model download complete")


if __name__ == "__main__":
    download_models()
