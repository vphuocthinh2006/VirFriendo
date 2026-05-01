# Pally — Tài liệu kỹ thuật

Mục lục theo thứ tự đọc gợi ý.

| # | Tài liệu | Mô tả ngắn |
|---|----------|------------|
| 01 | [Kiến trúc hệ thống](./01-architecture.md) | Thành phần, luồng dữ liệu, boundary `core` / `agent_service` |
| 02 | [Chạy local & môi trường](./02-local-development.md) | Python, Node, Docker Compose, biến môi trường, cổng |
| 03 | [Dữ liệu & lưu trữ](./03-data-and-storage.md) | PostgreSQL, Redis, ChromaDB, migration |
| 04 | [API & WebSocket](./04-api-overview.md) | Router chính, health, WS chat |
| 05 | [Pipeline agent (LangGraph)](./05-agent-pipeline.md) | Intent, workflow agent, RAG |
| 06 | [Roadmap hạ tầng](./06-roadmap-infra.md) | Pha local → container → CI/CD → cloud |
| 07 | [Bảo mật & bí mật](./07-security-and-secrets.md) | JWT, CORS, production checks |
| 08 | [Xử lý sự cố](./08-troubleshooting.md) | WS, DB, dev thường gặp |
| 09 | [AWS ECR & deploy](./09-aws-ecr-ecs.md) | ECR, GitHub Actions, ECS / App Runner |
| 10 | [Chuẩn bị AWS](./10-aws-run-app-prep.md) | RDS, Secrets Manager, checklist trước ECS |

---

## Người đọc mục tiêu

- **Contributor / backend:** 01 → 02 → 04 → 05
- **DevOps / platform:** 01 → 06 → 09 → 07 → 02
- **Frontend:** 02 → 04 (REST + WS)

---

## Trạng thái tài liệu

| Khu vực | Mức độ |
|---------|--------|
| Kiến trúc & local dev | Đồng bộ với code hiện tại |
| Voice / Vision / Imagine | Đồng bộ (Deepgram, Gemini, Replicate FLUX) |
| Hạ tầng cloud | Kế hoạch — chi tiết tại [06-roadmap-infra.md](./06-roadmap-infra.md) |
