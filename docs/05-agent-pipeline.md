# 05 — Pipeline agent (LangGraph)

## 5.1 Vai trò

`services/agent_service` triển khai **phân loại intent** (`intent_classifier`) và **StateGraph** LangGraph trong `graph/workflow.py`: các node **`chit_chat`**, **`guardrail`**, **`entertainment_expert`**, **`comfort`**, **`advice`**, **`crisis`**.

## 5.2 Luồng trong `workflow.py`

1. `START` → **`classifier`** (`classification_node`) — intent hybrid.
2. → **`emotion`** (`emotion_node`).
3. → **`route_intent`** — chọn node theo `intent` (và ưu tiên crisis nếu `emotion == crisis`):

| Intent (classifier) | Node |
|---------------------|------|
| `greeting_chitchat` | `chit_chat` |
| `out_of_domain` | `guardrail` |
| `entertainment_knowledge` | `entertainment_expert` |
| `psychology_venting` | `comfort` |
| `psychology_advice_seeking` | `advice` |
| `crisis_alert` | `crisis` |

4. Mỗi node → `END`. Phản hồi trả về **core** → client. Việc **chia khối hiển thị** là trách nhiệm **frontend** (`splitIntoSemanticBlocks`), không phải output “chunk” cố định từ graph.

## 5.3 RAG / retrieval

- Có thể dùng retrieval trong các node / module LLM (xem `services/agent_service/llm/`, Chroma khi cấu hình).

## 5.4 Cấu hình LLM

- `services/agent_service/llm/client.py`: ưu tiên **OpenAI** (`OPENAI_API_KEY`, mặc định model `gpt-4o` nếu không set `OPENAI_MODEL`); fallback **Groq** (`GROQ_API_KEY`, `LLM_PROVIDER=groq`).

## 5.5 Tài liệu sâu hơn

- `workflow.py`, `state.py`, `agents.py` khi chỉnh hành vi từng node.
