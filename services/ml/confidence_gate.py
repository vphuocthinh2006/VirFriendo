"""Confidence gating and merge NLP emotion with heuristic avatar emotion."""

from __future__ import annotations

from typing import Any

from services.core.config import settings
from services.ml.nlp_inference import NLPPrediction


def nlp_emotion_to_avatar_tone(nlp_emotion_lower: str) -> str:
    """Map NLP dataset emotion string to Claude avatar coarse emotion."""
    t = (nlp_emotion_lower or "").lower()
    if "neutral" in t or "no emotion" in t:
        return "neutral"
    if "happiness" in t or "happy" in t:
        return "happy"
    if "surprise" in t:
        return "surprised"
    if "crisis" in t:
        return "crisis"
    if "anger" in t or "disgust" in t or "fear" in t or "sadness" in t or "sad" in t:
        return "sad"
    return "neutral"


def emotion_to_avatar_action(emotion: str) -> str:
    mapping = {
        "happy": "excited_wave",
        "sad": "comfort_sit",
        "surprised": "shocked_face",
        "crisis": "serious_alert",
        "neutral": "idle_typing",
    }
    return mapping.get(emotion, "idle_typing")


def _in_gray_band(conf: float) -> bool:
    lo = float(getattr(settings, "NLP_CONFIDENCE_GRAY_LOW", 0.4))
    hi = float(getattr(settings, "NLP_CONFIDENCE_GRAY_HIGH", 0.7))
    return lo <= conf <= hi


def _emotion_high_conf(pred: NLPPrediction) -> bool:
    thr = float(getattr(settings, "NLP_EMOTION_MIN_PROB", 0.55))
    marg = float(getattr(settings, "NLP_EMOTION_MIN_MARGIN", 0.08))
    return pred.emotion_prob_top1 >= thr and pred.emotion_margin >= marg


def _emotion_low_conf(pred: NLPPrediction) -> bool:
    return pred.emotion_prob_top1 < float(getattr(settings, "NLP_EMOTION_LOW_PROB", 0.35))


def gate_dialogue_act(pred: NLPPrediction) -> str | None:
    ta = float(getattr(settings, "NLP_ACT_MIN_PROB", 0.55))
    ma = float(getattr(settings, "NLP_ACT_MIN_MARGIN", 0.06))
    if pred.act_prob_top1 >= ta and pred.act_margin >= ma:
        return pred.dialogue_act_label
    return None


def merge_emotion_for_avatar(
    nlp: NLPPrediction | None,
    heuristic_emotion: str | None,
) -> tuple[str, str, dict[str, Any]]:
    """
    Returns (final_avatar_emotion, avatar_action, debug dict).
    Heuristic_emotion comes from agent reply inference (baseline).
    """
    heur = (heuristic_emotion or "neutral").strip() or "neutral"
    meta: dict[str, Any] = {"fallback_heuristic_emotion": heur, "nlp_used": False}

    if nlp is None:
        meta["final_source"] = "heuristic_only"
        return heur, emotion_to_avatar_action(heur), meta

    ml_tone = nlp_emotion_to_avatar_tone(nlp.emotion_label)
    meta["nlp_emotion_raw"] = nlp.emotion_label
    meta["nlp_emotion_avatar_tone"] = ml_tone
    meta["nlp_emotion_probs"] = {
        "top1": nlp.emotion_prob_top1,
        "margin": nlp.emotion_margin,
    }

    if _emotion_high_conf(nlp):
        meta["nlp_used"] = True
        meta["final_source"] = "nlp_high"
        disagree = ml_tone != heur and heur != "neutral"
        meta["disagreement_with_heuristic"] = disagree
        return ml_tone, emotion_to_avatar_action(ml_tone), meta

    if _emotion_low_conf(nlp):
        meta["final_source"] = "heuristic_low_nlp_conf"
        return heur, emotion_to_avatar_action(heur), meta

    if _in_gray_band(nlp.emotion_prob_top1):
        meta["nlp_gray_zone"] = True
        if ml_tone == heur:
            meta["final_source"] = "nlp_gray_agrees_heuristic"
            return ml_tone, emotion_to_avatar_action(ml_tone), meta
        meta["final_source"] = "heuristic_overrides_gray_conflict"
        return heur, emotion_to_avatar_action(heur), meta

    meta["final_source"] = "heuristic_mid_conf"
    return heur, emotion_to_avatar_action(heur), meta


def needs_emotion_llm_arbitrator(nlp: NLPPrediction | None, merge_meta: dict[str, Any]) -> bool:
    if not getattr(settings, "ENABLE_LLM_DOUBLE_CHECK", False):
        return False
    if nlp is None:
        return False
    if not merge_meta.get("nlp_gray_zone") and not merge_meta.get("disagreement_with_heuristic"):
        return False
    if merge_meta.get("final_source") in ("nlp_high",):
        return False
    return bool(merge_meta.get("nlp_gray_zone") or merge_meta.get("disagreement_with_heuristic"))
