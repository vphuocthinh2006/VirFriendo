# 05 — Agent Pipeline

## 5.1 Overview

The agent pipeline (`services/agent_service/llm_agent.py`) handles all chat responses using Groq Llama 3.3 70B with intelligent web search.

**No LangGraph.** No routing nodes. Single LLM generates all replies.

## 5.2 Flow

```
run_agent(messages, agent_id)
    │
    ├── 1. Extract last user text
    │
    ├── 2. Web Search Decision (LLM classifier)
    │       └── Ask Groq: "Does this need web search? YES/NO"
    │       └── If YES → Tavily search → inject results into system prompt
    │
    ├── 3. Generate reply (Groq Llama 3.3 70B)
    │       └── System prompt: personality + memories + search results
    │       └── If empty → retry with nudge prompt
    │       └── If still empty → fallback message
    │
    └── 4. Return {reply, emotion, avatar_action, model_info}
```

## 5.3 ML Pipeline (parallel with agent)

Runs in `chat.py` alongside the agent call:

```
User message
    ├── NLP BERT predict(text) → {emotion_label, dialogue_act_label, confidence}
    ├── Intent Classifier predict(text) → intent label (keyword rules)
    └── Merge:
        ├── High confidence NLP → use NLP emotion for avatar
        ├── Low confidence → use heuristic from agent reply
        ├── Gray zone → LLM arbitrator (Groq 8B) decides
        └── Final: avatar_action (excited_wave / comfort_sit / shocked_face / idle_typing)
```

## 5.4 Web Search Decision

The LLM classifier decides if web search is needed based on:
- **YES**: fresh info, dates, stats, unknown topics, comparisons needing data
- **NO**: greetings, opinions, well-known lore, short messages

## 5.5 LLM Provider Selection

`services/agent_service/llm/client.py`:

| `LLM_PROVIDER` | Primary | Fallback |
|----------------|---------|----------|
| `groq` (current) | Groq Llama 3.3 70B | Claude → OpenAI |
| `claude` | Claude 3.5 Sonnet | Groq → OpenAI |
| `openai` | GPT-4o | Claude → Groq |
| `auto` | Claude → Groq → OpenAI | — |

## 5.6 Memory System

- `extract_user_memories`: extracts facts/preferences from conversation → stores in `user_memories` table
- Memories injected into system prompt on subsequent turns
- Quickstart personality: Redis-backed summary of user communication style

## 5.7 Vision Pipeline (image upload)

Multi-model consensus:
1. **ViT Gallery** (local): cosine match against 45 trained characters
2. **GPT-4o + Gemini** (parallel): both describe the image
3. **LLM Judge** (Groq): merges best answer from both vision models
4. **Tavily**: web search to enrich with facts about identified character

Cross-validation:
- ViT high confidence (>0.55) + good margin → trust ViT name
- ViT medium → need Vision API confirmation
- ViT low (<0.35) → ignore, rely on Gemini/GPT-4o
- Top2 within 0.05 of top1 → flag ambiguity

## 5.8 Prediction Logging

`services/ml/prediction_logger.py` buffers predictions → flushes to S3 every 60s or 50 records:
- Path: `s3://virfriendo-media-ap-southeast-1/ml-predictions/YYYY/MM/DD/*.jsonl`
- Contains: emotion, dialogue_act, confidence, margin, arbitrator decisions
