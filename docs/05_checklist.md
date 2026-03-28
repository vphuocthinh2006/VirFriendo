# Checklist — phát triển & production (VirFriendo)

> **Cập nhật:** 2026-03-29  
> Trạng thái tổng quan: [04_current_status.md](04_current_status.md)

Dùng danh sách này khi chuẩn bị release hoặc merge nhánh lớn. Đánh dấu `[x]` trong bản sao của bạn (hoặc issue tracker).

---

## A. Môi trường dev (mỗi máy / mỗi lần onboard)

- [ ] Python 3.10+, Node 18+, Docker (cho Postgres/Redis/Chroma).
- [ ] `cp .env.example .env` ở **root repo**; điền `SECRET_KEY`, `DATABASE_URL`, khóa LLM/search theo nhu cầu.
- [ ] `docker compose up -d` (hoặc tương đương) để có DB.
- [ ] `pip install -r requirements.txt`; chạy API: `uvicorn services.core.main:app --reload --port 8000`.
- [ ] `cd frontend && npm install && npm run dev` — frontend dev mặc định gọi API **`http://localhost:8000`** (xem `src/services/api.ts`).
- [ ] Đăng ký/đăng nhập thử; chat REST + (nếu cần) WebSocket `ws://localhost:8000/chat/ws` sau khi có token.

---

## B. Trước khi merge PR / tag bản

- [ ] `pytest` (từ root, với `PYTHONPATH` / venv đúng) — ít nhất các test không cần API key thật.
- [ ] `cd frontend && npx vite build` (hoặc `npm run build` nếu `tsc` sạch).
- [ ] Không commit `.env`, không commit secret.
- [ ] Chạy `alembic upgrade head` trên DB sạch hoặc staging nếu có migration mới.

---

## C. Production / staging (triển khai thật)

### Cấu hình

- [ ] **HTTPS** (reverse proxy hoặc PaaS).
- [ ] **`VITE_API_URL`** trỏ đúng URL public của API khi **build** frontend.
- [ ] **`SECRET_KEY`** production khác dev; rotate nếu lộ.
- [ ] **CORS:** hiện code dùng `allow_origins=["*"]` — trước khi public rộng, thu hẹp origin theo domain frontend.
- [ ] **Database:** backup định kỳ; `DATABASE_URL` trên server.

### Vận hành

- [ ] Health check: `GET /health`.
- [ ] Log lỗi (stdout → collector hoặc file rotate).
- [ ] (Tùy chọn) Uptime/cảnh báo khi API down.

### Chưa bắt buộc nhưng “chuẩn lớn”

- [ ] GitHub Actions: lint + test + build.
- [ ] Container image cho API + tài liệu `docker run`.
- [ ] Staging environment giống prod.

---

## D. Backlog sản phẩm (nhắc nhanh)

- [ ] CI/CD đầy đủ.
- [ ] Avatar animation theo emotion (Phase 3).
- [ ] Chroma / embedding pipeline nếu cần RAG offline (Phase 2 nâng cao).
- [ ] Mood dashboard (Phase 3).
- [ ] Game/quiz mở rộng (Phase 4).

---

## E. Tài liệu

- [ ] README root phản ánh cách chạy hiện tại (API port 8000, frontend 5173).
- [ ] Cập nhật `04_current_status.md` khi đổi phase lớn hoặc mỗi sprint.
