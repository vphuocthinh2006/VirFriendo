# 04 — API & WebSocket (tổng quan)

## 4.1 Routers

| Router | Module | Ghi chú |
|--------|--------|---------|
| Auth | `services.core.api.auth` | Đăng ký / đăng nhập / JWT / Google OAuth |
| Agents | `services.core.api.agents` | Stats, like, play count |
| Chat | `services.core.api.chat` | REST + WebSocket + Voice + Vision + Imagine |
| Diary | `services.core.api.diary` | Nhật ký |
| Game | `services.core.api.game` | Chess, Caro |
| External game | `services.core.api.external_game` | Tích hợp game ngoài |
| Caro | `services.core.api.caro` | Cờ caro |

## 4.2 Chat endpoints

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/chat` | Gửi tin nhắn (REST) |
| WS | `/chat/ws` | Stream chat (WebSocket) |
| GET | `/chat/conversations` | Danh sách conversations |
| GET | `/chat/history/{id}` | Lịch sử tin nhắn |
| DELETE | `/chat/conversations/{id}` | Xóa conversation |
| GET | `/chat/memories` | User memories |
| GET | `/chat/relationship` | Relationship stats |
| POST | `/chat/transcribe` | Voice → text (Deepgram / Groq) |
| POST | `/chat/analyze-media` | Phân tích ảnh/video/URL (Gemini / GPT-4o) |
| POST | `/chat/imagine` | Text → image (Replicate FLUX) |

## 4.3 Health

- `GET /health` — JSON `status`, `project`, `version`.

## 4.4 WebSocket protocol

**Client → Server:**
```json
{"type": "message", "content": "...", "conversation_id": "..." }
```

**Server → Client:**
```json
{"type": "stream_start", "conversation_id": "..."}
{"type": "token", "content": "..."}
{"type": "stream_end", "detected_intent": "...", "detected_emotion": "..."}
```

**Auth:** query param `?token=<JWT>` — `ws://localhost:8000/chat/ws?token=...`

## 4.5 OpenAPI

`/docs` khi `DEBUG=true` hoặc `APP_ENV != production`.
