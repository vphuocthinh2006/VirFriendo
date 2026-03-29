# 06 — Roadmap hạ tầng (mục tiêu platform)

Tài liệu này mô tả **hướng đi** để VirFriendo có **độ sâu kỹ thuật vận hành** tương tự một repo platform (Docker → CI → cloud), **không** cam kết mọi mục đã triển khai trong repo tại thời điểm đọc — kiểm tra nhánh `main` và thư mục `infra/` (nếu có).

## Pha 0 — Hiện trạng (baseline)

- Local: Python + Node + **Docker Compose** cho Postgres / Redis / Chroma.
- API: `uvicorn services.core.main:app`.
- Tài liệu: `docs/` (mục lục `docs/README.md`).

## Pha 1 — Đóng gói ứng dụng

- [ ] `Dockerfile` cho API (multi-stage, user không root, healthcheck trỏ `/health`).
- [ ] Mở rộng `docker-compose`: service `api` phụ thuộc `database`, `redis`, `chromadb`; biến môi trường inject từ `.env`.
- [ ] (Tuỳ) `Dockerfile` frontend + nginx static hoặc dev chỉ chạy `npm run dev` ngoài container.

## Pha 2 — CI

- [ ] GitHub Actions: cài Python, `pip install`, `ruff` / `pytest` (khi `tests/` được đưa vào CI).
- [ ] Build image và push **Container Registry** (GHCR / ECR / GCR) theo tag commit.

## Pha 3 — Kubernetes (tối thiểu)

- [ ] Manifest hoặc **Helm chart**: Deployment + Service + Ingress; Secret cho `DATABASE_URL`, `SECRET_KEY` (External Secrets hoặc sealed secrets).
- [ ] Probe: `liveness` / `readiness` dùng `/health`.

## Pha 4 — Infrastructure as Code

- [ ] **Terraform** (chọn **một** cloud): VPC, cluster managed (EKS/GKE), DB managed nếu có, registry IAM.
- [ ] Tài liệu: region, ước tính cost, lệnh `terraform destroy` cho môi trường thử.

## Pha 5 — Quan sát & vận hành

- [ ] Logs tập trung (Fluent Bit → stack logging hoặc cloud logging).
- [ ] Metrics (Prometheus + Grafana hoặc managed).
- [ ] Cảnh báo cơ bản (5xx, latency).

## Nguyên tắc

- **Một cloud làm chuẩn** trên CV (AWS *hoặc* GCP), tránh dàn trải khi học.
- **Secrets không** trong Git; chỉ template `.env.example` (không giá trị thật).
