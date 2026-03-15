# services/agent_service/api/intent_classifier.py
import os
from pathlib import Path
from typing import Literal, cast

from loguru import logger

IntentType = Literal[
    "greeting_chitchat",
    "out_of_domain",
    "comic_knowledge",
    "psychology_venting",
    "psychology_advice_seeking",
    "crisis_alert",
]

VALID_INTENTS: set[str] = {
    "greeting_chitchat",
    "out_of_domain",
    "comic_knowledge",
    "psychology_venting",
    "psychology_advice_seeking",
    "crisis_alert",
}
DEFAULT_INTENT: IntentType = "greeting_chitchat"

SYSTEM_PROMPT = (
    "You are an intent classifier for a mental wellness anime companion chatbot. "
    "Given a user message, output exactly one intent label and nothing else.\n"
    "Valid labels: greeting_chitchat, out_of_domain, comic_knowledge, "
    "psychology_venting, psychology_advice_seeking, crisis_alert"
)

# Prompt cho Groq reason: phân tích intent (dùng trong hybrid)
GROQ_INTENT_SYSTEM = """Bạn là bộ phân loại ý định (intent) cho chatbot bạn ảo anime.
Nhiệm vụ: đọc tin nhắn người dùng và chọn ĐÚNG MỘT nhãn dưới đây, trả lời CHỈ bằng nhãn đó, không thêm gì.

Nhãn:
- greeting_chitchat: chào hỏi, small talk, trò chuyện xã giao
- out_of_domain: hỏi code, tài chính, thời tiết, tin tức... ngoài manga/anime và tâm lý nhẹ
- comic_knowledge: hỏi về manga, anime, nhân vật, chapter, tình tiết
- psychology_venting: đang xả/giãi bày (mệt, buồn, tức, cô đơn, stress...)
- psychology_advice_seeking: xin lời khuyên, làm sao để..., cách nào...
- crisis_alert: có ý tự tử, không muốn sống, nguy hiểm tính mạng

Trả lời chỉ một từ duy nhất là nhãn (ví dụ: greeting_chitchat hoặc crisis_alert)."""


def _keyword_fallback(text: str) -> IntentType:
    text_lower = text.lower().strip()
    crisis_keywords = ["chết", "tự tử", "không muốn sống", "die", "suicide", "kill myself", "end it all"]
    if any(kw in text_lower for kw in crisis_keywords):
        return "crisis_alert"
    ood_keywords = ["code", "html", "python", "bitcoin", "thời tiết", "chứng khoán", "toán"]
    if any(kw in text_lower for kw in ood_keywords):
        return "out_of_domain"
    comic_keywords = ["one piece", "manga", "anime", "naruto", "dragon ball", "chapter", "tập", "nhân vật"]
    if any(kw in text_lower for kw in comic_keywords):
        return "comic_knowledge"
    advice_keywords = ["làm sao", "lời khuyên", "cách nào", "giúp mình", "mẹo", "tips", "how to"]
    if any(kw in text_lower for kw in advice_keywords):
        return "psychology_advice_seeking"
    venting_keywords = ["mệt mỏi", "buồn", "chán", "áp lực", "sếp", "cô đơn", "tức", "cay", "chửi"]
    if any(kw in text_lower for kw in venting_keywords):
        return "psychology_venting"
    return "greeting_chitchat"


def _build_prompt(message: str) -> str:
    return (
        "<|begin_of_text|>"
        "<|start_header_id|>system<|end_header_id|>\n"
        f"{SYSTEM_PROMPT}<|eot_id|>"
        "<|start_header_id|>user<|end_header_id|>\n"
        f"{message}<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n"
    )


def _parse_output(generated: str) -> IntentType:
    normalized = generated.strip().lower()
    for label in VALID_INTENTS:
        if label in normalized:
            return cast(IntentType, label)
    for line in normalized.splitlines():
        candidate = line.strip(" .:-\t\n\r\"")
        if candidate in VALID_INTENTS:
            return cast(IntentType, candidate)
    return DEFAULT_INTENT


