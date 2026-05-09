"""Character gallery cosine search — numpy (fast path) or Chroma."""

from __future__ import annotations

import json
import pickle
import threading
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
from loguru import logger

from services.core.config import settings

_holder: dict[str, object | None] = {"flat": None, "labels": None, "chroma": None}
_lock = threading.Lock()


def _l2_normalize_rows(mat: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(mat, axis=1, keepdims=True).clip(min=1e-8)
    return mat / n


def _load_numpy_gallery_flat() -> tuple[np.ndarray | None, list[str] | None]:
    gp = (getattr(settings, "GALLERY_EMBEDDINGS_NPY_PATH", "") or "").strip()
    cp = (getattr(settings, "GALLERY_CLASS_NAMES_PKL_PATH", "") or "").strip()
    if not gp or not cp:
        return None, None
    gp_path = Path(gp)
    cp_path = Path(cp)
    if not gp_path.is_file():
        logger.warning("Gallery npy missing: {}", gp_path)
        return None, None
    raw = np.load(gp_path, allow_pickle=True)
    blob = raw.item() if hasattr(raw, "item") else raw
    if not isinstance(blob, dict):
        logger.warning("Gallery npy unexpected format {}", type(blob))
        return None, None
    with open(cp_path, "rb") as f:
        class_order = pickle.load(f)
    if not isinstance(class_order, list):
        logger.warning("class_names.pkl unexpected {}", type(class_order))
        return None, None
    rows_list: list[np.ndarray] = []
    labels_flat: list[str] = []
    for nm in class_order:
        if nm not in blob:
            continue
        chunk = np.asarray(blob[nm], dtype=np.float32)
        if chunk.ndim != 2:
            continue
        rows_list.append(chunk)
        labels_flat.extend([str(nm)] * len(chunk))
    if not rows_list:
        logger.warning("No gallery rows flattened")
        return None, None
    mat = np.vstack(rows_list).astype(np.float32, copy=False)
    mat = _l2_normalize_rows(mat)
    return mat, labels_flat


class GalleryMatcher:
    def __init__(self) -> None:
        self.backend = (getattr(settings, "GALLERY_VECTOR_BACKEND", "numpy") or "numpy").strip().lower()

    def _ensure_numpy(self) -> None:
        with _lock:
            if _holder["flat"] is not None:
                return
            m, lbl = _load_numpy_gallery_flat()
            _holder["flat"] = m
            _holder["labels"] = lbl

    def _parse_chroma(self) -> tuple[str, int]:
        raw = ((settings.CHROMA_SERVER_URL or "") or "").strip()
        parsed = urlparse(raw)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8000
        return host, port

    def top_k(self, embedding: np.ndarray, k: int = 8) -> list[dict[str, object]]:
        """embedding: shape (dim,) normalized float32."""
        k = max(1, min(int(k), 50))
        v = embedding.astype(np.float32, copy=False).reshape(-1)

        min_sim = float(getattr(settings, "VIT_MIN_SIMILARITY", 0.35))
        min_margin = float(getattr(settings, "VIT_MIN_MARGIN_SIM", 0.02))

        if self.backend == "chroma" and (settings.CHROMA_SERVER_URL or "").strip():
            try:
                import chromadb

                host, port = self._parse_chroma()
                client = chromadb.HttpClient(host=host, port=port)
                coll = client.get_collection(
                    getattr(settings, "CHROMA_GALLERY_COLLECTION", "character_gallery_vit")
                )
                res = coll.query(
                    query_embeddings=[v.tolist()],
                    n_results=k,
                    include=["distances", "metadatas", "documents"],
                )
                docs: list[dict[str, object]] = []
                ids0 = (res.get("ids") or [[]])[0]
                dist0 = (res.get("distances") or [[]])[0]
                md0 = (res.get("metadatas") or [[]])[0]
                for i, _id in enumerate(ids0):
                    if i >= len(dist0):
                        break
                    dist = float(dist0[i])
                    sim = 1.0 - dist
                    md = md0[i] if i < len(md0) else {}
                    ch = md.get("character") if isinstance(md, dict) else str(_id)
                    docs.append({"character": ch, "similarity": sim, "row_id": str(_id), "tier": "low"})
                if docs:
                    d0 = float(docs[0]["similarity"])
                    d1 = float(docs[1]["similarity"]) if len(docs) > 1 else 0.0
                    tier0 = (
                        "high"
                        if d0 >= min_sim and (d0 - d1) >= min_margin
                        else ("medium" if d0 >= min_sim * 0.85 else "low")
                    )
                    docs[0]["tier"] = tier0
                return docs[:k]
            except Exception as e:
                logger.warning("Chroma gallery query failed {}, falling back numpy", e)

        self._ensure_numpy()
        flat = _holder["flat"]
        labels = _holder["labels"]
        if flat is None or labels is None:
            return []
        sims = flat @ v
        if sims.ndim != 1:
            sims = sims.reshape(-1)
        ix = np.argsort(-sims)[: k + 5]
        out: list[dict[str, object]] = []
        for i in ix[: k + 5]:
            if len(out) >= k:
                break
            ss = float(sims[int(i)])
            out.append({"character": labels[int(i)], "similarity": ss, "row_id": f"row_{int(i)}", "tier": "low"})
        if not out:
            return []
        d0 = float(out[0]["similarity"])
        d1 = float(out[1]["similarity"]) if len(out) > 1 else 0.0
        tier = "high" if d0 >= min_sim and (d0 - d1) >= min_margin else ("medium" if d0 >= min_sim * 0.85 else "low")
        out[0]["tier"] = tier
        return out[:k]


_matcher_singleton: GalleryMatcher | None = None


def gallery_matcher() -> GalleryMatcher:
    global _matcher_singleton
    if _matcher_singleton is None:
        _matcher_singleton = GalleryMatcher()
    return _matcher_singleton


def gallery_hints_blob(hits: list[dict[str, object]]) -> str:
    slim = [{"character": h.get("character"), "similarity": round(float(h["similarity"]), 4), "tier": h.get("tier")} for h in hits[:5]]
    return json.dumps(slim, ensure_ascii=False)
