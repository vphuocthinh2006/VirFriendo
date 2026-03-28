# Trạng thái dự án & lộ trình (VirFriendo)

> **Cập nhật:** 2026-03-29  
> **Tài liệu liên quan:** [01_project_plan.md](01_project_plan.md) · [05_checklist.md](05_checklist.md) · [THESIS_DELTA.md](THESIS_DELTA.md)

---

## 1. Tóm tắt: đang ở giai đoạn nào?

| Phase | Nội dung | Trạng thái (ước lượng) | Ghi chú |
|-------|----------|------------------------|---------|
| **Phase 1 — Foundation** | Monorepo, Docker Compose (DB/Redis/Chroma), Auth, Chat API, Frontend SPA | **~98%** | Thiếu CI/CD tự động |
| **Phase 2 — Core AI** | Intent, Emotion, LangGraph agents, RAG, retriever router, LLM, user memory | **~90%** | WebSocket streaming **đã có**; ChromaDB trong compose **chưa** làm RAG vector chính (đang ưu tiên API ngoài + pipeline code) |
| **Phase 3 — Avatar & UX** | UI VN, portrait, theme; animation nâng cao | **~45%** | Chat/landing/menu ổn; **avatar Spine/Pixi theo emotion** chưa đầy đủ |
| **Phase 4 — Games & tích hợp** | Cờ, mini-game, Godot bridge | **~35%** | Backend chess + caro; helper `turn_game_ai`; frontend: Snake, Tetris, Ringrealms (RTS); tích hợp Source of Mana (addon) |
| **Phase 5 — Production** | Deploy, quan sát, bảo mật vận hành | **~25%** | Có Docker Compose dev; **chưa** K8s/Actions; có pytest nhưng chưa gate CI |

**Kết luận ngắn:** Có thể coi **Phase 2 đã đạt mục tiêu chức năng chính** (chat AI end-to-end + RAG + WS). Còn lại chủ yếu là **đánh bóng UX/avatar**, **mở rộng game**, và **chuẩn hóa production** (CI, secrets, HTTPS, backup).

---

## 2. Đã có (đúng với code hiện tại)

### Hạ tầng

- **Docker Compose:** PostgreSQL 16, Redis 7, ChromaDB (Chroma chưa bắt buộc cho luồng chat chính).
- **DB:** User, Conversation, Message, UserMemory, quan hệ agent/user (Alembic migrations trong `migrations/`).
- **Auth:** Đăng ký, đăng nhập, JWT; Google OAuth (frontend + env); route bảo vệ bằng `get_current_user_id`.

### Backend (FastAPI — `services/core`)

- **`/auth`** — register, login, forgot password, Google.
- **`/chat`** — `POST` chat đồng bộ; **`GET`** conversations, history, memories, relationship; **`WebSocket /chat/ws`** — streaming token (LangGraph).
- **`/agents`** — stats, like, play counter.
- **`/diary`** — nhật ký companion.
- **`/game`** — chess (python-chess + Stockfish nếu có `STOCKFISH_PATH`), caro, nền tảng cờ (`game.py`, `caro`); `turn_game_ai` dùng nội bộ cho bot/lượt.
- **`/game/external`** — API cho client ngoài (Godot): `external_game.py`.
- **`/health`** — health check.

### Agent service (LangGraph — `services/agent_service`)

- Workflow: intent → routing → các agent (chit_chat, guardrail, entertainment_expert, comfort, advice, crisis).
- Intent hybrid (keyword + LLM); emotion; RAG + retriever router + knowledge judge; entertainment pipeline; retriever bổ sung (fanwiki, reddit, v.v. theo env).

### Frontend (`frontend/`)

- React + Vite + TypeScript + Tailwind; chat kiểu Visual Novel (chunks, karaoke text).
- Trang: Landing, Menu, Chat, Login/Register, Contact, ForgotPassword, Updates.
- **API client:** `src/services/api.ts` — dev mặc định gọi API **`http://localhost:8000`** (tránh proxy WebSocket qua Vite).
- Mini-game trong app: Snake, Tetris, Ringrealms (Ancient RTS), v.v.
- Loading/connect: overlay CSS (không còn bundle Three.js cho màn hình chờ).

### Kiểm thử

- Thư mục **`tests/`**: `test_auth_api`, `test_chat_api`, `test_intent`, `test_retriever_router`, `test_security`, `test_ws`, `conftest.py`, golden retrieval JSONL.

### Tích hợp khác

- **`integrations/sourceofmana/`** — addon Godot Companion AI bridge (tài liệu trong thư mục).

---

## 3. Chưa có / cần làm (ưu tiên)

### P0 — Nên làm trước khi “production thật”

- [ ] **CI (GitHub Actions):** lint Python + `pytest` + `npm run build` (hoặc `vite build`) trên push/PR.
- [ ] **Bí mật & cấu hình:** `SECRET_KEY`, DB, API keys chỉ trên host / secret manager; không commit `.env`.
- [ ] **HTTPS + reverse proxy** (Caddy/nginx/Cloudflare) cho domain thật.
- [ ] **Build frontend production:** `VITE_API_URL=https://api.của-bạn...` tại thời điểm build.

### P1 — Sản phẩm & chất lượng

- [ ] **Chroma / embedding RAG** nếu muốn vector store nội bộ thay vì chỉ API ngoài.
- [ ] **Avatar animation** theo `avatar_action` / emotion (Spine/Pixi hoặc sprite).
- [ ] **Mood timeline / dashboard** (hiện có memory + relationship, chưa dashboard tổng hợp).
- [ ] **Giám sát:** logging tập trung, uptime (tối thiểu health + log errors).

### P2 — Mở rộng

- [ ] Anime Quiz (RAG) hoàn chỉnh trong UI nếu chưa có.
- [ ] TTS (Edge/VOICEVOX).
- [ ] Adaptive personality nâng cao (ngoài relationship level hiện tại).

### Nợ kỹ thuật (định kỳ dọn)

- [ ] Rà soát folder/agent trùng tên cũ (nếu còn trong repo).
- [ ] Đồng bộ `docs/01_project_plan.md` diagram “monorepo cũ” với cấu trúc `services/core` + `services/agent_service` hiện tại (hoặc đọc như lịch sử thiết kế).

---

## 4. Sơ đồ kiến trúc (thực tế triển khai dev)

```
Browser (localhost:5173)
    │  REST + WebSocket trực tiếp tới API (khuyến nghị: localhost:8000)
    ▼
FastAPI (services.core.main)
    ├── auth, chat (+ WS /chat/ws), agents, diary, game, external_game, caro
    └── LangGraph + agent_service (cùng process)
            ├── PostgreSQL
            ├── Redis (tùy tính năng)
            └── LLM / search APIs (OpenAI, Groq, Tavily, … theo .env)
```

---

## 5. Định nghĩa “xong Phase 2” (gợi ý)

Có thể **chốt Phase 2** khi:

1. Chat qua **REST + WebSocket** ổn định với token hợp lệ.  
2. Intent + emotion + ít nhất một đường RAG entertainment **chạy được trên staging**.  
3. Có **ít nhất một bộ test tự động** chạy được locally (đã có trong `tests/` — cần **CI** để khỏi regress).

Phase 3–5 là **độ sâu UX, game, và vận hành** — không chặn việc gọi Phase 2 “đã đạt MVP AI”.
