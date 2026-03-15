# VirFriendo

> AI Anime Companion — người bạn ảo kiểu Visual Novel: trò chuyện theo từng đoạn (streaming + karaoke), nhận diện cảm xúc, intent classification và nhiều agent chuyên biệt.

---

## Tổng quan

**VirFriendo** là ứng dụng chat với AI companion dạng nhân vật anime, giao diện theo phong cách Visual Novel:

- **Chat kiểu VN:** Hội thoại hiển thị từng đoạn (chunks), hiệu ứng karaoke (từng chữ đổi màu), cooldown 5s trước đoạn đầu, click dialogue để skip/advance.
- **Backend:** FastAPI (auth, chat API), LangGraph (intent classification, 6 agent: chit_chat, guardrail, comic_expert, comfort, advice, crisis), PostgreSQL + Redis + ChromaDB.
- **Mở rộng:** Emotion-driven avatar, RAG manga/anime, mini-game (Chess, Quiz), mood tracking (theo kế hoạch).

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

## Cấu trúc thư mục

```
├── frontend/                 # React + Vite + TypeScript, giao diện VN
├── services/
│   ├── core/                 # FastAPI — main, auth, chat, database
│   └── agent_service/        # LangGraph — workflow, state, agents, intent_classifier
├── shared/                   # Shared schemas (auth)
├── docs/                     # Tài liệu dự án
├── migrations/               # Alembic
├── requirements.txt
└── docker-compose.yml        # PostgreSQL, Redis, ChromaDB
```

---

## Chạy dự án

### Yêu cầu

- Python 3.10+
- Node.js 18+ (cho frontend)
- Docker & Docker Compose (cho DB/infra)

### Backend (Core API)

```bash
# Tạo venv và cài dependency
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt

# Chạy API (port 8000)
uvicorn services.core.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Mở http://localhost:5173. Proxy `/auth` và `/chat` tới backend (cần chạy Core API tại port 8000).

### Hạ tầng (DB, Redis, ChromaDB)

```bash
docker-compose up -d
```

---

## Tài liệu

- [01 — Project Plan](docs/01_project_plan.md)
- [02 — System Architecture](docs/02_system_architecture.md)
- [03 — Taxonomy & Dataset](docs/03_taxonomy_and_dataset.md)
- [04 — Current Status](docs/04_current_status.md)

---

## License

MIT (hoặc theo quy định của repo).
