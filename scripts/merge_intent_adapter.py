"""
Chạy 1 lần để merge LoRA adapter vào base model.
Output: services/agent_service/models/intent_merged/

Usage:
    python scripts/merge_intent_adapter.py
"""

from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

BASE_MODEL_ID = "unsloth/llama-3-8b-Instruct"
FALLBACK_QUANTIZED_BASE_MODEL_ID = "unsloth/llama-3-8b-Instruct-bnb-4bit"
ADAPTER_DIR = Path("services/agent_service/models/intent")
OUTPUT_DIR = Path("services/agent_service/models/intent_merged")


def main():
    print(f"[1/4] Loading tokenizer from adapter dir...")
    tokenizer = AutoTokenizer.from_pretrained(ADAPTER_DIR)

    print(f"[2/4] Loading base model: {BASE_MODEL_ID}")
    try:
        base_model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_ID,
            device_map={"": "cpu"},
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
        )
    except Exception as error:
        print(f"Full-precision base load failed: {error}")
        print("Retrying with quantized fallback base model...")
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        base_model = AutoModelForCausalLM.from_pretrained(
            FALLBACK_QUANTIZED_BASE_MODEL_ID,
            quantization_config=bnb_config,
            device_map="auto",
            torch_dtype=torch.bfloat16,
        )

    print(f"[3/4] Applying LoRA adapter from: {ADAPTER_DIR}")
    model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
    merged = model.merge_and_unload()

    print(f"[4/4] Saving merged model to: {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(OUTPUT_DIR, safe_serialization=False)
    tokenizer.save_pretrained(OUTPUT_DIR)

    print("Done! Update INTENT_MODEL_PATH in .env to:")
    print("  INTENT_MODEL_PATH=services/agent_service/models/intent_merged")


if __name__ == "__main__":
    main()
