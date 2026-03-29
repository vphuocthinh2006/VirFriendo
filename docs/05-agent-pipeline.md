# 05 — Pipeline agent (LangGraph)

## 5.1 Vai trò

`services/agent_service` triển khai **phân loại intent** và **đồ thị agent** (LangGraph): các nhánh như chit-chat, guardrail, entertainment, comfort, advice, crisis — tùy phiên bản code.

## 5.2 Luồng điển hình (khái niệm)

1. Tin nhắn user vào **core** (`chat`).
2. Core gọi **intent / workflow** trong `graph/` (workflow, state, nodes).
3. Có thể dùng **retrieval** (RAG) — fan wiki, Reddit, v.v. tùy module LLM (xem `services/agent_service/llm/`).
4. Phản hồi trả về client (chunked cho UI Visual Novel).

## 5.3 Cấu hình LLM

- Biến môi trường như `GROQ_API_KEY` và các key khác theo `config` / client trong `services/agent_service/llm/`.

## 5.4 Tài liệu sâu hơn

- Đọc trực tiếp `services/agent_service/graph/workflow.py`, `state.py`, `agents.py` khi chỉnh hành vi agent.
- Thay đổi prompt / retrieval: cân nhắc benchmark và dataset nội bộ (thư mục `scripts/` có thể không nằm trong Git — xem `.gitignore`).
