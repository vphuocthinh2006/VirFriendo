# Tích hợp Source of Mana ↔ Companion API

## Đã có sẵn trong repo companion

- **Backend:** `POST /game/external/decide`, `POST /game/external/demo-log` (cần JWT).
- **Addon Godot (bản copy):** `integrations/sourceofmana/godot_addon/companion_ai/`

## Bước 1 — Clone game (nếu chưa có)

```bash
git clone https://github.com/sourceofmana/sourceofmana.git
```

**Không** bắt buộc đặt clone bên trong repo companion (thư mục `upstream/` có thể rất lớn — có thể đã được `.gitignore`).

## Bước 2 — Copy addon vào game

Sao chép cả thư mục `companion_ai` vào project Godot:

- Đích: `sourceofmana/addons/companion_ai/` (cùng cấp với các addon khác).

Trong **Godot → Project → Project Settings → Plugins**, bật **CompanionAiBridge**.

## Bước 3 — Chạy API

Từ repo companion (đã có `uvicorn`):

```bash
uvicorn services.core.main:app --reload
```

Đăng nhập web app → copy **Bearer token** (localStorage `access_token`) → dán vào Inspector của node `GodotAiBridge` (`bearer_token`), hoặc set trong code **chỉ lúc dev**.

## Bước 4 — Scene thử

1. Tạo scene mới: root `Node`, thêm child `GodotAiBridge`, thêm child script `companion_ai_test_runner.gd` trên root (hoặc dùng `example_ai_controller.gd` ở thư mục cha).
2. Chạy scene → **Space** (ui_accept) → xem **Output** có `action=` / `source=`.

Nếu lỗi 401: token hết hạn hoặc sai URL (`api_base_url` phải trùng `VITE_API_URL`).

## Bước 5 — Gắn vào game thật (sau này)

Source of Mana là **MMORPG**; AI mobs dùng `sources/ai/AI.gd` + `AIAgent`. Hướng lâu dài:

1. Định nghĩa `state` + `actions` cho **một** mob hoặc **pet** (chuỗi string ổn định).
2. Trong tick AI (hoặc `AI.Refresh`), nếu bật chế độ remote: gọi `request_decide` **bất đồng bộ** — cần hàng đợi hành động để không block frame.
3. **Server authority:** nếu có server riêng, logic bot nên chạy **server-side**; client chỉ hiển thị. Bridge HTTP trên client chỉ phù hợp **dev / offline bot**.

## File tham khảo trong clone

- `sources/ai/AI.gd` — vòng lặp `Refresh` / `HandleBehaviour`.
- `sources/actor/agent/variants/AIAgent.gd` — biến `aiBehaviour`, `WalkToward`, v.v.

Chỉnh sửa trực tiếp cần **fork** và tuân **license** của Source of Mana.
