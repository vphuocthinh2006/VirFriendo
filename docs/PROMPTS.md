# LLM prompts trong project (inventory)

Tài liệu này liệt kê **mọi chỗ** hệ thống gọi LLM với **system prompt** (hoặc tương đương), và **luồng ngữ cảnh** (conversation + memory).

---

## 1. Luồng tin nhắn vào graph (quan trọng)

### 1.1 REST `POST /chat` và WebSocket `/chat/ws`

File: `services/core/api/chat.py`

1. User message được **lưu DB** trước.
2. `_build_lc_messages(db, conversation_id, user_uuid, fallback_text, session)`:
   - Gọi `get_conversation_context()` (`services/core/context.py`) — lấy tối đa **`MAX_CONTEXT_MESSAGES` = 20** tin (user/assistant) theo thời gian, **đã gồm tin user vừa commit**.
   - Ghép thành `HumanMessage` / `AIMessage`.
   - Thêm **SystemMessage** đầu tiên nếu có:
     - Identity (`tuq27`…)
     - Character persona (entry `character`)
     - Quickstart summary (`get_quickstart_summary`)
     - **UserMemory** (tối đa 20 bản ghi active, bullet `(type) content`)
3. `graph_app.ainvoke({"messages": lc_messages, "agent_id": ...})` — toàn bộ list trên đi vào LangGraph.

**Kết luận:** Trong một **conversation_id**, bot **có** lịch sử gần nhất + memory user (system). Điều này áp dụng cho **chit_chat, comfort, advice, crisis, guardrail** (dùng `generate_with_history`).

### 1.2 Nhánh Entertainment Expert (kiến thức + retrieval)

File: `services/agent_service/graph/agents.py` → `entertainment_expert_node`

- Trước đây pipeline chỉ gọi `generate(system, user_query)` với **một chuỗi retrieval** — **không** đưa toàn bộ history vào user message của bước generate đó.
- **Hiện tại:** `run_entertainment_pipeline(..., conversation_context=...)` nhận thêm **lược đổi thoại** (`Bạn:` / `tuq27:`) từ `state["messages"]` (bỏ `SystemMessage` để tránh lặp memory khổng lồ), ghép vào **human prompt** cùng chủ đề cần trả lời (xem `entertainment_pipeline._compose_user_prompt_for_model`).
- **Retrieval** (`agentic_retrieve`) vẫn chỉ dùng **`user_query`** (có thể là `prev + Follow-up` khi follow-up ngắn).

---

## 2. Gọi LLM theo kiểu

| Hàm | File | Mô tả |
|-----|------|--------|
| `generate(system, user)` | `services/agent_service/llm/client.py` | Một system + một user message. |
| `generate_with_history(system, messages)` | Cùng file | System + `messages` (slice 20 tin cuối). |

---

## 3. LangGraph agents & system prompt (character)

File: `services/agent_service/graph/agents.py`

| Constant / node | Mục đích |
|-----------------|----------|
| `BASE_PERSONA` | Giọng tuq27, tiếng Việt, không AI-slop, không bullet list. |
| `CHIT_CHAT_SYSTEM` | Tán gẫu, chào hỏi. |
| `GUARDRAIL_SYSTEM` | Out-of-domain nhẹ nhàng. |
| `ENTERTAINMENT_VOICE` | Giọng tuq27 **trong** nhánh có Tham khảo; cấm "You"/cụt ý. |
| `ENTERTAINMENT_EXPERT_SYSTEM` | Luật bám Tham khảo, anti-hallucination. |
| `COMMUNITY_PRESENTER_SYSTEM` | Trích Reddit/community có format. |
| `GROUNDED_KNOWLEDGE_RULES` | Thêm vào system khi có `Tham khảo`. |
| `COMFORT_SYSTEM`, `ADVICE_SYSTEM`, `CRISIS_SYSTEM` | Tâm lý / khủng hoảng. |

Các node dùng `generate_with_history(_system_with_identity(...), state["messages"])` trừ **entertainment** (dùng pipeline).

---

## 4. Entertainment pipeline & judge

File: `services/agent_service/graph/entertainment_pipeline.py`

- `_build_generation_system(...)` — ghép `expert_system` / `community_system` + `KEEP_TERMS` + `GROUNDED_KNOWLEDGE_RULES` + `Tham khảo:` + `src_text`.
- Các gợi ý retry: `_PLOT_SYNOPSIS_RETRY_HINT`, `_RECOVERY_AFTER_JUDGE_REJECT_HINT`.
- `_build_preference_fallback_system` — fallback preference.

File: `services/agent_service/llm/knowledge_judge.py`

- `JUDGE_SYSTEM` — JSON verdict accept/reject; có rule draft phải là đoạn tiếng Việt trọn, không nhãn "You"/"User:".

---

## 5. Intent classifier

File: `services/agent_service/api/intent_classifier.py`

- `SYSTEM_PROMPT` (template Llama-style nếu dùng local model).
- `INTENT_LLM_SYSTEM` — phân loại intent (greeting, entertainment_knowledge, …).

---

## 6. Retrieval / công cụ

| File | Prompt |
|------|--------|
| `services/agent_service/llm/agentic_retriever.py` | `PLANNER_SYSTEM`, `SEMANTIC_QUERY_SYSTEM` |
| `services/agent_service/llm/retriever_router.py` | `ROUTER_SYSTEM` |
| `services/agent_service/llm/fanwiki_search.py` | `FANWIKI_DOMAIN_SYSTEM` |

---

## 7. Memory extraction (sau mỗi reply)

File: `services/agent_service/llm/memory.py`

- `MEMORY_EXTRACT_SYSTEM` — trích tối đa 3 memory JSON từ history.

---

## 8. Emotion (không dùng LLM)

File: `services/agent_service/graph/emotion.py` — keyword → `emotion` (avatar).

---

## 9. Biến môi trường liên quan

- `LLM_PROVIDER`, `OPENAI_MODEL`, `GROQ_MODEL`, API keys — `client.py`.
- `ENABLE_KNOWLEDGE_JUDGE` — `knowledge_judge.py`.
- `RETRIEVER_MODE`, `ENABLE_DETERMINISTIC_SOURCE_STITCH` — pipeline / retrieval.

---

## 10. Cập nhật khi chỉnh prompt

Khi sửa bất kỳ `*_SYSTEM` hoặc `BASE_PERSONA`, cân nhắc:

- Đồng bộ **giọng** giữa `ENTERTAINMENT_VOICE` và `BASE_PERSONA`.
- Judge có đủ rule để không chấp nhận draft cụt / meta / "You".
