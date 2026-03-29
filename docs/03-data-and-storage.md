# 03 — Dữ liệu & lưu trữ

## 3.1 PostgreSQL

- **Vai trò:** User, session chat, diary, metadata ứng dụng (theo models trong `services/core/models.py`).
- **Chạy local:** service `database` trong `docker-compose.yml` (image `postgres:16-alpine`).
- **Migration:** thư mục `migrations/` (Alembic). Ở dev, `main.py` có thể tạo bảng thiếu qua `create_all` — production nên dùng migration có kiểm soát.

## 3.2 Redis

- **Vai trò:** Tuỳ tính năng (ví dụ buffer personality) khi `REDIS_URL` được set.
- **Compose:** service `redis`, cổng host `6379`.

## 3.3 ChromaDB

- **Vai trò:** Vector store cho RAG / retrieval trong agent pipeline.
- **Compose:** service `chromadb`, map cổng host `8003` → container `8000` (kiểm tra client config trong agent service nếu đổi cổng).

## 3.4 Khuyến nghị

- Backup định kỳ DB trước khi thử migration lớn.
- Không commit volume Docker; dữ liệu nhạy cảm chỉ trên môi trường được kiểm soát.
