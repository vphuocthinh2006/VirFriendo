# 06 — Roadmap hạ tầng

## Pha 0 — Hiện trạng

- Local: Python + Node + **Docker Compose** cho Postgres / Redis / Chroma.
- API: `uvicorn services.core.main:app`.
- Tài liệu: `docs/`.

## Pha 1 — Đóng gói ứng dụng

- [x] `Dockerfile` cho API (multi-stage, healthcheck `/health`).
- [x] `docker-compose.yml`: `api`, `database`, `redis`, `chromadb`, `web`.
- [x] `Dockerfile` frontend + nginx static (service `web`, host `8081→80`).

## Pha 2 — CI

- [ ] GitHub Actions: `ruff` / `pytest`.
- [x] Build image và push **Amazon ECR** — `.github/workflows/ecr-publish.yml`.
- [ ] Deploy AWS (ECS / App Runner): xem `docs/09-aws-ecr-ecs.md`.

## Pha 3 — Kubernetes

- [ ] Helm chart: Deployment + Service + Ingress.
- [ ] Probe: `liveness` / `readiness` → `/health`.

## Pha 4 — Infrastructure as Code

- [ ] **Terraform**: VPC, cluster managed (EKS), DB managed, registry IAM.

## Pha 5 — Quan sát & vận hành

- [ ] Logs tập trung (Fluent Bit).
- [ ] Metrics (Prometheus + Grafana).
- [ ] Cảnh báo cơ bản (5xx, latency).

## Nguyên tắc

- **Một cloud làm chuẩn** (AWS).
- **Secrets không** trong Git — chỉ `.env.example` (không giá trị thật).
