# 03 — Data & Storage

## 3.1 Aurora Serverless v2 (Production)

- **Engine:** PostgreSQL 16.6
- **Capacity:** 0.5–4 ACU (scales to near-zero when idle)
- **Multi-AZ:** Yes (writer + reader replica)
- **Endpoint:** `virfriendo-aurora.cluster-cvggyooq6zi9.ap-southeast-1.rds.amazonaws.com`
- **Encryption:** At rest enabled

### Tables

| Table | Purpose |
|-------|---------|
| `users` | Accounts (UUID, username, email, password_hash) |
| `conversations` | Chat sessions per user |
| `messages` | All messages (role, content, detected_intent, detected_emotion, dialogue_act, ml_metadata, avatar_action) |
| `user_memories` | Extracted facts/preferences (type, content, is_active) |
| `diary_entries` | User diary lines per companion |
| `agent_stats` | Play counts per agent |
| `user_agent_likes` | Like tracking |
| `user_agent_relationships` | Per-companion message count → relationship level |

## 3.2 S3

- **Bucket:** `virfriendo-media-ap-southeast-1`
- **Prefixes:**
  - `media/` — user uploads, generated images, voice clips
  - `models/` — ML model files (BERT, ViT, gallery embeddings)
  - `ml-predictions/` — prediction logs (JSONL, for monitoring)
- **Access:** Public blocked. Clients use 7-day presigned URLs.

## 3.3 Redis (Optional)

- **Purpose:** Quickstart personality cache (user lines → LLM summary)
- **Production:** Not deployed (graceful degradation — feature skipped if unavailable)
- **Local dev:** `redis:7-alpine` in docker-compose

## 3.4 ChromaDB (Optional)

- **Purpose:** Character gallery vector search (alternative to numpy)
- **Production:** Not deployed (numpy flat file used instead)
- **Local dev:** `chromadb/chroma:latest` in docker-compose
- **Config:** `GALLERY_VECTOR_BACKEND=numpy` (default) or `chroma`

## 3.5 Secrets Manager

- **Secret:** `virfriendo/prod/database`
- **Contains:** DATABASE_URL, SECRET_KEY, all API keys (Groq, OpenAI, Gemini, Deepgram, Replicate, Tavily, Anthropic), LLM_PROVIDER, APP_ENV
