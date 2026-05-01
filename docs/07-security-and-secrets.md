# 07 — Bảo mật & bí mật

## 7.1 JWT & `SECRET_KEY`

- Access token ký bằng HS256.
- Sinh `SECRET_KEY`: `openssl rand -hex 32`
- Production: tối thiểu 32 ký tự, không dùng placeholder.

## 7.2 Production checklist

- [ ] `APP_ENV=production`
- [ ] `SECRET_KEY` đủ mạnh (validator trong `config.py`)
- [ ] `TRUSTED_HOSTS` khớp hostname public
- [ ] `/docs` tắt trên public (`DEBUG=false`)
- [ ] `CORS_ORIGINS` liệt kê rõ origin — không dùng `*` kèm credentials

## 7.3 CORS

- `CORS_ORIGINS` trong `.env` — danh sách origin frontend cách nhau bằng dấu phẩy.
- Không dùng wildcard `*` khi `allow_credentials=True`.

## 7.4 Security headers

Middleware tự động thêm:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`

## 7.5 SSRF protection

`/chat/analyze-media` (web scraping) block private/loopback IPs — không thể trỏ tới `127.0.0.1`, `10.x.x.x`, `192.168.x.x`, v.v.

## 7.6 Bí mật vận hành

- API keys LLM, DB connection string: chỉ **Secrets Manager** / biến môi trường trên orchestrator.
- **Không commit** `.env` — đã gitignored.
- Dùng `.env.example` làm template.

## 7.7 Khi key bị lộ

1. Revoke key ngay trên dashboard provider.
2. Generate key mới.
3. Update `.env` (local) và Secrets Manager (production).
4. Không cần rebuild container — chỉ `docker-compose up -d api`.
