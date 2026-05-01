# 09 — AWS: ECR + triển khai

## 1. ECR — tạo repository

1. Console **Amazon ECR** → *Private registry* → **Create repository**.
2. Tạo hai repo (tên khớp với `ECR_REPOSITORY_*` trong `.github/workflows/ecr-publish.yml`):
   - `pally-api`
   - `pally-web`
3. Chọn **region** phù hợp — ghi nhớ cho bước secrets.

## 2. IAM — quyền cho CI

Tạo **IAM user** chỉ dùng để GitHub Actions đăng nhập ECR và push image.

### 2.1 Tạo IAM user

1. IAM → **Users** → **Create user**.
2. Không bật Console access (chỉ dùng access key).

### 2.2 Gắn policy

- **`AmazonEC2ContainerRegistryPowerUser`** — đủ cho CI push ECR.
- Hoặc custom policy chỉ cho phép push trên ARN hai repo cụ thể (chặt hơn).

### 2.3 Tạo Access key

1. Tab **Security credentials** → **Create access key**.
2. Use case: **Application running outside AWS**.
3. Lưu **Access key ID** và **Secret access key** — chỉ hiện một lần.

### 2.4 GitHub Secrets

**Settings → Secrets and variables → Actions:**

| Secret | Giá trị |
|--------|---------|
| `AWS_ACCESS_KEY_ID` | Access key ID |
| `AWS_SECRET_ACCESS_KEY` | Secret access key |
| `AWS_REGION` | Region ECR (vd. `ap-southeast-1`) |

### 2.5 Kiểm tra

Push code lên `main` → **Actions** → workflow **ECR publish** → phải xanh → ECR có tag mới.

## 3. GitHub — biến cho frontend build

**Settings → Variables → Actions:**

| Variable | Ví dụ |
|----------|--------|
| `VITE_PUBLIC_API_URL` | `https://api.yourdomain.com` |

## 4. OIDC (khuyến nghị — không lưu access key lâu dài)

1. IAM → **Identity provider**: OIDC `token.actions.githubusercontent.com`.
2. IAM **Role** trust policy: `sts:AssumeRoleWithWebIdentity` cho repo của bạn.
3. Gắn policy ECR push.
4. Workflow dùng `role-to-assume` thay vì access key.

Chi tiết: [aws-actions/configure-aws-credentials](https://github.com/aws-actions/configure-aws-credentials).

## 5. Deploy

### A) ECS Fargate

- Task definition: image từ ECR `pally-api`; env từ **Secrets Manager**.
- Service: desired count ≥ 1; health check → `/health`.
- RDS PostgreSQL thay Postgres local.

### B) App Runner

- Tạo service trỏ source = ECR image `pally-api`.
- Lưu ý: WebSocket cần kiểm tra giới hạn App Runner.

### C) EC2 + docker compose

- Máy EC2 cài Docker; kéo image từ ECR; phù hợp MVP.

## 6. Kéo image trên máy chủ

```bash
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin \
    $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

docker pull $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/pally-api:latest
```

## 7. Checklist sau khi có URL API production

- [ ] `VITE_PUBLIC_API_URL` = URL API (https).
- [ ] `CORS_ORIGINS` khớp domain web.
- [ ] `DATABASE_URL` trỏ RDS, không dùng `localhost`.
