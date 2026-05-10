"""Tests for ML confidence gate (services/ml/confidence_gate.py)."""
import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only-32chars!!")

from services.ml.confidence_gate import (
    nlp_emotion_to_avatar_tone,
    emotion_to_avatar_action,
    merge_emotion_for_avatar,
    gate_dialogue_act,
    needs_emotion_llm_arbitrator,
)
from services.ml.nlp_inference import NLPPrediction


def _make_pred(
    emotion="happiness",
    act="statement",
    e_prob=0.8,
    e_margin=0.3,
    a_prob=0.7,
    a_margin=0.2,
) -> NLPPrediction:
    return NLPPrediction(
        emotion_label=emotion,
        dialogue_act_label=act,
        emotion_logits_idx=0,
        act_logits_idx=0,
        emotion_prob_top1=e_prob,
        emotion_prob_top2=e_prob - e_margin,
        emotion_margin=e_margin,
        act_prob_top1=a_prob,
        act_prob_top2=a_prob - a_margin,
        act_margin=a_margin,
    )


class TestNlpEmotionToAvatarTone:
    def test_happiness(self):
        assert nlp_emotion_to_avatar_tone("happiness") == "happy"

    def test_sadness(self):
        assert nlp_emotion_to_avatar_tone("sadness") == "sad"

    def test_anger(self):
        assert nlp_emotion_to_avatar_tone("anger") == "sad"

    def test_surprise(self):
        assert nlp_emotion_to_avatar_tone("surprise") == "surprised"

    def test_neutral(self):
        assert nlp_emotion_to_avatar_tone("neutral") == "neutral"
        assert nlp_emotion_to_avatar_tone("no emotion") == "neutral"

    def test_unknown(self):
        assert nlp_emotion_to_avatar_tone("xyz") == "neutral"


class TestEmotionToAvatarAction:
    def test_all(self):
        assert emotion_to_avatar_action("happy") == "excited_wave"
        assert emotion_to_avatar_action("sad") == "comfort_sit"
        assert emotion_to_avatar_action("surprised") == "shocked_face"
        assert emotion_to_avatar_action("crisis") == "serious_alert"
        assert emotion_to_avatar_action("neutral") == "idle_typing"


class TestMergeEmotionForAvatar:
    def test_no_nlp(self):
        emotion, action, meta = merge_emotion_for_avatar(None, "happy")
        assert emotion == "happy"
        assert action == "excited_wave"
        assert meta["final_source"] == "heuristic_only"

    def test_high_confidence_nlp(self):
        pred = _make_pred(emotion="happiness", e_prob=0.85, e_margin=0.4)
        emotion, action, meta = merge_emotion_for_avatar(pred, "neutral")
        assert emotion == "happy"
        assert meta["nlp_used"] is True
        assert meta["final_source"] == "nlp_high"

    def test_low_confidence_nlp_uses_heuristic(self):
        pred = _make_pred(emotion="happiness", e_prob=0.2, e_margin=0.05)
        emotion, action, meta = merge_emotion_for_avatar(pred, "sad")
        assert emotion == "sad"
        assert meta["final_source"] == "heuristic_low_nlp_conf"

    def test_gray_zone_agrees(self):
        pred = _make_pred(emotion="happiness", e_prob=0.5, e_margin=0.1)
        emotion, action, meta = merge_emotion_for_avatar(pred, "happy")
        assert emotion == "happy"
        assert meta.get("nlp_gray_zone") is True


class TestGateDialogueAct:
    def test_high_confidence(self):
        pred = _make_pred(act="question", a_prob=0.8, a_margin=0.3)
        assert gate_dialogue_act(pred) == "question"

    def test_low_confidence(self):
        pred = _make_pred(act="question", a_prob=0.3, a_margin=0.02)
        assert gate_dialogue_act(pred) is None


class TestNeedsArbitrator:
    def test_no_nlp(self):
        assert needs_emotion_llm_arbitrator(None, {}) is False

    def test_high_conf_no_arbitrator(self):
        pred = _make_pred(e_prob=0.9, e_margin=0.5)
        meta = {"final_source": "nlp_high"}
        assert needs_emotion_llm_arbitrator(pred, meta) is False

    def test_gray_zone_triggers(self):
        os.environ["ENABLE_LLM_DOUBLE_CHECK"] = "true"
        pred = _make_pred(e_prob=0.5, e_margin=0.1)
        meta = {"nlp_gray_zone": True, "final_source": "heuristic_overrides_gray_conflict"}
        assert needs_emotion_llm_arbitrator(pred, meta) is True
        os.environ.pop("ENABLE_LLM_DOUBLE_CHECK", None)