class IntentClassifier:
    """
    Phân loại Intent: keyword fallback hoặc load model (Llama + PEFT) khi INTENT_MODEL_PATH được set.
    """
    def __init__(self, model_path: str | None = None):
        self.model_path: str | None = (model_path or os.environ.get("INTENT_MODEL_PATH", "").strip() or None)
        self._enable_runtime = os.environ.get("ENABLE_INTENT_MODEL_RUNTIME", "").strip().lower() in ("1", "true", "yes")
        self._tokenizer = None
        self._model = None
        self._load_failed = False
        self._load_model()

    def _load_model(self) -> None:
        if not self.model_path or not self._enable_runtime:
            logger.info("IntentClassifier: Mock mode (set INTENT_MODEL_PATH and ENABLE_INTENT_MODEL_RUNTIME=true to use model)")
            return
        path = Path(self.model_path)
        if not path.exists():
            logger.warning("IntentClassifier: path does not exist: {}", self.model_path)
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            from peft import PeftConfig, PeftModel
        except ImportError as e:
            logger.warning("IntentClassifier: missing deps (torch/transformers/peft): {}", e)
            return
        try:
            adapter_config = path / "adapter_config.json"
            if adapter_config.exists():
                self._load_peft(path, torch, AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, PeftModel, PeftConfig)
            else:
                logger.warning("IntentClassifier: only PEFT adapter supported (adapter_config.json not found)")
        except Exception as e:
            logger.error("IntentClassifier: load failed: {}", e)
            self._load_failed = True

    def _load_peft(self, path: Path, torch, AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, PeftModel, PeftConfig) -> None:
        peft_config = PeftConfig.from_pretrained(str(path))
        base_id = os.environ.get("INTENT_BASE_MODEL", "").strip() or peft_config.base_model_name_or_path
        self._tokenizer = AutoTokenizer.from_pretrained(str(path))
        if getattr(self._tokenizer, "pad_token_id", None) is None and getattr(self._tokenizer, "eos_token_id", None) is not None:
            self._tokenizer.pad_token_id = self._tokenizer.eos_token_id
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
            )
            base_model = AutoModelForCausalLM.from_pretrained(
                base_id,
                quantization_config=bnb_config,
                device_map="auto",
                torch_dtype=torch.float16,
            )
        else:
            base_model = AutoModelForCausalLM.from_pretrained(
                base_id,
                device_map={"": "cpu"},
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True,
            )
        self._model = PeftModel.from_pretrained(base_model, str(path))
        self._model.eval()
        self._device = device
        logger.info("IntentClassifier: loaded PEFT model from {}", path)

    def predict(self, text: str) -> IntentType:
        """Intent từ model (Llama) hoặc keyword. Sync, dùng trong hybrid cùng Groq."""
        if self._load_failed or self._model is None or self._tokenizer is None:
            return _keyword_fallback(text)
        try:
            import torch
            prompt = _build_prompt(text)
            inputs = self._tokenizer(prompt, return_tensors="pt").to(self._device)
            with torch.inference_mode():
                output_ids = self._model.generate(
                    **inputs,
                    max_new_tokens=20,
                    do_sample=False,
                    pad_token_id=getattr(self._tokenizer, "eos_token_id", None),
                )
            new_ids = output_ids[0][inputs["input_ids"].shape[-1]:]
            generated = self._tokenizer.decode(new_ids, skip_special_tokens=True)
            parsed = _parse_output(generated)
            if parsed == DEFAULT_INTENT:
                return _keyword_fallback(text)
            return parsed
        except Exception as e:
            logger.warning("IntentClassifier: inference failed, using keyword fallback: {}", e)
            return _keyword_fallback(text)

    async def _predict_via_groq(self, text: str):
        """Intent từ Groq (reasoning). Trả về None nếu không gọi được hoặc parse lỗi."""
        use_hybrid = os.environ.get("ENABLE_INTENT_GROQ_HYBRID", "true").strip().lower() in ("1", "true", "yes")
        if not use_hybrid:
            return None
        try:
            from services.agent_service.llm.client import generate
            raw = await generate(GROQ_INTENT_SYSTEM, text)
            if not raw:
                return None
            return _parse_output(raw)
        except Exception as e:
            logger.debug("Intent Groq failed: {}", e)
            return None

    async def predict_hybrid_async(self, text: str) -> IntentType:
        """
        Hybrid: so sánh intent từ model/keyword với intent từ Groq.
        - Nếu một bên là crisis_alert → luôn chọn crisis_alert (an toàn).
        - Nếu hai bên trùng → dùng kết quả đó.
        - Nếu khác → ưu tiên Groq (reasoning).
        """
        intent_model = self.predict(text)  # Llama hoặc keyword
        intent_groq = await self._predict_via_groq(text)
        if intent_groq is None:
            return intent_model
        if intent_model == "crisis_alert" or intent_groq == "crisis_alert":
            return "crisis_alert"
        if intent_model == intent_groq:
            return intent_model
        logger.debug("Intent hybrid: model={} groq={} -> chọn Groq", intent_model, intent_groq)
        return intent_groq


intent_classifier = IntentClassifier()
