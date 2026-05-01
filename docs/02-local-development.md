# 02 — Chạy local & môi trường

## 2.1 Yêu cầu

| Công cụ | Phiên bản gợi ý |
|---------|-----------------|
| Python | 3.10+ |
| Node.js | 18+ |
| Docker | Bản ổn định + Docker Compose v2 |

## 2.2 Clone & Python

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
```

## 2.3 Biến môi trường

Copy `.env.example` → `.env` và điền giá trị thật. **Không commit `.env`.**

**Bắt buộc:**

| Biến | Ý nghĩa |
|------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://USER:PASS@localhost:5432/DBNAME` |
| `SECRET_KEY` | Ký JWT — sinh bằng `openssl rand -hex 32` |

**LLM (cần ít nhất một):**

| Biến | Ghi chú |
|------|---------|
| `ANTHROPIC_API_KEY` | Claude 3.5 Sonnet — primary chat LLM |
| `GROQ_API_KEY` | Fallback chat + Whisper voice fallback |
| `OPENAI_API_KEY` | Vision fallback (GPT-4o) |
| `GEMINI_API_KEY` | Vision primary (Gemini 1.5 Pro) |
| `DEEPGRAM_API_KEY` | Voice transcription primary |
| `REPLICATE_API_TOKEN` | Image generation (/imagine) |
| `LLM_PROVIDER` | `claude` / `groq` / `openai` / `auto` |

**Tùy chọn:**

| Biến | Mặc định |
|------|---------|
| `CORS_ORIGINS` | `:5173`, `:8081` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `CHROMA_SERVER_URL` | `http://localhost:8003` |
| `TAVILY_API_KEY` | Web search trong agent |

## 2.4 Docker Compose (stack đầy đủ)

```bash
docker compose up --build -d
```

- API: `http://localhost:8000`
- UI: `http://localhost:8081`
- Chroma: `http://localhost:8003`

Chỉ chạy DB + Redis + Chroma:

```bash
docker compose up -d database redis chromadb
```

## 2.5 Chạy API (local, không Docker)

```bash
# Phải chạy từ thư mục gốc project
uvicorn services.core.main:app --reload --port 8000
```

## 2.6 Frontend

```bash
cd frontend
npm install
npm run dev
```

- UI: `http://localhost:5173`
- API: `http://localhost:8000`

**WebSocket:** client trỏ thẳng tới API (`:8000`), không proxy qua Vite.

## 2.7 Makefile

`make run-core`, `make dev`, `make down` — Windows dùng lệnh tương đương trong PowerShell.
