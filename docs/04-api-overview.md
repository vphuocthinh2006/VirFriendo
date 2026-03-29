# 04 — API & WebSocket (tổng quan)

## 4.1 Routers đăng ký trong `main.py`

| Router | Module | Ghi chú |
|--------|--------|---------|
| Auth | `services.core.api.auth` | Đăng ký / đăng nhập / JWT |
| Agents | `services.core.api.agents` | API liên quan agent cấu hình |
| Chat | `services.core.api.chat` | REST + **WebSocket** chat |
| Diary | `services.core.api.diary` | Nhật ký / mood (nếu bật) |
| Game | `services.core.api.game` | Mini-game |
| External game | `services.core.api.external_game` | Tích hợp game ngoài |
| Caro | `services.core.api.caro` | Cờ caro |

Chi tiết đường dẫn xem OpenAPI tại `/docs` khi bật (môi trường dev).

## 4.2 Health

- `GET /health` — JSON `status`, `project`, `version`. Dùng cho probe sau khi container hoá / đưa lên orchestrator.

## 4.3 WebSocket

- Router `chat` có `prefix="/chat"`; endpoint WS: **`/chat/ws`** (query `token` — xem `services/core/api/chat.py` và `createChatWs` trong `frontend/src/services/api.ts`).
- **Dev:** client dùng `ws://localhost:8000/chat/ws?...` (không proxy qua Vite).
