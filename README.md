# VirFriendo
---

## Tổng quan

**VirFriendo** là ứng dụng chat với AI companion dạng nhân vật anime, giao diện theo phong cách Visual Novel:

- **Chat kiểu VN:** Hội thoại hiển thị từng đoạn (chunks), hiệu ứng karaoke (từng chữ đổi màu), cooldown 5s trước đoạn đầu, click dialogue để skip/advance.
- **Backend:** FastAPI (auth, chat API), LangGraph (intent classification, 6 agent: chit_chat, guardrail, entertainment_expert, comfort, advice, crisis), PostgreSQL + Redis + ChromaDB.
- **Mở rộng:** Emotion-driven avatar, RAG entertainment (anime, manga, game, phim), mini-game (Chess, Quiz), mood tracking (theo kế hoạch).
- **Vận hành hiện tại:** ưu tiên `GPT-4o + RAG + guardrails`, không cần fine-tune model để chạy production.

---

## Kiến trúc

```
Frontend (React + Vite + TS + Tailwind) — UI Visual Novel
    ↕
Core API (FastAPI) — Auth + Chat + LangGraph (services.core + services.agent_service)
    ↕
Data — PostgreSQL, ChromaDB, Redis (docker-compose)
```

---

## Cấu trúc thư mục (repo “product”)

`docs/`, `scripts/`, `tests/`, `integrations/` không được track trong Git (xem `.gitignore`) — giữ bản cục bộ nếu cần. **Addon Source of Mana (Godot)** nằm trên nhánh `archive/sourceofmana-integration`.

```
├── frontend/          # React + Vite + TypeScript (UI)
├── services/
│   ├── core/          # FastAPI — auth, chat, API
│   └── agent_service/ # LangGraph — agents, RAG, LLM
├── shared/            # Schemas dùng chung
├── migrations/        # Alembic
├── requirements.txt
├── docker-compose.yml
└── Makefile
```

---

## Chạy dự án

### Yêu cầu

- Python 3.10+
- Node.js 18+ (cho frontend)
- Docker & Docker Compose (cho DB/infra)

Tạo file **`.env`** ở thư mục gốc (không commit): `SECRET_KEY`, `DATABASE_URL`, và các khóa LLM/search theo nhu cầu. Tuỳ chọn: `CORS_ORIGINS`, `APP_ENV`, `TRUSTED_HOSTS` (xem `services/core/config.py`).

### Backend (Core API)

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn services.core.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Mở http://localhost:5173. **API** chạy tại **http://localhost:8000**. Trong dev, `frontend/src/services/api.ts` mặc định gọi thẳng API (REST + WebSocket `/chat/ws`) — tránh proxy WS qua Vite.

### Hạ tầng (DB, Redis, ChromaDB)

```bash
docker-compose up -d
```

---

## License

MIT (hoặc theo quy định của repo).
