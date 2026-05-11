"""Lazy-loaded multitask NLP inference — intent_emotion_model.pth + bert-base-uncased."""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from loguru import logger
from transformers import AutoTokenizer

from services.core.config import settings
from services.ml.label_maps import parse_id_to_label_txt
from services.ml.metrics import ModelType
from services.ml.metrics.collector import track_inference
from services.ml.nlp_models import build_multitask_bert_from_checkpoint


@dataclass
class NLPPrediction:
    emotion_label: str
    dialogue_act_label: str
    emotion_logits_idx: int
    act_logits_idx: int
    emotion_prob_top1: float
    emotion_prob_top2: float
    emotion_margin: float
    act_prob_top1: float
    act_prob_top2: float
    act_margin: float
    extras: dict[str, Any] = field(default_factory=dict)


class NLPInferenceService:
    """Thread-safe lazy singleton."""

    _instance: NLPInferenceService | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model = None
        self._tokenizer = None
        self._device = torch.device("cpu")
        self._emotion_names: dict[int, str] = {}
        self._act_names: dict[int, str] = {}
        self._act_logits_offset = 1
        self._load_error: str | None = None

    @classmethod
    def instance(cls) -> NLPInferenceService:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def enabled(self) -> bool:
        if not getattr(settings, "ENABLE_NLP_METADATA", False):
            return False
        p = getattr(settings, "NLP_MODEL_PATH", None)
        return bool((p or "").strip())

    def _ensure_loaded(self) -> bool:
        if self._model is not None:
            return True
        with self._lock:
            if self._model is not None:
                return True
            path = (settings.NLP_MODEL_PATH or "").strip()
            label_path = (settings.NLP_LABEL_PATH or "").strip()
            if not path:
                return False
            try:
                if torch.cuda.is_available() and getattr(settings, "ML_DEVICE", "cpu").strip().lower() in (
                    "cuda",
                    "gpu",
                    "auto",
                ):
                    self._device = torch.device("cuda")
                else:
                    self._device = torch.device((settings.ML_DEVICE or "cpu").strip() or "cpu")

                ckpt_path = Path(path)
                try:
                    sd = torch.load(ckpt_path, map_location=self._device, weights_only=False)
                except TypeError:
                    sd = torch.load(ckpt_path, map_location=self._device)
                if isinstance(sd, dict) and any(k.endswith("act_classifier.weight") for k in sd.keys()):
                    state_dict = sd
                else:
                    logger.warning("NLP checkpoint type unexpected {}", type(sd))
                    return False

                model, _cfg = build_multitask_bert_from_checkpoint(
                    state_dict=state_dict,
                    pretrained_name=getattr(settings, "NLP_BERT_NAME", "bert-base-uncased"),
                    device=self._device,
                )
                self._model = model
                tokenizer_name = getattr(settings, "NLP_BERT_NAME", "bert-base-uncased").strip()
                self._tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
                act_off = getattr(settings, "NLP_ACT_LABEL_ID_OFFSET", 1)
                self._act_logits_offset = int(act_off)

                if label_path:
                    ef, af = parse_id_to_label_txt(label_path)
                    self._emotion_names = ef
                    self._act_names = af
                self._load_error = None
                logger.info("NLP multitask model loaded from {}", ckpt_path)
                return True
            except Exception as e:
                self._load_error = str(e)
                logger.exception("Failed to load NLP model: {}", e)
                return False

    @track_inference(model_name="bert-intent-emotion", model_type=ModelType.LOCAL)
    def maybe_predict(self, text: str, max_length: int = 64) -> NLPPrediction | None:
        if not self.enabled():
            return None
        if not self._ensure_loaded():
            return None
        txt = (text or "").strip()
        if not txt:
            return None
        tok = self._tokenizer(
            txt,
            truncation=True,
            max_length=max_length,
            padding="max_length",
            return_tensors="pt",
        ).to(self._device)
        assert self._model is not None
        with torch.inference_mode():
            act_logits, em_logits = self._model(**{k: v for k, v in tok.items() if k in ("input_ids", "attention_mask", "token_type_ids")})
        ae = act_logits.squeeze(0)
        ee = em_logits.squeeze(0)
        probs_e = F.softmax(ee, dim=-1)
        probs_a = F.softmax(ae, dim=-1)
        top2e = torch.topk(probs_e, k=min(2, probs_e.shape[0]))
        top2a = torch.topk(probs_a, k=min(2, probs_a.shape[0]))
        ei = int(top2e.indices[0].item())
        ai = int(top2a.indices[0].item())
        p1e = float(top2e.values[0].item())
        p2e = float(top2e.values[1].item()) if top2e.values.numel() > 1 else 0.0
        p1a = float(top2a.values[0].item())
        p2a = float(top2a.values[1].item()) if top2a.values.numel() > 1 else 0.0

        em_name = self._emotion_names.get(ei, f"emotion_{ei}")
        act_key = ai + self._act_logits_offset
        act_name = self._act_names.get(act_key, self._act_names.get(ai, f"dialogue_act_{ai}"))

        return NLPPrediction(
            emotion_label=em_name,
            dialogue_act_label=act_name,
            emotion_logits_idx=ei,
            act_logits_idx=ai,
            emotion_prob_top1=p1e,
            emotion_prob_top2=p2e,
            emotion_margin=p1e - p2e,
            act_prob_top1=p1a,
            act_prob_top2=p2a,
            act_margin=p1a - p2a,
            extras={"nlp_load_error": self._load_error},
        )


def get_nlp_service() -> NLPInferenceService:
    return NLPInferenceService.instance()
