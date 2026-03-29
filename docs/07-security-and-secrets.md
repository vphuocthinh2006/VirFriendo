# 07 — Bảo mật & bí mật

## 7.1 JWT & `SECRET_KEY`

- Access token ký bằng HS256 (`ALGORITHM` trong config).
- `SECRET_KEY` phải ngẫu nhiên đủ dài; sinh ví dụ: `openssl rand -hex 32`.

## 7.2 Production (`APP_ENV=production`)

- `SECRET_KEY` tối thiểu 32 ký tự và không chứa các từ placeholder (xem validator trong `services/core/config.py`).
- Nên đặt `TRUSTED_HOSTS` phù hợp hostname public.
- Tắt OpenAPI `/docs` trên public nếu không cần (logic trong `main.py`).

## 7.3 CORS

- `CORS_ORIGINS` liệt kê rõ origin frontend; không dùng `*` kèm credentials.

## 7.4 Bí mật vận hành

- API keys LLM, connection string DB: chỉ Secret Manager / biến môi trường trên orchestrator, không commit.
