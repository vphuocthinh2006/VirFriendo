from __future__ import annotations

from pathlib import Path
from typing import cast

import torch
from peft import PeftConfig, PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from config import settings
from graph.state import AgentState, IntentLabel


MODEL_DIR = Path(settings.INTENT_MODEL_DIR)

VALID_INTENTS = {
    "greeting_chitchat",
    "out_of_domain",
    "comic_knowledge",
    "psychology_venting",
    "psychology_advice_seeking",
    "crisis_alert",
}
DEFAULT_INTENT: IntentLabel = "greeting_chitchat"

SYSTEM_PROMPT = (
    "You are an intent classifier for a mental wellness anime companion chatbot. "
    "Given a user message, output exactly one intent label and nothing else.\n"
    "Valid labels: greeting_chitchat, out_of_domain, comic_knowledge, "
    "psychology_venting, psychology_advice_seeking, crisis_alert"
)

_tokenizer: AutoTokenizer | None = None
_model: PeftModel | None = None
_device = "cuda" if torch.cuda.is_available() else "cpu"
_load_failed_once = False


def _keyword_intent_fallback(text: str) -> IntentLabel:
    normalized = text.lower().strip()

    crisis_keywords = [
        "tự tử",
        "muốn chết",
        "kết thúc cuộc đời",
        "không muốn sống",
        "suicide",
        "kill myself",
        "end my life",
    ]
    if any(keyword in normalized for keyword in crisis_keywords):
        return "crisis_alert"

    comic_keywords = [
        "anime",
        "manga",
        "one piece",
        "naruto",
        "gojo",
        "luffy",
        "chap",
        "arc",
    ]
    if any(keyword in normalized for keyword in comic_keywords):
        return "comic_knowledge"

    advice_keywords = [
        "làm sao",
        "nên làm gì",
        "advice",
        "tips",
        "how do i",
        "help me",
        "giúp mình",
    ]
    if any(keyword in normalized for keyword in advice_keywords):
        return "psychology_advice_seeking"

    venting_keywords = [
        "mệt",
        "buồn",
        "chán",
        "stress",
        "tức",
        "cay",
        "thất vọng",
        "cô đơn",
        "khó chịu",
    ]
    if any(keyword in normalized for keyword in venting_keywords):
        return "psychology_venting"

    out_of_domain_keywords = [
        "python",
        "javascript",
        "code",
        "sql",
        "bitcoin",
        "chứng khoán",
        "thời tiết",
        "tin tức",
    ]
    if any(keyword in normalized for keyword in out_of_domain_keywords):
        return "out_of_domain"

    return "greeting_chitchat"


def _load_intent_model() -> None:
    global _tokenizer, _model, _load_failed_once
    if _tokenizer is not None and _model is not None:
        return
    if not settings.ENABLE_INTENT_MODEL_RUNTIME:
        _load_failed_once = True
        return
    if _load_failed_once:
        return

    try:
        peft_config = PeftConfig.from_pretrained(MODEL_DIR)
        base_model_id = settings.INTENT_BASE_MODEL or peft_config.base_model_name_or_path

        _tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
        if _tokenizer.pad_token_id is None and _tokenizer.eos_token_id is not None:
            _tokenizer.pad_token = _tokenizer.eos_token

        if _device == "cuda":
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
            )
            base_model = AutoModelForCausalLM.from_pretrained(
                base_model_id,
                quantization_config=bnb_config,
                device_map="auto",
                torch_dtype=torch.float16,
            )
        else:
            base_model = AutoModelForCausalLM.from_pretrained(
                base_model_id,
                device_map={"": "cpu"},
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True,
            )

        _model = PeftModel.from_pretrained(base_model, MODEL_DIR)
        _model.eval()
    except Exception:
        _load_failed_once = True
        _tokenizer = None
        _model = None


def _build_prompt(message: str) -> str:
    """Tạo prompt theo Llama 3 Instruct format."""
    return (
        "<|begin_of_text|>"
        "<|start_header_id|>system<|end_header_id|>\n"
        f"{SYSTEM_PROMPT}<|eot_id|>"
        "<|start_header_id|>user<|end_header_id|>\n"
        f"{message}<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n"
    )


def _parse_output(generated: str) -> IntentLabel:
    """Lấy intent label từ text được generate."""
    normalized = generated.strip().lower()

    for label in VALID_INTENTS:
        if label in normalized:
            return cast(IntentLabel, label)

    for line in normalized.splitlines():
        candidate = line.strip(" .:-\t\n\r\"")
        if candidate in VALID_INTENTS:
            return cast(IntentLabel, candidate)

    return DEFAULT_INTENT


@torch.inference_mode()
def predict_intent(text: str) -> IntentLabel:
    _load_intent_model()
    if _tokenizer is None or _model is None:
        if settings.ENABLE_INTENT_KEYWORD_FALLBACK:
            return _keyword_intent_fallback(text)
        return DEFAULT_INTENT

    prompt = _build_prompt(text)
    inputs = _tokenizer(prompt, return_tensors="pt").to(_device)

    output_ids = _model.generate(
        **inputs,
        max_new_tokens=20,
        do_sample=False,
        temperature=1.0,
        pad_token_id=_tokenizer.eos_token_id,
    )
    # Chỉ lấy phần được generate (bỏ prompt)
    new_ids = output_ids[0][inputs["input_ids"].shape[-1]:]
    generated = _tokenizer.decode(new_ids, skip_special_tokens=True)

    parsed = _parse_output(generated)
    if parsed == DEFAULT_INTENT and settings.ENABLE_INTENT_KEYWORD_FALLBACK:
        return _keyword_intent_fallback(text)
    return parsed


def intent_node(state: AgentState) -> AgentState:
    message = state.get("message", "").strip()
    if not message:
        return {"intent": DEFAULT_INTENT}

    intent = predict_intent(message)
    return {"intent": intent}