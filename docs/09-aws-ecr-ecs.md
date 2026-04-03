# 09 — AWS: ECR + triển khai (ECS / App Runner)

Tài liệu ngắn cho pipeline **GitHub Actions → Amazon ECR** và hướng **deploy** phổ biến.

## 1. ECR — tạo repository

1. Console **Amazon ECR** → *Private registry* → **Create repository**.
2. Tạo hai repo (tên khớp workflow, hoặc sửa `ECR_REPOSITORY_*` trong `.github/workflows/ecr-publish.yml`):
   - `virfriendo-api`
   - `virfriendo-web`
3. Chọn **region** (ví dụ `ap-southeast-1`) — ghi nhớ cho bước secrets.

Image sau khi push:

`<account_id>.dkr.ecr.<region>.amazonaws.com/virfriendo-api:<tag>`

## 2. IAM — quyền cho CI (access key), làm kỹ từng bước

Mục tiêu: một **IAM user** chỉ dùng để **GitHub Actions đăng nhập ECR và push image** — không cần quyền EC2, RDS, v.v. (có thể thu hẹp sau).

### 2.1 Vào đúng account và region IAM

1. Đăng nhập [AWS Console](https://console.aws.amazon.com).
2. Góc phải trên kiểm tra **Account ID** (phải trùng account có ECR, ví dụ `292773837061`).
3. **IAM là dịch vụ toàn account** — không chọn region như ECR, nhưng access key dùng được cho mọi region; bạn vẫn sẽ ghi **`AWS_REGION=ap-southeast-1`** trên GitHub cho đúng region ECR.

### 2.2 Tạo IAM user

1. Tìm dịch vụ **IAM** (ô search gõ `IAM`).
2. Menu trái → **Users** → **Create user**.
3. **User name**: ví dụ `github-ecr-virfriendo` (tên gợi nhớ, không ảnh hưởng kỹ thuật).
4. **AWS Management Console access**: **không** bật “Provide user access to the AWS Management Console” nếu user chỉ dùng access key cho CI (không cần đăng nhập web bằng password).
5. **Next**.

### 2.3 Gắn quyền (policy)

**Cách đơn giản (đủ cho CI push ECR):**

1. Chọn **Attach policies directly**.
2. Ô tìm kiếm gõ: `AmazonEC2ContainerRegistryPowerUser`.
3. Tick chọn policy đó → **Next**.

Policy này cho phép thao tác ECR (push/pull image) trong account; **không** tự động cho phép xóa toàn bộ AWS — vẫn nên giữ access key trong GitHub Secrets, không commit lên git.

**Cách chặt hơn (tùy chọn, sau này):** tạo custom policy chỉ `ecr:GetAuthorizationToken` (resource `*`) và các API push trên ARN hai repo `virfriendo-api` / `virfriendo-web`. Lúc đầu dùng managed policy ở trên cho nhanh.

### 2.4 Hoàn tất tạo user

1. **Next** → **Create user**.
2. Vào lại **Users** → bấm vào user vừa tạo → tab **Permissions** → xác nhận đã có policy **AmazonEC2ContainerRegistryPowerUser** (hoặc policy tùy chỉnh).

### 2.5 Tạo Access key (Access key ID + Secret)

1. Vẫn trong trang user → tab **Security credentials** (hoặc **Security** tùy giao diện).
2. Kéo xuống **Access keys** → **Create access key**.
3. **Use case**: chọn **Application running outside AWS** (hoặc “Command Line Interface (CLI)” — cả hai đều được; quan trọng là key dùng ngoài console).
4. Tick xác nhận (nếu có) → **Next** → **Create access key**.
5. Màn hình hiện:
   - **Access key ID** — chuỗi bắt đầu thường là `AKIA...`
   - **Secret access key** — **chỉ hiện một lần**
6. Bấm **Download .csv** hoặc copy vào chỗ an toàn (password manager). **Không** dán vào Slack/email công khai.

Nếu đóng màn hình mà chưa lưu Secret: phải **Create access key** mới và **vô hiệu hóa** key cũ (Deactivate/Delete) trong cùng mục Access keys.

### 2.6 Gắn vào GitHub Secrets (khớp workflow)

Trên **GitHub** → repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret | Giá trị |
|--------|---------|
| `AWS_ACCESS_KEY_ID` | Access key ID (dòng `AKIA...`) |
| `AWS_SECRET_ACCESS_KEY` | Secret access key |
| `AWS_REGION` | `ap-southeast-1` (đúng region có ECR) |

**Lưu ý:** `AWS_REGION` đặt là **Repository secret** giống hai secret kia (workflow đang đọc `secrets.AWS_REGION`).

### 2.7 Kiểm tra nhanh

1. Push code lên `main` (đã có `.github/workflows/ecr-publish.yml`).
2. **Actions** → workflow **ECR publish** → phải **xanh**.
3. **ECR** → từng repository → tab **Images** → có tag mới (vd. `latest`).

Nếu lỗi **denied / unauthorized**:

- User có đúng policy ECR?
- Secret trên GitHub đúng tên, không thừa khoảng trắng?
- Region secret trùng region repo ECR?

### 2.8 Bảo mật & về lâu dài

- Không commit access key vào repo; chỉ dùng **GitHub Secrets**.
- Key lộ: **Deactivate/Delete** key cũ trong IAM → tạo key mới → cập nhật Secrets.
- Muốn **không lưu access key**: dùng **OIDC** (mục 4 dưới) — GitHub nhận token ngắn hạn, assume role AWS.

## 3. GitHub — biến cho frontend build

File `frontend` build nhúng `VITE_API_URL` vào bundle. Trên GitHub: **Settings → Secrets and variables → Actions → Variables**:

| Variable | Ví dụ |
|----------|--------|
| `VITE_PUBLIC_API_URL` | `https://api.ban.com` (URL public của FastAPI sau khi deploy) |

Nếu không set, workflow dùng `http://localhost:8000` (chỉ hợp lý khi test; production nên set URL thật).

## 4. OIDC (khuyến nghị, không lưu access key lâu dài)

Thay access key bằng **GitHub OIDC → IAM role**:

1. IAM → **Identity provider**: OIDC `token.actions.githubusercontent.com`.
2. IAM **Role** trust policy: `sts:AssumeRoleWithWebIdentity` cho repo của bạn.
3. Gắn policy ECR push như trên.
4. Trong workflow, thay `configure-aws-credentials` bằng `role-to-assume: arn:aws:iam::ACCOUNT:role/ROLE_NAME` và bật `permissions: id-token: write`.

Chi tiết: [aws-actions/configure-aws-credentials](https://github.com/aws-actions/configure-aws-credentials).

## 5. Deploy — lựa chọn

### A) **ECS Fargate** (phổ biến cho API + có thể tách web)

- **VPC**: public subnets + ALB, hoặc private + NAT.
- **Task definition**: image từ ECR `virfriendo-api`; env từ **Secrets Manager** / SSM: `DATABASE_URL`, `SECRET_KEY`, `GROQ_API_KEY`, …
- **Service**: desired count ≥ 1; health check HTTP → `/health`.
- **RDS** (PostgreSQL) hoặc Aurora thay cho Postgres trong compose.
- Service thứ hai (hoặc cùng ALB path-based) cho image `virfriendo-web`, hoặc phục vụ static qua **S3 + CloudFront** nếu tách build.

### B) **App Runner** (đơn giản hơn, ít cấu hình mạng)

- Tạo **App Runner service** trỏ source = **ECR** image `virfriendo-api`.
- Phù hợp API có HTTP health; WebSocket cần kiểm tra giới hạn App Runner.
- Frontend có thể App Runner riêng hoặc CloudFront + S3.

### C) **EC2 + docker compose**

- Máy EC2 cài Docker; `docker compose` kéo image từ ECR (`aws ecr get-login-password`); phù hợp MVP, ít “managed” hơn.

## 6. Kéo image trên máy chủ (EC2 / bastion)

```bash
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com
docker pull $ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/virfriendo-api:latest
```

Task execution role (ECS) cần quyền `ecr:BatchGetImage` + `logs` nếu ghi CloudWatch.

## 7. Checklist sau khi có URL API production

- [ ] `VITE_PUBLIC_API_URL` trên GitHub = URL API (https).
- [ ] `CORS_ORIGINS` / `TRUSTED_HOSTS` trên API khớp domain web.
- [ ] `DATABASE_URL` trỏ RDS, không dùng `localhost` trong container.
