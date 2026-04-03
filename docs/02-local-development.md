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

## 2.3 Biến môi trường (`.env` ở thư mục gốc)

**Bắt buộc** (xem `services/core/config.py`):

| Biến | Ý nghĩa |
|------|---------|
| `DATABASE_URL` | Chuỗi async SQLAlchemy, ví dụ `postgresql+asyncpg://USER:PASS@localhost:5432/DBNAME` |
| `SECRET_KEY` | Ký JWT; production: ≥32 ký tự, không dùng chuỗi placeholder |

**Thường dùng:**

| Biến | Mặc định / ghi chú |
|------|-------------------|
| `APP_ENV` | `development` — `production` bật kiểm tra `SECRET_KEY` chặt hơn |
| `CORS_ORIGINS` | Mặc định trong code gồm `:5173` (Vite) và `:8081` (UI Docker Compose; kèm `:8080` nếu cần); thêm origin production khi cần |
| `TRUSTED_HOSTS` | Production: hostname được phép (không gồm scheme) |
| `GROQ_API_KEY` | Tuỳ chọn — LLM qua Groq nếu cấu hình |
| `REDIS_URL` | Tuỳ chọn — buffer/quickstart personality; Compose gán `redis://redis:6379/0` cho service `api` |
| `CHROMA_SERVER_URL` | Tuỳ chọn — HTTP Chroma; Compose gán `http://chromadb:8000` cho `api` |

Không commit file `.env`.

## 2.4 Docker Compose (stack đầy đủ — Pha 1)

File `docker-compose.yml` gồm `database`, `redis`, `chromadb`, `api` (build `Dockerfile` gốc), `web` (build `frontend/Dockerfile`, nginx phục vụ static). Cần `.env` với `POSTGRES_*`, `SECRET_KEY`, và `DATABASE_URL` hợp lệ (Compose vẫn override `DATABASE_URL` / `REDIS_URL` / `CHROMA_SERVER_URL` cho container `api`).

```bash
docker compose up --build -d
```

- API: `http://localhost:8000` (kể cả `/health`, `/docs`)
- UI tĩnh (build Vite, `VITE_API_URL=http://localhost:8000`): `http://localhost:8081` (tránh xung đột cổng 8080 trên Windows)
- Chroma (host): `http://localhost:8003`

Chỉ chạy DB + Redis + Chroma (không build API/web): `docker compose up -d database redis chromadb`.

## 2.5 Chạy API

```bash
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

**WebSocket:** client nên trỏ trực tiếp tới API (`:8000`), không proxy WS qua Vite — xem [08-troubleshooting.md](./08-troubleshooting.md).

## 2.7 Makefile (tuỳ chọn)

`make run-core`, `make dev` / `make down` — trên Windows có thể chạy lệnh tương đương trong PowerShell nếu không có `make`.
