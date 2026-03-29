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
| `CORS_ORIGINS` | Danh sách origin có dấu phẩy, ví dụ `http://localhost:5173` |
| `TRUSTED_HOSTS` | Production: hostname được phép (không gồm scheme) |
| `GROQ_API_KEY` | Tuỳ chọn — LLM qua Groq nếu cấu hình |
| `REDIS_URL` | Tuỳ chọn — buffer/quickstart personality nếu dùng |

Không commit file `.env`.

## 2.4 Hạ tầng dữ liệu (Docker Compose)

Chỉ các service Postgres, Redis, ChromaDB (xem `docker-compose.yml`):

```bash
docker compose up -d
```

Biến cho Postgres thường đặt trong `.env`: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — khớp với `DATABASE_URL`.

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
