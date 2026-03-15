# Frontend — AI Anime Companion

React 18 + Vite + TypeScript + TailwindCSS.

## Chạy local

1. Cài dependency: `npm install`
2. Chạy backend (Core API) tại port 8000, ví dụ: `uvicorn services.core.main:app --reload --host 0.0.0.0 --port 8000`
3. Chạy frontend: `npm run dev` → mở http://localhost:5173

Proxy Vite đã cấu hình: `/auth` và `/chat` được chuyển tới `http://localhost:8000`.

## Trang

- **/** — Landing (Đăng nhập / Đăng ký)
- **/login** — Đăng nhập
- **/register** — Đăng ký
- **/chat** — Trò chuyện (cần đăng nhập)

## Build

```bash
npm run build
```

File tĩnh nằm trong `dist/`. Production cần set `VITE_API_URL` trỏ tới backend.
