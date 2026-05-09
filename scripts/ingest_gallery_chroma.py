#!/usr/bin/env python3
"""
One-shot ingest: gallery_embeddings.npy (dict class->matrix) + class_names.pkl -> Chroma.
Uses precomputed ViT vectors (no embedding function on server).

Usage:
  export CHROMA_SERVER_URL=http://localhost:8003
  python scripts/ingest_gallery_chroma.py \\
    --embeddings path/to/gallery_embeddings.npy \\
    --class-names path/to/class_names.pkl \\
    --collection character_gallery_vit
"""

from __future__ import annotations

import argparse
import hashlib
import pickle
from pathlib import Path

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--embeddings", type=Path, required=True)
    ap.add_argument("--class-names", type=Path, required=True)
    ap.add_argument("--collection", type=str, default="character_gallery_vit")
    ap.add_argument("--batch", type=int, default=256)
    args = ap.parse_args()

    import chromadb
    from chromadb.config import Settings

    import os

    raw = (os.environ.get("CHROMA_SERVER_URL") or "http://localhost:8000").strip()
    if not raw:
        raise SystemExit("Set CHROMA_SERVER_URL")
    from urllib.parse import urlparse

    u = urlparse(raw)
    host = u.hostname or "localhost"
    port = u.port or 8000
    client = chromadb.HttpClient(host=host, port=port, settings=Settings(anonymized_telemetry=False))

    with open(args.class_names, "rb") as f:
        class_order = pickle.load(f)
    raw_np = np.load(args.embeddings, allow_pickle=True)
    blob = raw_np.item() if hasattr(raw_np, "item") else raw_np
    if not isinstance(blob, dict):
        raise SystemExit("embeddings file must be a pickled dict class_name -> ndarray")

    ids: list[str] = []
    embeddings: list[list[float]] = []
    metadatas: list[dict[str, str]] = []
    documents: list[str] = []

    for cls in class_order:
        if cls not in blob:
            continue
        mat = np.asarray(blob[cls], dtype=np.float32)
        if mat.ndim != 2:
            continue
        for i in range(len(mat)):
            row = mat[i]
            h = hashlib.sha1(f"{cls}::{i}".encode("utf-8")).hexdigest()
            uid = f"g_{h[:24]}"
            ids.append(uid)
            embeddings.append(row.astype(float).tolist())
            metadatas.append({"character": str(cls), "class": str(cls), "index": str(i)})
            documents.append(str(cls))

    if not ids:
        raise SystemExit("No rows to ingest")

    dim = len(embeddings[0])
    try:
        client.delete_collection(args.collection)
    except Exception:
        pass
    coll = client.create_collection(
        name=args.collection,
        metadata={"hnsw:space": "cosine", "dimension": str(dim)},
    )

    batch = max(1, int(args.batch))
    for start in range(0, len(ids), batch):
        end = min(len(ids), start + batch)
        coll.add(
            ids=ids[start:end],
            embeddings=embeddings[start:end],
            metadatas=metadatas[start:end],
            documents=documents[start:end],
        )
    print(f"Ingested {len(ids)} vectors dim={dim} into {args.collection} @ {host}:{port}")


if __name__ == "__main__":
    main()
