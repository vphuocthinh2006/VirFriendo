# 01 — System Architecture

## 1.1 Overview

Pally is a **monorepo** AI companion chatbot platform:

- **Frontend:** React + Vite + TypeScript + Tailwind — Cloudflare Pages (`virfriendo.win`)
- **Backend:** FastAPI (`services.core`) — ECS Fargate (`api.virfriendo.win`)
- **ML Models:** NLP BERT (emotion/dialogue_act) + ViT (character gallery) — runs in-process
- **LLM:** Groq Llama 3.3 70B (primary) with web search via Tavily

## 1.2 Chat Flow

```
User message
    │
    ├── [parallel] LLM Agent (Groq) → generate reply
    │       ├── Ask Groq: "need web search?" (YES/NO)
    │       ├── If YES → Tavily search → inject into context
    │       └── Generate reply with full context
    │
    ├── [parallel] NLP BERT → emotion + dialogue_act prediction
    │       └── Confidence gate → LLM arbitrator (if ambiguous)
    │
    └── [parallel] Intent Classifier → keyword-based classification
    
    → Merge results → avatar_action + reply + metadata → Response
```

## 1.3 Vision Flow (image upload)

```
Image upload
    ├── [1] ViT Gallery (local) → cosine match 45 characters
    ├── [2] GPT-4o (parallel) → describe image
    ├── [2] Gemini 1.5 Pro (parallel) → describe image
    └── [3] LLM Judge (Groq) → consensus merge
    └── [4] Tavily web search → enrich with facts
```

## 1.4 Components

| Component | Path | Purpose |
|-----------|------|---------|
| Core API | `services/core/main.py` | FastAPI app, all routers |
| Auth | `services/core/api/auth.py` | Register, login, Google OAuth |
| Chat | `services/core/api/chat.py` | Chat, voice, vision, imagine, WS |
| Games | `services/core/api/game.py`, `caro.py` | Chess (Stockfish), Caro |
| LLM Agent | `services/agent_service/llm_agent.py` | Groq orchestrator + web search |
| LLM Client | `services/agent_service/llm/client.py` | Provider selection (Groq/OpenAI/Claude) |
| NLP BERT | `services/ml/nlp_inference.py` | Emotion + dialogue act classification |
| ViT Gallery | `services/ml/vit_encoder.py` + `gallery_search.py` | Character recognition |
| Confidence Gate | `services/ml/confidence_gate.py` | Emotion merge + arbitration |
| Prediction Logger | `services/ml/prediction_logger.py` | Log predictions to S3 |

## 1.5 LLM Providers

| Provider | Purpose | Env var |
|----------|---------|---------|
| **Groq Llama 3.3 70B** | Chat (primary) | `GROQ_API_KEY`, `LLM_PROVIDER=groq` |
| GPT-4o | Vision (primary) | `OPENAI_API_KEY` |
| Gemini 1.5 Pro | Vision (parallel) | `GEMINI_API_KEY` |
| Deepgram Nova-3 | Voice transcription | `DEEPGRAM_API_KEY` |
| Groq Whisper | Voice fallback | `GROQ_API_KEY` |
| Replicate FLUX | Image generation | `REPLICATE_API_TOKEN` |
| Tavily | Web search | `TAVILY_API_KEY` |

## 1.6 ML Models

| Model | File | Purpose |
|-------|------|---------|
| NLP Multitask BERT | `intent_emotion_model.pth` (418MB) | Emotion + dialogue act classification |
| ViT Base Patch16 | `best_vit_model.pth` (329MB) | Character recognition (45 classes) |
| Gallery Embeddings | `gallery_embeddings.npy` (18MB) | Cosine search vectors |
| Intent Classifier | Keyword rules (no model file) | Intent classification for analytics |

## 1.7 Health Check

- `GET /health` → `{"status": "healthy", "project": "VirFriendo", "version": "0.1.0"}`
- OpenAPI: `/docs` when `DEBUG=true` or `APP_ENV != production`
