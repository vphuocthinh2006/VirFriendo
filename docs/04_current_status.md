# Trạng thai hien tai & Buoc tiep theo (VirFriendo)

> Cap nhat: 2026-03-20

---

## 1. Project dang o buoc nao?

| Phase | Noi dung | Trang thai |
|-------|----------|------------|
| **Phase 1 — Foundation** | Monorepo, Docker, DB, Auth, Chat API, Frontend | **~95%** — Thieu CI/CD |
| **Phase 2 — Core AI** | Intent/Emotion, RAG, Agents, LLM, Retriever Router | **~80%** — Thieu WebSocket streaming, ChromaDB |
| **Phase 3 — Avatar & Frontend** | Avatar animation, Mood tracking | **~30%** — Frontend co, avatar chua animation |
| **Phase 4 — Games & Extras** | Chess, Quiz, Bibliotherapy | **0%** |
| **Phase 5 — Production** | K8s, Monitoring, Tests, Docs | **~10%** — Co Docker Compose, chua CI/CD |

**Ket luan:** Project dang o **giua Phase 2**. Backend, frontend, AI pipeline (intent + emotion + RAG + LLM + judge + user memory) deu hoat dong. Can lam tiep: WebSocket streaming, tests, cleanup, roi avatar animation.

---

## 2. Da co (implemented & working)

### Infrastructure
- **Docker Compose:** PostgreSQL 16, Redis 7, ChromaDB
- **Database:** Schema User, Conversation, Message, UserMemory (Alembic migrations)
- **Auth:** Register, Login, JWT; `get_current_user_id` cho protected routes

### Backend API (FastAPI)
- `POST /chat` — gui tin, chay LangGraph, tra reply + intent + emotion + avatar_action
- `GET /chat/conversations` — danh sach hoi thoai
- `GET /chat/history/{id}` — lich su tin nhan

### LangGraph Workflow
- **6 agent nodes:** chit_chat, guardrail, entertainment_expert, comfort, advice, crisis
- **Intent classifier:** Hybrid keyword + Groq LLM (co the bat PEFT model qua env)
- **Emotion detector:** Keyword-based (7 class) trong emotion_node
- **Retriever Router:** Groq reasoning chon retriever tot nhat truoc khi search

### Entertainment Expert (RAG Pipeline)
- **4 retriever sources:** AniList API, Wikipedia API, Community Search (Reddit/Fandom/wiki.gg via Tavily), Tavily Web Search
- **Retriever Router:** Groq phan tich cau hoi → chon retriever phu hop (anilist/wiki/community/tavily)
- **Fallback chain:** Primary retriever → fallback qua cac retriever con lai
- **Knowledge Judge:** LLM-based anti-hallucination, kiem tra draft answer vs references
- **Dynamic KEEP_TERMS:** Tu dong extract proper nouns tu references de giu nguyen khi dich
- **Community Presenter:** Format rieng cho community sources (trich dan + subreddit attribution)
- **Query normalization:** Strip Vietnamese filler, router artifacts, summarization qualifiers

### User Memory
- Tu dong extract facts/preferences/triggers tu hoi thoai
- Inject vao context cho cac lan chat sau
- Luu trong bang `user_memories` (PostgreSQL)

### LLM Integration
- **Groq** (llama-3.1-8b-instant) — primary, nhanh
- **OpenAI** (gpt-4o) — fallback
- Persona system (tuq27 — anime girl character)
- Fine-tuning dataset (Level 2, 50+ mau JSONL)

### Frontend (React + Vite + TypeScript)
- Visual Novel UI: stage, portrait, dialogue chunks
- Karaoke text effect (tung chu doi mau)
- Login/Register pages
- Chat interface voi conversation management
- Nature-inspired theme (do, chill, branch decorations)
- TailwindCSS styling

---

## 3. Chua co / Can lam

### Uu tien cao (P0)
- [ ] **WebSocket / Streaming:** Chat chi REST, chua real-time streaming
- [ ] **Tests (pytest):** 0 test — can test auth, chat API, intent classifier
- [ ] **CI/CD:** Chua co GitHub Actions (lint, test, build)

### Uu tien vua (P1)
- [ ] **Avatar Animation:** Frontend co stage nhung chua co PixiJS/Spine animation theo emotion
- [ ] **Mood Tracking API:** Co user_memory nhung chua co mood timeline/dashboard
- [ ] **ChromaDB RAG:** Co trong docker-compose nhung chua dung (dang dung external APIs)
- [ ] **Translation Layer:** Chua co VN↔EN translation rieng (Groq/LLM dang handle)

### Uu tien thap (P2)
- [ ] **Mini-games:** Chess (Stockfish), Anime Quiz
- [ ] **Adaptive Personality:** relationship_level
- [ ] **TTS:** Text-to-speech anime voice

---

## 4. Technical Debt

- [ ] Xoa folder `services/agent-service/` (cu, duplicate voi `services/agent_service/`)
- [ ] Commit + push tat ca code chua commit len GitHub
- [ ] Update `.env.example` cho day du cac env vars moi

---

## 5. Architecture Overview

```
Frontend (React + Vite + TS) — Visual Novel UI
    |
Core API (FastAPI) — Auth + Chat + LangGraph
    |
    +-- Intent Classifier (Hybrid: Keyword + Groq)
    +-- Emotion Detector (Keyword-based)
    +-- Retriever Router (Groq Reasoning)
    |       |
    |       +-- AniList API (anime/manga)
    |       +-- Wikipedia API (factual)
    |       +-- Community Search (Reddit/Fandom via Tavily)
    |       +-- Tavily Web Search (general)
    |
    +-- Knowledge Judge (anti-hallucination)
    +-- User Memory (extract + inject)
    |
Data — PostgreSQL, ChromaDB (unused), Redis (docker-compose)
```
