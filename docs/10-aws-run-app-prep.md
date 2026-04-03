# 10 — Chuẩn bị chạy app trên AWS (bước 1 trước khi ECS / App Runner)

Tài liệu này mô tả **chuẩn bị tầng dữ liệu và bí mật** để container API (image từ ECR) chạy **an toàn** trên AWS — **không** thay thế hướng dẫn tạo ECS Service (xem [09-aws-ecr-ecs.md](./09-aws-ecr-ecs.md)).

---

## 1. Mục tiêu bạn cần có sau bước này

| Thành phần | Mục đích |
|------------|----------|
| **RDS PostgreSQL** (hoặc Aurora PostgreSQL) | Thay Postgres máy local / Docker; dữ liệu bền, backup theo policy AWS. |
| **Chuỗi `DATABASE_URL`** | App FastAPI (async) dùng `postgresql+asyncpg://...` — trỏ tới **endpoint RDS**, không phải `localhost`. |
| **`SECRET_KEY`** | Ký JWT — đủ dài, ngẫu nhiên, **không** commit lên git. |
| **Nơi lưu bí mật** | **AWS Secrets Manager** (hoặc SSM Parameter Store *SecureString*) — ECS/App Runner đọc lúc chạy. |
| **(Sau)** URL API công khai | Khi có **ALB / domain** → cấu hình **`VITE_PUBLIC_API_URL`** trên GitHub để build lại image **web**. |

**Tuỳ chọn:** `GROQ_API_KEY`, `REDIS_URL` (ElastiCache), Chroma — làm sau khi core đã chạy.

---

## 2. Chọn Region và VPC

- Dùng **cùng Region** với ECR (vd. `ap-southeast-1`) để giảm độ trễ và đơn giản hóa IAM/ VPC endpoint (nếu sau này cần).
- **VPC:** lần đầu có thể dùng **Default VPC** của account (RDS + ECS sau này cùng VPC dễ nối). Production nên tách VPC/subnet theo best practice — có thể làm sau.

---

## 3. Tạo RDS for PostgreSQL (console)

1. Vào **RDS** → **Create database**.
2. **Engine type:** PostgreSQL (phiên bản tương thích app, vd. 15.x hoặc 16.x).
3. **Templates:**
   - **Dev/test:** `Free tier` nếu account đủ điều kiện, hoặc **Production** với instance nhỏ (vd. `db.t4g.micro` / `db.t3.micro`) để học.
4. **DB instance identifier:** ví dụ `virfriendo-db`.
5. **Master username:** ví dụ `postgres` hoặc `virfriendo` (ghi nhớ).
6. **Master password:** tạo mật khẩu mạnh — **lưu vào password manager**; sẽ dùng trong `DATABASE_URL`.
   - Nếu mật khẩu có ký tự đặc biệt (`@`, `#`, `:`, …) → phải **URL-encode** khi ghép `DATABASE_URL` (hoặc đổi mật khẩu chỉ gồm chữ số + chữ để đỡ lỗi).
7. **Instance configuration:** class phù hợp budget.
8. **Storage:** gp3 mặc định; bật encryption nếu policy yêu cầu.
9. **Connectivity:**
   - **VPC:** Default VPC (hoặc VPC đã chọn).
   - **Public access:** với môi trường học, có thể **Yes** tạm để test từ máy (ít bảo mật hơn). **Production: No** — chỉ cho phép từ ECS/ Lambda trong VPC qua security group.
   - **VPC security group:** tạo **mới** hoặc chọn group có rule phù hợp (bước 4).
10. **Database name** (initial DB): ví dụ `anime_companion` hoặc `virfriendo` — **khớp** với phần cuối `DATABASE_URL`.
11. **Create database** — đợi trạng thái **Available** (vài phút đến vài chục phút).

**Ghi lại:**

- **Endpoint** (vd. `virfriendo-db.xxxxx.ap-southeast-1.rds.amazonaws.com`)
- **Port** (thường `5432`)
- **Master username / password**
- **Database name** đã tạo

---

## 4. Security group cho RDS

RDS chỉ nên nhận PostgreSQL từ **nhóm bảo mật của ECS tasks / App Runner** (hoặc bastion), không mở `0.0.0.0/0` trên production.

**Lần đầu test nhanh (không khuyến nghị production):**

- Inbound rule: **PostgreSQL (5432)** — Source: IP máy bạn / hoặc tạm `0.0.0.0/0` rồi **xóa ngay** sau khi test xong.

**Đúng hướng:**

- Tạo security group **SG-RDS** gắn RDS.
- Tạo **SG-ECS** (hoặc SG App Runner) cho service chạy API.
- Rule inbound trên **SG-RDS:** Type PostgreSQL, Source = **SG-ECS** (reference theo security group id).

Sau khi ECS chạy, chỉnh lại rule — làm khi bạn tạo service (tài liệu ECS chi tiết nằm ngoài file này).

---

