# 08 — Xử lý sự cố

## WebSocket không kết nối

- Frontend phải gọi **đúng origin API** (`http://localhost:8000`), không proxy WS qua Vite.
- Kiểm tra `CORS_ORIGINS` có chứa origin UI (`http://localhost:5173`).
- WS token hết hạn → logout và login lại.

## Lỗi kết nối PostgreSQL

- Compose đã chạy: `docker compose ps`.
- `DATABASE_URL` khớp user/password/db với `POSTGRES_*` trong `.env`.
- Chạy uvicorn phải từ **thư mục gốc project** (chứa `services/`).

## `ModuleNotFoundError: No module named 'services'`

Bạn đang chạy uvicorn từ thư mục sai. Phải chạy từ thư mục gốc:

```bash
cd /path/to/project   # thư mục chứa services/, frontend/, requirements.txt
uvicorn services.core.main:app --reload --port 8000
```

## Redis / Chroma không dùng được

- Redis: port `6379`.
- Chroma: compose map `8003` → container `8000`.

## `/imagine` không hoạt động

- Kiểm tra `REPLICATE_API_TOKEN` trong `.env`.
- Sau khi đổi `.env`, chạy `docker-compose up -d api` (không rebuild) để container load env mới.

## Voice transcription lỗi

- Kiểm tra `DEEPGRAM_API_KEY` trong `.env`.
- Fallback: `GROQ_API_KEY` cho Whisper.
- Browser cần cấp quyền microphone.

## Vision analysis lỗi

- Kiểm tra `GEMINI_API_KEY` trong `.env`.
- Fallback: `OPENAI_API_KEY` cho GPT-4o.

## Container không load code mới

- Uvicorn trong Docker **không có** `--reload` — phải `docker restart <container>` sau khi copy file.
- Hoặc dùng `docker-compose up -d api` để recreate container với `.env` mới.

## OpenAPI không thấy

- `APP_ENV=production` và `DEBUG=false` → `/docs` bị tắt — đúng thiết kế.
- Dev: `DEBUG=true` hoặc `APP_ENV=development`.
