# 10 — Chuẩn bị chạy app trên AWS

## 1. Mục tiêu

| Thành phần | Mục đích |
|------------|----------|
| **RDS PostgreSQL** | Thay Postgres local; dữ liệu bền, backup AWS. |
| **`DATABASE_URL`** | `postgresql+asyncpg://USER:PASS@RDS_ENDPOINT:5432/DBNAME` |
| **`SECRET_KEY`** | Ký JWT — sinh bằng `openssl rand -hex 32`. |
| **AWS Secrets Manager** | Lưu tất cả secrets — ECS/App Runner đọc lúc chạy. |

## 2. Region và VPC

- Dùng **cùng Region** với ECR để giảm độ trễ.
- Lần đầu: Default VPC ổn. Production nên tách VPC/subnet.

## 3. Tạo RDS PostgreSQL

1. **RDS** → **Create database** → Engine: PostgreSQL.
2. Template: **Free tier** (dev) hoặc instance nhỏ (`db.t4g.micro`).
3. Đặt **Master username** và **Master password** mạnh — lưu vào password manager.
4. **Connectivity:** Public access = No (production); Yes tạm thời khi test.
5. **Database name**: tên DB initial — khớp với `DATABASE_URL`.
6. Đợi trạng thái **Available**.

**Ghi lại:**
- Endpoint RDS
- Port (thường `5432`)
- Master username / password
- Database name

## 4. Security group cho RDS

**Production:**
- Tạo **SG-RDS** gắn RDS.
- Inbound rule: PostgreSQL (5432), Source = **SG-ECS** (security group của ECS tasks).
- Không mở `0.0.0.0/0` vĩnh viễn.

## 5. Ghép `DATABASE_URL`

```
postgresql+asyncpg://USER:PASSWORD@RDS_ENDPOINT:5432/DATABASE_NAME
```

Nếu password có ký tự đặc biệt (`@`, `#`, `:`) → URL-encode (vd. `@` → `%40`).

Test kết nối:
```bash
psql "host=RDS_ENDPOINT port=5432 dbname=DATABASE_NAME user=USER password=PASSWORD sslmode=require"
```

## 6. `SECRET_KEY`

```bash
openssl rand -hex 32
```

Lưu vào Secrets Manager — không dán public.

## 7. AWS Secrets Manager

**Cách 1 — Một secret JSON:**

Tạo secret (vd. `pally/production/api`):

```json
{
  "DATABASE_URL": "postgresql+asyncpg://...",
  "SECRET_KEY": "...hex...",
  "ANTHROPIC_API_KEY": "sk-ant-...",
  "GEMINI_API_KEY": "AIza...",
  "DEEPGRAM_API_KEY": "...",
  "REPLICATE_API_TOKEN": "r8_...",
  "GROQ_API_KEY": "gsk_...",
  "OPENAI_API_KEY": "sk-proj-...",
  "TAVILY_API_KEY": "tvly-...",
  "APP_ENV": "production"
}
```

**Quyền IAM:** role ECS task cần `secretsmanager:GetSecretValue` trên ARN secret.

## 8. Biến tùy chọn

| Biến | Ghi chú |
|------|---------|
| `REDIS_URL` | ElastiCache Redis |
| `CHROMA_SERVER_URL` | Chroma trên AWS |
| `CORS_ORIGINS` | Origin web production (https) |
| `TRUSTED_HOSTS` | Hostname API |

## 9. Schema DB

App có `Base.metadata.create_all` ở startup — tạo bảng thiếu tự động.
Production nên dùng Alembic migration có kiểm soát.

## 10. Frontend build

Khi có URL HTTPS của API:
1. GitHub → **Settings → Variables** → `VITE_PUBLIC_API_URL` = URL đó.
2. Chạy lại workflow ECR publish để image `web` embed đúng API URL.

## 11. Checklist

- [ ] RDS **Available**, endpoint + credentials lưu an toàn.
- [ ] Security group RDS không mở `0.0.0.0/0` vĩnh viễn.
- [ ] `DATABASE_URL` test kết nối được.
- [ ] `SECRET_KEY` sinh bằng `openssl rand -hex 32`, lưu Secrets Manager.
- [ ] Tất cả API keys trong Secrets Manager.
- [ ] IAM role ECS có quyền đọc secret + pull ECR.
- [ ] Sau có domain → `VITE_PUBLIC_API_URL` + rebuild web + `CORS_ORIGINS`.
