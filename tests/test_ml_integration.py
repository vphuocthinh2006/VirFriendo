"""
ML smoke / integration tests.

- **Luôn chạy:** parse `id_to_label`, confidence merge (không cần checkpoint).
- **Có checkpoint trong repo hoặc `NLP_MODEL_PATH`:** suy luận BERT (có thể tải `bert-base-uncased` lần đầu).
- **Gallery:** có `gallery_embeddings.npy` + `class_names.pkl` thì test cosine top-k.
- **ViT:** đặt `RUN_VIT_SMOKE=1` và có `best_vit_model.pth` trong repo/path — có thể rất chậm lần đầu.

Không chỉnh `plan` hay artifact; chỉ bỏ qua (skip) nếu file không có.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
NLP_ARTIFACT_DIR = REPO_ROOT / "NLP_main-20260509T103239Z-3-001" / "NLP_main"
GALLERY_ARTIFACT_DIR = REPO_ROOT / "ML_model_and_embedding_gallery-20260509T103143Z-3-001" / "ML_model_and_embedding_gallery"


def _nlp_checkpoint_path() -> Path | None:
    env = (os.environ.get("NLP_MODEL_PATH") or "").strip()
    if env:
        p = Path(env)
        return p if p.is_file() else None
    p = NLP_ARTIFACT_DIR / "intent_emotion_model.pth"
    return p if p.is_file() else None


def _nlp_label_path() -> Path | None:
    env = (os.environ.get("NLP_LABEL_PATH") or "").strip()
    if env:
        p = Path(env)
        return p if p.is_file() else None
    p = NLP_ARTIFACT_DIR / "id_to_label.txt"
    return p if p.is_file() else None


def _gallery_paths() -> tuple[Path | None, Path | None]:
    gp = os.environ.get("GALLERY_EMBEDDINGS_NPY_PATH", "").strip()
    cp = os.environ.get("GALLERY_CLASS_NAMES_PKL_PATH", "").strip()
    if gp and cp:
        p1, p2 = Path(gp), Path(cp)
        if p1.is_file() and p2.is_file():
            return p1, p2
    e = GALLERY_ARTIFACT_DIR / "gallery_embeddings.npy"
    c = GALLERY_ARTIFACT_DIR / "class_names.pkl"
    if e.is_file() and c.is_file():
        return e, c
    return None, None


def _vit_checkpoint_path() -> Path | None:
    env = (os.environ.get("VIT_MODEL_PATH") or "").strip()
    if env:
        p = Path(env)
        return p if p.is_file() else None
    p = GALLERY_ARTIFACT_DIR / "best_vit_model.pth"
    return p if p.is_file() else None


@pytest.mark.ml
def test_parse_id_to_label_txt_when_present():
    from services.ml.label_maps import parse_id_to_label_txt

    lbl = _nlp_label_path()
    if lbl is None:
        pytest.skip("id_to_label.txt không có (đặt NLP_LABEL_PATH hoặc thêm thư mục NLP artifact)")
    emo, act = parse_id_to_label_txt(lbl)
    assert 0 in emo or len(emo) >= 3
    assert len(act) >= 1


@pytest.mark.ml
def test_merge_emotion_high_conf_uses_nlp(monkeypatch: pytest.MonkeyPatch):
    from services.core.config import settings
    from services.ml.confidence_gate import merge_emotion_for_avatar
    from services.ml.nlp_inference import NLPPrediction

    monkeypatch.setattr(settings, "NLP_EMOTION_MIN_PROB", 0.05)
    monkeypatch.setattr(settings, "NLP_EMOTION_MIN_MARGIN", 0.0)

    pred = NLPPrediction(
        emotion_label="happiness",
        dialogue_act_label="Question",
        emotion_logits_idx=4,
        act_logits_idx=1,
        emotion_prob_top1=0.95,
        emotion_prob_top2=0.03,
        emotion_margin=0.92,
        act_prob_top1=0.7,
        act_prob_top2=0.15,
        act_margin=0.55,
    )
    emo, action, meta = merge_emotion_for_avatar(pred, "sad")
    assert emo == "happy"
    assert action == "excited_wave"
    assert meta.get("final_source") == "nlp_high"


@pytest.mark.ml
def test_merge_emotion_low_conf_falls_back_heuristic(monkeypatch: pytest.MonkeyPatch):
    from services.core.config import settings
    from services.ml.confidence_gate import merge_emotion_for_avatar
    from services.ml.nlp_inference import NLPPrediction

    monkeypatch.setattr(settings, "NLP_EMOTION_LOW_PROB", 0.5)

    pred = NLPPrediction(
        emotion_label="sadness",
        dialogue_act_label="Inform",
        emotion_logits_idx=5,
        act_logits_idx=0,
        emotion_prob_top1=0.2,
        emotion_prob_top2=0.18,
        emotion_margin=0.02,
        act_prob_top1=0.3,
        act_prob_top2=0.2,
        act_margin=0.1,
    )
    emo, _, meta = merge_emotion_for_avatar(pred, "surprised")
    assert emo == "surprised"
    assert meta.get("final_source") == "heuristic_low_nlp_conf"


@pytest.mark.ml
@pytest.mark.integration
def test_gate_dialogue_act(monkeypatch: pytest.MonkeyPatch):
    from services.core.config import settings
    from services.ml.confidence_gate import gate_dialogue_act
    from services.ml.nlp_inference import NLPPrediction

    monkeypatch.setattr(settings, "NLP_ACT_MIN_PROB", 0.05)
    monkeypatch.setattr(settings, "NLP_ACT_MIN_MARGIN", 0.0)

    pred = NLPPrediction(
        emotion_label="neutral",
        dialogue_act_label="Directive",
        emotion_logits_idx=0,
        act_logits_idx=2,
        emotion_prob_top1=0.9,
        emotion_prob_top2=0.05,
        emotion_margin=0.85,
        act_prob_top1=0.88,
        act_prob_top2=0.05,
        act_margin=0.83,
    )
    assert gate_dialogue_act(pred) == "Directive"


@pytest.mark.ml
@pytest.mark.integration
def test_nlp_multitask_forward_smoke(monkeypatch: pytest.MonkeyPatch):
    """Load checkpoint + tokenizer; một câu tiếng Anh như trong tập huấn luyện."""
    pytest.importorskip("torch")
    pytest.importorskip("transformers")

    ckpt = _nlp_checkpoint_path()
    if ckpt is None:
        pytest.skip("Không tìm thấy intent_emotion_model.pth (NLP_MODEL_PATH hoặc thư mục NLP artifact)")
    lbl = _nlp_label_path()

    from services.core.config import settings
    from services.ml.nlp_inference import NLPInferenceService, get_nlp_service

    NLPInferenceService._instance = None
    monkeypatch.setattr(settings, "ENABLE_NLP_METADATA", True)
    monkeypatch.setattr(settings, "NLP_MODEL_PATH", str(ckpt))
    monkeypatch.setattr(settings, "NLP_LABEL_PATH", str(lbl) if lbl else "")
    monkeypatch.setattr(settings, "ML_DEVICE", "cpu")

    svc = get_nlp_service()
    assert svc.enabled() is True
    pred = svc.maybe_predict("I guess you are right. What shall we do?")
    assert pred is not None
    assert pred.emotion_prob_top1 > 0.0
    assert pred.act_prob_top1 > 0.0


@pytest.mark.ml
@pytest.mark.integration
def test_gallery_numpy_top_k(monkeypatch: pytest.MonkeyPatch):
    """Cosine search trên embedding gallery đã lưu sẵn."""
    pytest.importorskip("numpy")

    gp, cn = _gallery_paths()
    if gp is None:
        pytest.skip("Không có gallery_embeddings.npy + class_names.pkl")

    from services.core.config import settings
    import services.ml.gallery_search as gsearch

    gsearch._holder["flat"] = None
    gsearch._holder["labels"] = None
    gsearch._matcher_singleton = None

    monkeypatch.setattr(settings, "GALLERY_EMBEDDINGS_NPY_PATH", str(gp))
    monkeypatch.setattr(settings, "GALLERY_CLASS_NAMES_PKL_PATH", str(cn))
    monkeypatch.setattr(settings, "GALLERY_VECTOR_BACKEND", "numpy")
    monkeypatch.setattr(settings, "VIT_MIN_SIMILARITY", 0.0)

    import numpy as np

    from services.ml.gallery_search import gallery_matcher

    gm = gallery_matcher()
    gm._ensure_numpy()
    flat = gsearch._holder["flat"]
    assert flat is not None and len(flat.shape) == 2
    dim = flat.shape[1]
    q = flat[0].astype(np.float32).copy()

    hits = gallery_matcher().top_k(q, k=5)
    assert len(hits) >= 1
    assert hits[0]["similarity"] >= 0.99


@pytest.mark.ml
@pytest.mark.integration
@pytest.mark.slow
def test_vit_encode_smoke(monkeypatch: pytest.MonkeyPatch):
    """Chậm; cần timm + torch. Bật: RUN_VIT_SMOKE=1."""
    if os.environ.get("RUN_VIT_SMOKE", "").strip().lower() not in ("1", "true", "yes"):
        pytest.skip("Đặt RUN_VIT_SMOKE=1 để chạy (tải timm + load ViT)")

    pytest.importorskip("torch")
    pytest.importorskip("timm")

    ckpt = _vit_checkpoint_path()
    if ckpt is None:
        pytest.skip("Không tìm thấy best_vit_model.pth")

    from services.core.config import settings
    import services.ml.vit_encoder as vit_enc

    vit_enc._vit_holder["m"] = None

    monkeypatch.setattr(settings, "ENABLE_VIT_GALLERY", True)
    monkeypatch.setattr(settings, "VIT_MODEL_PATH", str(ckpt))
    monkeypatch.setattr(settings, "VIT_TIMM_MODEL", "vit_base_patch16_224")
    monkeypatch.setattr(settings, "VIT_NUM_CLASSES", 45)
    monkeypatch.setattr(settings, "ML_DEVICE", "cpu")

    from PIL import Image
    import numpy as np

    from services.ml.vit_encoder import encode_image_pil_normalized

    arr = np.zeros((448, 448, 3), dtype=np.uint8)
    arr[..., 1] = 120
    img = Image.fromarray(arr, mode="RGB")
    emb = encode_image_pil_normalized(img)
    assert emb is not None
    v = emb.numpy().reshape(-1)
    assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-2
