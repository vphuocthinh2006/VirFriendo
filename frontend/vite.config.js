import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
    plugins: [react()],
    build: {
        rollupOptions: {
            output: {
                manualChunks: function (id) {
                    if (id.indexOf('node_modules/three') !== -1 || id.indexOf('@react-three') !== -1) {
                        return 'vendor-three';
                    }
                },
            },
        },
    },
    server: {
        port: 5173,
        proxy: {
            '/auth': { target: 'http://localhost:8000', changeOrigin: true },
            // API: POST /chat, GET /chat/conversations, WS /chat/ws — but React route is GET /chat
            // Without bypass, GET /chat is proxied to FastAPI → 405. Serve SPA index.html instead.
            '/chat': {
                target: 'http://localhost:8000',
                changeOrigin: true,
                ws: true,
                bypass: function (req) {
                    var _a;
                    if (req.method !== 'GET')
                        return undefined;
                    var path = ((_a = req.url) !== null && _a !== void 0 ? _a : '').split('?')[0];
                    if (path === '/chat' || path === '/chat/')
                        return '/index.html';
                    return undefined;
                },
            },
        },
    },
});