## 5. Ghép `DATABASE_URL` cho app (asyncpg)

App dùng SQLAlchemy async — format:

```text
postgresql+asyncpg://USER:PASSWORD@ENDPOINT:5432/DATABASE_NAME
```

Ví dụ (password không có ký tự đặc biệt):

```text
postgresql+asyncpg://virfriendo:MatKhauCuaBan@virfriendo-db.xxxxx.ap-southeast-1.rds.amazonaws.com:5432/anime_companion
```

- **USER** = master username (hoặc user DB bạn tạo sau).
- **PASSWORD** = nếu có `@` → encode thành `%40`, v.v.
- **ENDPOINT** = hostname RDS (không có `https://`).
- **DATABASE_NAME** = tên DB initial khi tạo RDS.

Kiểm tra nhanh từ máy (có `psql`):

```bash
psql "host=VIRFRIENDO_ENDPOINT port=5432 dbname=DATABASE_NAME user=USER password=PASSWORD sslmode=require"
```

(App dùng `asyncpg`; RDS thường bật SSL — trong `DATABASE_URL` có thể cần thêm query `?ssl=require` tùy driver; nếu lỗi SSL, xem tài liệu SQLAlchemy/asyncpg + RDS.)

---

## 6. `SECRET_KEY` (JWT)

- Sinh (trên máy có OpenSSL):

  ```bash
  openssl rand -hex 32
  ```

- Chuỗi hex 64 ký tự — lưu vào **Secrets Manager** (không dán public chat/issue).

`services/core/config.py` yêu cầu `SECRET_KEY` khi `APP_ENV=production` — độ dài và độ mạnh có kiểm tra.

---

## 7. AWS Secrets Manager — gợi ý cấu trúc

**Cách 1 — Một secret JSON (dễ map sang env ECS):**

Tạo secret tên ví dụ `virfriendo/production/api`:

```json
{
  "DATABASE_URL": "postgresql+asyncpg://...",
  "SECRET_KEY": "...hex...",
  "GROQ_API_KEY": "gsk_...",
  "APP_ENV": "production"
}
```

**Cách 2 — Tách từng key** (`virfriendo/database-url`, `virfriendo/secret-key`) — quản lý rotation từng phần dễ hơn.

**Console:** Secrets Manager → **Store a new secret** → **Other type of secret** → Key/value → lưu.

**Quyền IAM:** role của **ECS task** (hoặc App Runner access role) cần `secretsmanager:GetSecretValue` trên ARN secret đó.

---

## 8. Biến tùy chọn (làm sau)

| Biến | Ghi chú |
|------|---------|
| `GROQ_API_KEY` | LLM — nếu không set, một số luồng agent có thể không chạy. |
| `REDIS_URL` | ElastiCache Redis — URL dạng `rediss://...` nếu TLS. |
| `CHROMA_SERVER_URL` | Nếu sau này host Chroma trên AWS. |
| `CORS_ORIGINS` | Danh sách origin web production (https). |
| `TRUSTED_HOSTS` | Hostname API khi bật TrustedHost middleware. |

---

## 9. Schema DB (migration)

- App có `Base.metadata.create_all` ở startup — **tạo bảng thiếu** trên DB mới (additive).
- Nếu dùng **Alembic** trong repo: chạy migration từ CI/CD hoặc bastion trước khi bật traffic — xem `migrations/` và [03-data-and-storage.md](./03-data-and-storage.md).

---

## 10. Frontend build (`VITE_PUBLIC_API_URL`)

**Chỉ làm khi đã có URL HTTPS** của API (vd. `https://api.example.com`):

1. GitHub repo → **Settings → Variables** → `VITE_PUBLIC_API_URL` = URL đó.
2. Chạy lại workflow **ECR publish** (push hoặc Run workflow) để image **web** embed đúng API.

Nếu set sớm URL tạm rồi đổi sau — build lại image web.

---

## 11. Checklist tóm tắt

- [ ] RDS **Available**, endpoint + DB name + user/pass đã lưu an toàn.
- [ ] Security group RDS **không** mở rộng vĩnh viễn `0.0.0.0/0` (trừ test ngắn).
- [ ] `DATABASE_URL` đầy đủ, test kết nối được (psql hoặc app local trỏ RDS).
- [ ] `SECRET_KEY` sinh bằng `openssl rand -hex 32`, lưu Secrets Manager.
- [ ] (Tuỳ) `GROQ_API_KEY` và secret khác trong Secrets Manager.
- [ ] IAM role cho ECS/App Runner có quyền đọc secret + pull ECR.
- [ ] Sau có domain API → `VITE_PUBLIC_API_URL` + rebuild web + `CORS_ORIGINS` trên API.

Bước tiếp theo: tạo **ECS Service** hoặc **App Runner** trỏ image `virfriendo-api`, inject env từ Secrets Manager — xem [09-aws-ecr-ecs.md](./09-aws-ecr-ecs.md) mục deploy.
