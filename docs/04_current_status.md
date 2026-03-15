# 📍 Trạng thái hiện tại & Bước tiếp theo (VirFriendo)

> Cập nhật theo đánh giá codebase và [01_project_plan.md](01_project_plan.md).

---

## 1. Project đang ở bước nào?

Theo **Phase** trong project plan:

| Phase | Nội dung | Trạng thái |
|-------|----------|------------|
| **Phase 1 — Foundation** | Monorepo, Docker, DB, Auth, Chat API, Frontend scaffold | **~70%** — Thiếu Frontend + CI/CD |
| **Phase 2 — Core AI** | Intent/Emotion model, RAG, 8 agents, LLM, Translation | **~25%** — Có skeleton, đa số đang mock |
| **Phase 3 — Avatar & Frontend** | Avatar, Chat UI, Mood | **0%** |
| **Phase 4 — Games & Extras** | Chess, Quiz, Bibliotherapy | **0%** |
| **Phase 5 — Production** | K8s, Monitoring, Docs | **0%** |

**Kết luận:** Project đang ở **cuối Phase 1, bắt đầu Phase 2**. Nền (backend API, auth, chat với LangGraph, DB) đã có; phần AI thật (model, RAG, LLM) và frontend chưa có.

---

## 2. Đã có gì (đã làm xong / đang dùng)

- **Docker Compose:** PostgreSQL, Redis, ChromaDB.
- **Database:** Schema User, Conversation, Message (Alembic migrations); lưu intent/emotion/avatar_action.
- **Auth:** Register, Login, JWT; bảo vệ route bằng `get_current_user_id`.
- **Chat API (REST):**
  - `POST /chat` — gửi tin, chạy LangGraph, trả reply + intent + emotion + avatar_action.
  - `GET /chat/conversations` — danh sách hội thoại.
  - `GET /chat/history/{id}` — lịch sử tin nhắn (có intent/emotion/avatar).
- **LangGraph:** 1 node classifier (intent) → route → 6 agent nodes (chit_chat, guardrail, comic_expert, comfort, advice, crisis). Mỗi agent trả message + emotion + avatar_action (mock).
- **Intent classifier:** Keyword mặc định; có thể bật model Llama+PEFT qua `INTENT_MODEL_PATH` + `ENABLE_INTENT_MODEL_RUNTIME=true`.
- **Emotion detector:** Node keyword-based (7 class) trong workflow; state có `emotion` cho avatar.
- **Model intent:** Có sẵn trong `services/agent-service/models/intent` (PEFT adapter), nối qua env.

---

## 3. Chưa có / Đang mock

- **Frontend:** Chưa có thư mục `frontend/` (React + Vite).
- **WebSocket / streaming:** Chat chỉ REST, chưa real-time/streaming.
- **Intent model thật:** Có thể bật bằng env (load Llama+PEFT); mặc định vẫn keyword.
- **Emotion detector:** Đã có node keyword trong workflow; có thể thay bằng model sau.
- **RAG:** Comic expert chỉ trả câu mock, chưa embed + ChromaDB + retriever.
- **LLM:** Chưa gọi GPT-4o/Gemini; reply đang fix cứng trong từng agent.
- **Translation (VN↔EN):** Chưa có.
- **Game (Chess, Quiz), Mood API, Avatar UI:** Chưa có.

---

## 4. Nên làm tiếp theo (gợi ý thứ tự)

### A. Hoàn nốt Phase 1 (nền tảng)

1. **Frontend scaffold (React + Vite + TS)**  
   Tạo app tối thiểu: login/register, 1 trang chat (gọi `POST /chat`, hiển thị reply). Không cần avatar/mood ngay.

2. **(Tùy chọn) CI/CD skeleton**  
   GitHub Actions: lint (ruff), test (pytest khi có test), build Docker image.

### B. Phase 2 — Core AI (ưu tiên cao)

3. **Bật Intent model thật**  
   Trong `agent_service`: load model từ `INTENT_MODEL_PATH` (hoặc path cố định tới `models/intent_merged`), thay keyword bằng inference. Giữ keyword làm fallback nếu load lỗi.

4. **Thêm Emotion detector vào workflow**  
   Một node sau classifier (hoặc song song): input message → emotion label (7 class). Cập nhật state `emotion`; có thể dùng keyword đơn giản trước, sau thay bằng model.

5. **Kết nối LLM (GPT-4o / Gemini)**  
   Trong mỗi agent: thay reply fix cứng bằng gọi LLM với system prompt + user message. Cần API key trong env.

6. **RAG cho Comic Expert**  
   Embed query → ChromaDB (đã có trong docker-compose) → retriever → (re-ranker nếu có) → đưa context vào LLM để sinh câu trả lời.

7. **(Sau) Translation layer**  
   Nếu muốn model xử lý tiếng Anh: VN→EN trước khi vào classifier/LLM, EN→VN cho reply.

### C. Phase 3 trở đi

8. **Chat UI đẹp + Avatar (PixiJS/Spine)**  
   Hiển thị avatar; map `avatar_action` từ API → animation (idle, happy, sad, …).

9. **Mood tracking API + dashboard**  
   Lưu emotion theo thời gian (có thể dùng bảng mood hoặc aggregate từ message); API + biểu đồ trên frontend.

10. **Games (Chess, Anime Quiz)**  
    Dịch vụ/game logic riêng, gọi từ API hoặc từ frontend.

---

## 5. Một việc “nhanh” có thể làm ngay

- **Viết vài test (pytest)** cho `POST /chat`, `GET /chat/conversations`, `GET /chat/history/{id}` (và auth nếu muốn). Giúp refactor sau này an toàn và sẵn sàng cho CI.

---

**Tóm tắt:** Bạn đang ở **bước cuối Phase 1, đầu Phase 2**. Nên làm tiếp theo: **(1) Frontend scaffold** để có giao diện chat thật, **(2) Bật intent model thật + thêm emotion node**, **(3) Kết nối LLM** cho các agent, **(4) RAG cho comic expert**. Sau đó mới tới avatar, mood, games.
