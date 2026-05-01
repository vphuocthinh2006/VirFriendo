# 05 — Pipeline agent (LangGraph)

## 5.1 Vai trò

`services/agent_service` triển khai **phân loại intent** và **StateGraph** LangGraph trong `graph/workflow.py`.

## 5.2 Luồng trong `workflow.py`

1. `START` → **`classifier`** — intent hybrid (model + keyword + LLM reason).
2. → **`emotion`** — phát hiện cảm xúc.
3. → **`route_intent`** — chọn node:

| Intent | Node |
|--------|------|
| `greeting_chitchat` | `chit_chat` |
| `out_of_domain` | `guardrail` |
| `entertainment_knowledge` | `entertainment_expert` |
| `psychology_venting` | `comfort` |
| `psychology_advice_seeking` | `advice` |
| `crisis_alert` / `emotion == crisis` | `crisis` |

4. Mỗi node → `END`. Phản hồi trả về **core** → client.

## 5.3 RAG / retrieval

- `entertainment_expert` node dùng agentic retriever: Wiki → Tavily → community search.
- Vector store: ChromaDB khi `CHROMA_SERVER_URL` được set.

## 5.4 LLM providers

`services/agent_service/llm/client.py` — priority theo `LLM_PROVIDER`:

| `LLM_PROVIDER` | Primary | Fallback |
|----------------|---------|---------|
| `claude` | Claude 3.5 Sonnet | Groq → OpenAI |
| `groq` | Groq Llama 3.3 70B | Claude → OpenAI |
| `openai` | GPT-4o | Claude → Groq |
| `auto` | Claude → Groq → OpenAI | — |

## 5.5 Memory

- `extract_user_memories` trích facts từ hội thoại → lưu `UserMemory` table.
- Memories được inject vào system prompt ở các lượt sau.

## 5.6 Quickstart personality

- `append_user_line_and_maybe_summarize` tích lũy style người dùng → summary inject vào context.
