"""Upload model files to S3. Run: python upload_models_to_s3.py"""
import os
import boto3
from pathlib import Path

# Uses default AWS credentials (env vars, ~/.aws/credentials, or IAM role)
BUCKET = "virfriendo-media-ap-southeast-1"
REGION = "ap-southeast-1"
LOCAL_DIR = Path("data/models")
S3_PREFIX = "models/"

FILES = [
    "intent_emotion_model.pth",
    "id_to_label.txt",
    "best_vit_model.pth",
    "gallery_embeddings.npy",
    "class_names.pkl",
    "class_centroids.npy",
]

def main():
    s3 = boto3.client("s3", region_name=REGION)
    
    for fname in FILES:
        local_path = LOCAL_DIR / fname
        if not local_path.exists():
            print(f"SKIP (not found): {local_path}")
            continue
        
        s3_key = S3_PREFIX + fname
        size_mb = local_path.stat().st_size / (1024 * 1024)
        print(f"Uploading {fname} ({size_mb:.1f} MB) → s3://{BUCKET}/{s3_key}")
        
        s3.upload_file(
            str(local_path),
            BUCKET,
            s3_key,
            Callback=lambda bytes_transferred: None,
        )
        print(f"  ✓ Done")
    
    print("\nAll uploads complete!")

if __name__ == "__main__":
    main()
