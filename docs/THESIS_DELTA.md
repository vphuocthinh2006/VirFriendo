# VirFriendo — thay đổi so với commit baseline

**Baseline (commit cũ để so sánh):** `ead8542` — *Phase 2 consolidation: RAG pipeline, retriever router, user memory, tests, cleanup*  
**Snapshot này:** nhánh `thesis/mar2026-snapshot` (tháng 3/2026)

Tài liệu này tóm tắt **những gì đã có thêm / đổi** so với baseline; không thay cho `git log`.

---

## Backend (`services/core`)

- **API external game / companion:** `POST /game/external/decide`, `POST /game/external/demo-log` (JWT), module `services/core/external_game_ai.py` (rules + chỗ mở rộng LLM).
- **API mở rộng:** `agents`, `caro`, `diary`, `game`, `turn_game`; `chess_platforms`, `quickstart_personality`, `redis_client`, `turn_game_ai`.
- **Auth / chat / models / security / config:** chỉnh tương ứng để nối route mới và tính năng (chi tiết xem diff trong repo).

## Agent service (`services/agent_service`)

- Pipeline giải trí: `entertainment_pipeline.py`.
- Retriever: `agentic_retriever`, `fanwiki_search`, `reddit_search`, `retrieval_auditor`.
- Cập nhật `intent_classifier`, `agents`, `graph`, `workflow`, `knowledge_judge`, `client`.

## Frontend

- Trang / luồng: `Menu`, `Contact`, `ForgotPassword`, `Updates`; `landingRoutes`, `games`, `components`, `constants`, `data`, `utils`.
- Hooks: `useAuthBootOverlay`, `GoogleSignIn`.
- `App`, `Chat`, `Landing`, `Login`, `Register`, `api`, styles — mở rộng lớn (UI + tích hợp API).

## Tích hợp Source of Mana (Godot)

- Thư mục `integrations/sourceofmana/`: addon **CompanionAiBridge** (`godot_ai_bridge.gd`, `companion_ai_test_runner.gd`, plugin), `INTEGRATION.md`, `README.md`, `example_ai_controller.gd`.
- Copy vào game: `addons/companion_ai/` — gọi backend đã deploy (đã test thành công với `action=` / `source=rules`).

## Database & migration

- `migrations/versions/b3e4c5d6e7f8_agent_engagement.py`

## Scripts & tests

- `benchmark_retrievers.py`, `blender_owlbear_walk.py`, `build_golden_intent_dataset.py`, `generate_golden_samples_openai.py`, `generate-changelog.mjs`, `sql/`.
- `tests/golden_retrieval.jsonl`, `tests/test_ws.py`

## Dữ liệu & export

- `data/` (trong repo; raw/processed vẫn tuân `.gitignore` có sẵn).
- `exports/` (nếu có trong commit).

## Không đưa vào Git (cố ý)

- **`.env`** — secrets; chỉ có `.env.example`.

---

## Cách xem diff đầy đủ

```bash
git diff ead8542..HEAD
git log ead8542..HEAD --oneline
```

---

## Ghi chú đẩy lên GitHub

Sau khi pull snapshot này, chạy:

```bash
git fetch origin
git checkout thesis/mar2026-snapshot
# hoặc merge vào main khi đã review
```
