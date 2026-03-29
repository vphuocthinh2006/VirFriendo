# 08 — Xử lý sự cố (FAQ ngắn)

## WebSocket không kết nối / disconnect trong dev

- Đảm bảo frontend gọi **đúng origin API** (ví dụ `http://localhost:8000`), không proxy WebSocket qua Vite — xem `frontend/src/services/api.ts`.
- Kiểm tra `CORS_ORIGINS` có chứa origin UI (ví dụ `http://localhost:5173`).

## Lỗi kết nối PostgreSQL

- Compose đã chạy: `docker compose ps`.
- `DATABASE_URL` khớp user/password/db với biến `POSTGRES_*` trong `.env`.

## Redis / Chroma không dùng được

- Kiểm tra cổng: Redis `6379`, Chroma trên compose map `8003` → kiểm tra URL client trong code agent nếu custom.

## Migration / schema

- Dev có thể dùng `create_all` — môi trường shared/production nên dùng Alembic có kiểm soát.

## OpenAPI không thấy

- Trên `APP_ENV=production` và `DEBUG=false`, `/docs` có thể bị tắt — đúng thiết kế.
